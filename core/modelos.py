# -*- coding: utf-8 -*-
"""
Modelos de datos, estados y excepciones del buscador de infracciones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable, List

if TYPE_CHECKING:
    from core.captcha import CaptchaSolver

# =============================================================================
# ESTADOS POSIBLES DE UNA CONSULTA
# =============================================================================
ESTADOS_OK = ("con_multas", "sin_multas")
ESTADOS_FALLO = ("error", "captcha_fallido", "indeterminado", "caido")

ESTADO_UI = {
    "con_multas": ("Con multas", "good"),
    "sin_multas": ("Sin multas", "good"),
    "error": ("Error de conexión", "bad"),
    "captcha_fallido": ("Captcha falló", "bad"),
    "indeterminado": ("No se pudo leer", "warn"),
    "sin_conector": ("Consulta manual", "neutral"),
    "caido": ("Servidor caído", "bad"),
    "simulacro": ("Listo (sin gastar captcha)", "good"),
}


# =============================================================================
# EXCEPCIONES PROPIAS
# =============================================================================
class CaptchaError(Exception):
    """Falla del servicio de captcha (saldo, clave, timeout o rechazo del portal)."""


class ConsultaIndeterminada(Exception):
    """El portal respondió, pero no se pudo interpretar el resultado."""

    def __init__(self, msg: str, http_status: int | None = None, muestra: str = ""):
        super().__init__(msg)
        self.http_status = http_status
        self.muestra = muestra


# =============================================================================
# MODELOS DE DATOS (MOLDES)
# =============================================================================
@dataclass
class Infraccion:
    acta: str
    descripcion: str
    monto: float | None
    controlador: bool = False
    etiquetas: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.controlador and "MULTA CON CONTROLADOR" not in self.etiquetas:
            self.etiquetas.append("MULTA CON CONTROLADOR")
        self.controlador = "MULTA CON CONTROLADOR" in self.etiquetas


@dataclass
class RespuestaPortal:
    infracciones: List[Infraccion]
    http_status: int | None = None
    muestra: str = ""
    total_oficial: float | None = None
    declaradas: int | None = None
    nota: str = ""
    vigencia: str = ""


@dataclass
class ResultadoJurisdiccion:
    nombre: str
    proteccion: str
    url: str
    estado: str = "pendiente"
    detalle: str = ""
    http_status: int | None = None
    muestra: str = ""
    demo: bool = False
    infracciones: List[Infraccion] = field(default_factory=list)
    total_oficial: float | None = None
    declaradas: int | None = None
    nota: str = ""
    vigencia: str = ""
    desde_cache: bool = False

    @property
    def conectado(self) -> bool:
        return self.estado in ESTADOS_OK

    @property
    def suma_lista(self) -> float:
        return sum(i.monto or 0 for i in self.infracciones)

    @property
    def subtotal(self) -> float:
        return self.total_oficial if self.total_oficial is not None else self.suma_lista


@dataclass
class JurisdiccionConfig:
    nombre: str
    proteccion: str
    url: str
    consultar: Callable[[str, CaptchaSolver], Awaitable[RespuestaPortal]] | None = None
    urls_chequeo: tuple = ()
    consultar_pausado: Callable | None = None