# -*- coding: utf-8 -*-
"""
Backend FastAPI para Marcelo Nuñez Gestiones.
Reutiliza core/ y conectores/ para consultar infracciones por patente.

Ejecutar (desde la carpeta del proyecto, con el entorno virtual activo):
    python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
"""
from __future__ import annotations

import asyncio
import copy
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from conectores.avellaneda import URL_AVELLANEDA_API, consultar_avellaneda
from conectores.base import nuevo_cliente
from conectores.caba import URL_CABA, consultar_caba
from conectores.entre_rios import API_ENTRE_RIOS, URL_ENTRE_RIOS, consultar_entre_rios
from conectores.lomas import URL_LOMAS, consultar_lomas
from conectores.pba import URL_PBA, URL_PBA_API, consultar_pba
from conectores.vicente_lopez import URL_VL, URL_VL_DATOS, consultar_vicente_lopez
from core.captcha import CaptchaSolver, SimulacroListo, SolverSimulacro
from core.config import cargar_config_captcha, cargar_en_entorno, diagnostico_entorno
from core.modelos import (
    ESTADOS_FALLO,
    ESTADOS_OK,
    CaptchaError,
    ConsultaIndeterminada,
    JurisdiccionConfig,
    RespuestaPortal,
    ResultadoJurisdiccion,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gestoria")

RAIZ = Path(__file__).resolve().parent
STATIC_DIR = RAIZ / "static"
STATIC_DIR.mkdir(exist_ok=True)

TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")
PATRON_PATENTE = re.compile(r"^([A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2}|[A-Z]\d{3}[A-Z]{3}|\d{3}[A-Z]{3})$")
CACHE_TTL_SEG = 600
SERVIDORES_TTL_SEG = 45

# Copia al entorno las variables de .env / secrets.toml (solo si faltan). Se loguean NOMBRES, nunca valores.
_CARGADAS = cargar_en_entorno()
if _CARGADAS:
    log.info("Variables cargadas desde archivos de configuración: %s", ", ".join(sorted(_CARGADAS)))

_CACHE: dict[tuple[str, str], tuple[float, ResultadoJurisdiccion]] = {}
_SERVIDORES_CACHE: dict[str, Any] = {"momento": 0.0, "datos": None}

JURISDICCIONES: List[JurisdiccionConfig] = [
    JurisdiccionConfig("CABA", "reCAPTCHA", URL_CABA, consultar_caba),
    JurisdiccionConfig(
        "PBA",
        "reCAPTCHA",
        URL_PBA,
        consultar_pba,
        urls_chequeo=((URL_PBA, False), (URL_PBA_API, True)),
    ),
    JurisdiccionConfig(
        "Entre Ríos",
        "Cloudflare Turnstile",
        "https://monitoreovialentrerios.info/#/consulta-infracciones",
        consultar_entre_rios,
        urls_chequeo=((URL_ENTRE_RIOS, False), (API_ENTRE_RIOS, True)),
    ),
    JurisdiccionConfig(
        "Avellaneda",
        "Sin CAPTCHA",
        "https://multas.mda.gob.ar",
        consultar_avellaneda,
        urls_chequeo=(("https://multas.mda.gob.ar/", False), (URL_AVELLANEDA_API, True)),
    ),
    JurisdiccionConfig("Lomas de Zamora", "Sin CAPTCHA", URL_LOMAS, consultar_lomas),
    JurisdiccionConfig(
        "Vicente López",
        "Cloudflare Turnstile",
        URL_VL,
        consultar_vicente_lopez,
        urls_chequeo=((URL_VL, False), (URL_VL_DATOS, True)),
    ),
]


class ConsultaRequest(BaseModel):
    """Si el frontend manda un campo con otro nombre (por ejemplo ignorarCache) se responde 422
    en vez de ignorarlo en silencio."""

    model_config = ConfigDict(extra="forbid")

    patente: str = Field(min_length=5, max_length=12)
    simulacro: bool = False
    ignorar_cache: bool = False


app = FastAPI(title="Marcelo Nuñez Gestiones API", version="1.1.0")

# El frontend se sirve desde el mismo origen (127.0.0.1:8000), así que no hace falta abrir CORS a todo el mundo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def sin_cache_en_desarrollo(request: Request, call_next):
    """Evita que el navegador use una versión vieja de app.js / styles.css mientras desarrollás."""
    respuesta = await call_next(request)
    ruta = request.url.path
    if ruta == "/" or ruta.startswith("/static") or ruta.startswith("/api"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


# ----------------------------------------------------------------------------- utilidades
def normalizar_patente(texto: str) -> str:
    return re.sub(r"[\s\-.]", "", texto or "").upper()


def pesos(valor: float | None) -> str:
    if valor is None:
        return "-"
    s = f"{valor:,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _suma_lista(r: ResultadoJurisdiccion) -> float:
    return sum((inf.monto or 0) for inf in r.infracciones)


def _obtener_solver(simulacro: bool) -> tuple[Any, dict[str, Any]]:
    """La clave se lee en CADA consulta desde core.config (entorno, .env o .streamlit/secrets.toml)."""
    cfg = cargar_config_captcha()
    if simulacro:
        return SolverSimulacro(), cfg
    return CaptchaSolver(cfg["proveedor"], cfg["api_key"]), cfg


async def _consultar_una(cfg: JurisdiccionConfig, patente: str, solver: Any) -> ResultadoJurisdiccion:
    r = ResultadoJurisdiccion(cfg.nombre, cfg.proteccion, cfg.url)
    if cfg.consultar is None:
        r.estado = "sin_conector"
        r.detalle = "Consulta automática no disponible para este portal."
        return r

    try:
        resp: RespuestaPortal | None = None
        for intento in (1, 2):  # un reintento solo ante fallos de red (no gasta captcha extra)
            try:
                resp = await asyncio.wait_for(cfg.consultar(patente, solver), timeout=150)
                break
            except httpx.TransportError:
                if intento == 2:
                    raise
                await asyncio.sleep(1.5)
        assert resp is not None
        r.infracciones = resp.infracciones
        r.http_status = resp.http_status
        r.muestra = resp.muestra
        r.total_oficial = resp.total_oficial
        r.declaradas = resp.declaradas
        r.nota = resp.nota
        r.vigencia = resp.vigencia
        r.estado = "con_multas" if resp.infracciones else "sin_multas"
    except SimulacroListo as exc:
        r.estado, r.detalle = "simulacro", str(exc)
    except CaptchaError as exc:
        r.estado, r.detalle = "captcha_fallido", str(exc)
    except ConsultaIndeterminada as exc:
        r.estado, r.detalle = "indeterminado", str(exc)
        r.http_status, r.muestra = exc.http_status, exc.muestra
    except asyncio.TimeoutError:
        r.estado, r.detalle = "error", "Timeout: el portal no respondió a tiempo."
    except Exception as exc:  # noqa: BLE001
        log.exception("Error inesperado consultando %s", cfg.nombre)
        r.estado, r.detalle = "error", f"{type(exc).__name__}: {exc}"

    clave = getattr(solver, "api_key", "") or ""
    if len(clave) >= 12:  # nunca dejar la clave en mensajes
        r.detalle = (r.detalle or "").replace(clave, "***")
        r.muestra = (r.muestra or "").replace(clave, "***")
    return r


def _serializar(r: ResultadoJurisdiccion, desde_cache: bool) -> dict[str, Any]:
    return {
        "jurisdiccion": r.nombre,
        "proteccion": r.proteccion,
        "url": r.url,
        "estado": r.estado,
        "detalle": r.detalle or "",
        "desde_cache": desde_cache,
        "subtotal": round(r.subtotal, 2),
        "subtotal_formato": pesos(r.subtotal),
        "suma_listada": round(_suma_lista(r), 2),
        "suma_listada_formato": pesos(_suma_lista(r)),
        "total_oficial": getattr(r, "total_oficial", None),
        "vigente_hasta": getattr(r, "vigencia", "") or None,
        "nota": getattr(r, "nota", "") or None,
        "infracciones_declaradas": getattr(r, "declaradas", None),
        "multas": [
            {
                "acta": inf.acta,
                "descripcion": inf.descripcion,
                "monto": inf.monto,
                "monto_formato": pesos(inf.monto),
                "etiquetas": list(inf.etiquetas or []),
            }
            for inf in r.infracciones
        ],
    }


# ----------------------------------------------------------------------------- servidores (chequeo gratis)
async def _chequear_url(url: str, permisivo: bool, timeout: int = 10) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        async with nuevo_cliente(timeout) as c:
            r = await c.get(url)
        ms = int((time.monotonic() - t0) * 1000)
        if permisivo or r.status_code < 400:
            return {"estado": "ok", "ms": ms, "codigo": r.status_code}
        if r.status_code in (403, 429):
            return {"estado": "bloqueado", "ms": ms, "codigo": r.status_code}
        if r.status_code >= 500:
            return {"estado": "caido", "ms": ms, "codigo": r.status_code}
        return {"estado": "ok", "ms": ms, "codigo": r.status_code}
    except Exception as exc:  # noqa: BLE001
        return {"estado": "caido", "ms": int((time.monotonic() - t0) * 1000), "error": type(exc).__name__}


async def _chequear_jurisdiccion(cfg: JurisdiccionConfig) -> dict[str, Any]:
    urls = cfg.urls_chequeo or ((cfg.url.split("#")[0], False),)
    checks = await asyncio.gather(*(_chequear_url(u, perm) for u, perm in urls))
    peso = {"ok": 0, "bloqueado": 1, "caido": 2}
    peor = max(checks, key=lambda x: peso[x["estado"]])
    return {
        "jurisdiccion": cfg.nombre,
        "proteccion": cfg.proteccion,
        "url": cfg.url,
        "estado": peor["estado"],
        "ms": max(x["ms"] for x in checks),
    }


@app.get("/api/servidores")
async def api_servidores() -> dict[str, Any]:
    ahora = time.time()
    if _SERVIDORES_CACHE["datos"] and ahora - _SERVIDORES_CACHE["momento"] < SERVIDORES_TTL_SEG:
        return _SERVIDORES_CACHE["datos"]
    resultados = await asyncio.gather(*(_chequear_jurisdiccion(c) for c in JURISDICCIONES))
    datos = {"actualizado_en": datetime.now(TZ_AR).isoformat(timespec="seconds"), "servidores": list(resultados)}
    _SERVIDORES_CACHE.update(momento=ahora, datos=datos)
    return datos


@app.get("/api/salud")
async def api_salud() -> dict[str, Any]:
    return {"ok": True, "hora": datetime.now(TZ_AR).isoformat(timespec="seconds")}


@app.get("/api/config/estado")
async def api_config_estado(request: Request) -> dict[str, Any]:
    """Diagnóstico de configuración SIN secretos. Solo responde a conexiones desde esta misma PC."""
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(status_code=404, detail="No encontrado")
    return diagnostico_entorno()


# ----------------------------------------------------------------------------- consulta principal
def _purgar_cache() -> None:
    ahora = time.time()
    for clave in [k for k, (t, _) in _CACHE.items() if ahora - t >= CACHE_TTL_SEG]:
        _CACHE.pop(clave, None)


async def _ejecutar_consulta(payload: ConsultaRequest) -> dict[str, Any]:
    dominio = normalizar_patente(payload.patente)
    if not PATRON_PATENTE.match(dominio):
        raise HTTPException(
            status_code=400,
            detail="Formato de patente inválido. Ejemplos: LVQ189, AB123CD, A123BCD, 123ABC.",
        )

    solver, cfg_captcha = _obtener_solver(payload.simulacro)
    clave_ok = bool(cfg_captcha.get("tiene_clave"))
    advertencias: list[str] = []
    if payload.simulacro:
        advertencias.append(
            "Modo simulacro: los portales con captcha NO se consultaron de verdad (no se gastó saldo). "
            "Solo se validó que el portal, el formulario y la clave estén listos."
        )
    elif not clave_ok:
        advertencias.append(
            "No hay API Key de captcha configurada: CABA, PBA, Entre Ríos y Vicente López no pueden consultarse. "
            "Creá el archivo .env con CAPSOLVER_API_KEY=tu-clave y reiniciá o volvé a consultar."
        )
    if payload.ignorar_cache:
        advertencias.append("Se ignoró el caché: todos los portales se consultaron de nuevo.")

    log.info(
        "consulta patente=%s simulacro=%s ignorar_cache=%s clave_captcha=%s proveedor=%s origen_clave=%s",
        dominio, payload.simulacro, payload.ignorar_cache,
        "sí" if clave_ok else "NO", cfg_captcha.get("proveedor"), cfg_captcha.get("origen"),
    )

    resultados: List[ResultadoJurisdiccion] = []
    desde_cache: set[str] = set()
    pendientes: List[JurisdiccionConfig] = []
    usar_cache = not payload.ignorar_cache and not payload.simulacro

    for cfg in JURISDICCIONES:
        if usar_cache:
            guardado = _CACHE.get((cfg.nombre, dominio))
            if guardado and (time.time() - guardado[0]) < CACHE_TTL_SEG:
                resultados.append(copy.deepcopy(guardado[1]))
                desde_cache.add(cfg.nombre)
                continue
        pendientes.append(cfg)

    if pendientes:
        nuevos = await asyncio.gather(*(_consultar_una(c, dominio, solver) for c in pendientes))
        for r in nuevos:
            if not payload.simulacro and r.estado in ESTADOS_OK:
                _CACHE[(r.nombre, dominio)] = (time.time(), copy.deepcopy(r))
            resultados.append(r)
        _purgar_cache()

    orden = {j.nombre: i for i, j in enumerate(JURISDICCIONES)}
    resultados.sort(key=lambda x: orden[x.nombre])

    con_multas = sorted((r for r in resultados if r.estado == "con_multas"), key=lambda r: -r.subtotal)
    fallos = [r for r in resultados if r.estado in ESTADOS_FALLO]
    sin_multas = [r.nombre for r in resultados if r.estado == "sin_multas"]
    n_multas = sum(len(r.infracciones) for r in con_multas)
    total = round(sum(r.subtotal for r in con_multas), 2)

    if n_multas:
        mensaje = f"Se encontraron {n_multas} multa(s) por {pesos(total)} en {len(con_multas)} jurisdicción(es)."
        if fallos:
            mensaje += f" ATENCIÓN: no se pudo consultar {', '.join(r.nombre for r in fallos)}; el total puede ser mayor."
    elif fallos:
        mensaje = (
            "No se encontraron multas en los portales que respondieron, pero "
            f"{len(fallos)} no pudieron consultarse: {', '.join(r.nombre for r in fallos)}."
        )
    else:
        mensaje = "No se encontraron multas en las jurisdicciones consultadas automáticamente."

    return {
        "patente": dominio,
        "consultado_en": datetime.now(TZ_AR).isoformat(timespec="seconds"),
        "mensaje": mensaje,
        "resultado_completo": len(fallos) == 0 and not payload.simulacro,
        "configuracion": {
            "simulacro": payload.simulacro,
            "ignorar_cache": payload.ignorar_cache,
            "captcha_clave_configurada": clave_ok,
            "captcha_proveedor": cfg_captcha.get("proveedor"),
        },
        "advertencias": advertencias,
        "resumen": {
            "cantidad_multas": n_multas,
            "jurisdicciones_con_multas": len(con_multas),
            "total_general": total,
            "total_general_formato": pesos(total),
            "por_jurisdiccion": [
                {
                    "jurisdiccion": r.nombre,
                    "multas": len(r.infracciones),
                    "subtotal": round(r.subtotal, 2),
                    "subtotal_formato": pesos(r.subtotal),
                }
                for r in con_multas
            ],
        },
        "jurisdicciones": [_serializar(r, r.nombre in desde_cache) for r in resultados],
        "sin_multas": sin_multas,
        "no_se_pudo_consultar": [
            {"jurisdiccion": r.nombre, "estado": r.estado, "motivo": r.detalle or ""} for r in fallos
        ],
    }


@app.post("/api/consultar")
async def api_consultar(payload: ConsultaRequest) -> dict[str, Any]:
    try:
        return await _ejecutar_consulta(payload)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        log.exception("Error inesperado en /api/consultar")
        raise HTTPException(status_code=500, detail="Error interno al consultar. Revisá la terminal donde corre uvicorn.")


# ----------------------------------------------------------------------------- archivos estáticos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

LOGO_CANDIDATOS = (RAIZ / "logo.png", STATIC_DIR / "logo.png")


@app.get("/logo.png")
async def get_logo():
    for ruta in LOGO_CANDIDATOS:
        if ruta.is_file():
            return FileResponse(ruta)
    raise HTTPException(status_code=404, detail="Logo no encontrado")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)  # evita el error 404 en la consola del navegador


@app.get("/")
async def index():
    html_file = STATIC_DIR / "index.html"
    if html_file.is_file():
        return FileResponse(html_file)
    return {"message": "API activa. Creá static/index.html para ver el frontend."}