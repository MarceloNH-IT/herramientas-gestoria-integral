# -*- coding: utf-8 -*-
"""
Marcelo Nuñez Gestiones | Buscador de infracciones por patente
Streamlit + HTTP directo + CapSolver.

Archivos que van juntos en el repositorio:
  GestoriaF.py            (este archivo)
  logo.png                (tu logo, al lado del .py)
  requirements.txt
  .streamlit/config.toml  (tema oscuro)

Novedades:
  * Diseño con la identidad de Marcelo Nuñez Gestiones (azul noche, dorado, Bebas Neue + DM Sans),
    con tus datos de contacto y llamado a WhatsApp con la patente y el total ya cargados.
  * Cada portal termina con un ESTADO explícito (nunca se confunde "falló" con "sin multas").
  * Serialización completa del formulario (como lo haría un navegador) y elección del botón correcto.
  * Explorador de portales: lee cada portal DESDE el servidor de Streamlit y arma un informe con
    formularios, sitekeys y URLs de API que aparecen en el JavaScript. Sirve para conectar los
    portales SPA sin abrir DevTools.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import hmac
import html
import json
import os
import random
import re
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, List
from urllib.parse import quote, urljoin
from zoneinfo import ZoneInfo

import httpx
import streamlit as st
from bs4 import BeautifulSoup

# =============================================================================
# 0. DATOS DE MARCA
# =============================================================================
WHATSAPP_NUM = "5491122533325"
WHATSAPP_TXT = "+54 9 11 2253-3325"
INSTAGRAM = "marcelonunezgestiones"
EMAIL = "marcelonunezgestiones@gmail.com"
WA_BASE = f"https://wa.me/{WHATSAPP_NUM}"

st.set_page_config(
    page_title="Marcelo Nuñez Gestiones | Buscador de infracciones",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def cargar_logo_b64() -> str:
    base = Path(__file__).resolve().parent
    for ruta in (base / "logo.png", base / "assets" / "logo.png"):
        if ruta.exists():
            return base64.b64encode(ruta.read_bytes()).decode()
    return ""


LOGO_B64 = cargar_logo_b64()

# =============================================================================
# 1. ESTILOS
# =============================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500;600;700&display=swap');
:root{
  --bg:#080e1f; --card:#111a33; --card2:#0d1530; --line:rgba(201,168,76,.24);
  --gold:#c9a84c; --gold2:#e6c56a; --txt:#e8ecf5; --mut:#93a0bd;
}
html, body, [class*="css"], .stApp, input, button, select { font-family:'DM Sans', sans-serif !important; }
.stApp{
  color:var(--txt);
  background:
    radial-gradient(1200px 600px at 15% -10%, rgba(40,60,130,.35), transparent 60%),
    linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px),
    var(--bg);
  background-size:auto, 48px 48px, 48px 48px, auto;
}
header[data-testid="stHeader"]{ background:transparent; }
[data-testid="stSidebar"], [data-testid="collapsedControl"]{ display:none; }
.block-container{ max-width:1080px; padding-top:.6rem; padding-bottom:4rem; }
#MainMenu, footer{ visibility:hidden; }
h1,h2,h3,.bebas{ font-family:'Bebas Neue', sans-serif !important; letter-spacing:.02em; font-weight:400; }

/* ---------- BARRA SUPERIOR ---------- */
.topbar{ display:flex; justify-content:space-between; align-items:center; padding:.9rem 0 1rem;
  border-bottom:1px solid rgba(255,255,255,.07); margin-bottom:1.6rem; }
.brand b{ display:block; font-size:.95rem; letter-spacing:.22em; font-weight:700; color:#fff; }
.brand span{ display:block; font-size:.62rem; letter-spacing:.22em; color:var(--gold); margin-top:2px; }
.btn{ display:inline-block; background:var(--gold); color:#0a1124 !important; font-weight:700; font-size:.86rem;
  padding:.7rem 1.2rem; border-radius:8px; text-decoration:none !important; border:1px solid var(--gold);
  box-shadow:0 8px 24px rgba(201,168,76,.18); }
.btn.ghost{ background:transparent; color:#fff !important; border:1px solid rgba(255,255,255,.18); box-shadow:none; }
.btn.sm{ padding:.5rem .95rem; font-size:.78rem; }

/* ---------- HERO ---------- */
.hero{ display:grid; grid-template-columns: 1.5fr .6fr; gap:2rem; align-items:center; margin-bottom:1.6rem; }
.hero img.logo{ width:min(430px,100%); display:block; border-radius:4px;
  box-shadow:0 0 70px rgba(201,168,76,.28); }
.logo-txt{ font-family:'Bebas Neue'; font-size:2.6rem; color:#ff9a3c; }
.contactos{ display:flex; flex-direction:column; gap:10px; margin:14px 0 18px; align-items:flex-start; }
.cchip{ display:inline-block; padding:.5rem .9rem; border-radius:8px; font-size:.85rem; font-weight:600;
  text-decoration:none !important; border:1px solid; }
.cchip.wa{ color:#4ade80 !important; border-color:rgba(74,222,128,.45); background:rgba(74,222,128,.08); }
.cchip.ig{ color:#f472b6 !important; border-color:rgba(244,114,182,.45); background:rgba(244,114,182,.08); }
.cchip.ml{ color:var(--gold2) !important; border-color:rgba(230,197,106,.45); background:rgba(230,197,106,.07); }
.tagline{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:.3rem .9rem;
  font-size:.7rem; letter-spacing:.18em; color:var(--gold); margin-bottom:.8rem; }
.hero h1{ font-size:clamp(3rem, 7vw, 5.2rem); line-height:.92; margin:.2rem 0 1rem; color:#fff; }
.hero h1 em{ color:var(--gold); font-style:normal; display:block; }
.lead{ color:#c3cce0; font-size:1rem; line-height:1.7; max-width:560px; margin-bottom:1.3rem; }
.stats{ display:flex; flex-direction:column; gap:14px; }
.stat{ background:var(--card); border:1px solid rgba(120,140,220,.22); border-radius:14px; text-align:center; padding:1rem; }
.stat b{ display:block; font-family:'Bebas Neue'; font-size:2.6rem; color:var(--gold); line-height:1; }
.stat span{ font-size:.66rem; letter-spacing:.16em; color:var(--mut); text-transform:uppercase; }

/* ---------- SECCIONES ---------- */
.sec-title{ font-family:'Bebas Neue'; font-size:2.2rem; color:#fff; margin:1.8rem 0 .2rem; }
.sec-title em{ color:var(--gold); font-style:normal; }
.sec-sub{ color:var(--mut); font-size:.9rem; margin-bottom:.9rem; }
.chips{ display:flex; flex-wrap:wrap; gap:8px; margin:.4rem 0 1rem; }
.chip{ display:inline-flex; align-items:center; gap:7px; background:var(--card2); border:1px solid rgba(255,255,255,.08);
  border-radius:999px; padding:6px 13px; font-size:.78rem; color:#d6def0; }
.chip i{ width:7px; height:7px; border-radius:50%; background:var(--gold); display:inline-block; }
.chip.man i{ background:#64748b; }

/* ---------- FORMULARIO ---------- */
[data-testid="stForm"]{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:1.2rem 1.3rem; }
[data-testid="stForm"] label p{ font-family:'Bebas Neue' !important; letter-spacing:.08em; font-size:1.25rem; color:var(--gold2); }
[data-testid="stForm"] input{ text-transform:uppercase; letter-spacing:.08em; font-weight:600; }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div{
  background:#0b1329 !important; border-radius:10px !important; }
[data-baseweb="input"], [data-baseweb="select"] > div{ border:1px solid rgba(201,168,76,.35) !important; }
input{ color:#fff !important; }
input::placeholder{ color:#6b7794 !important; text-transform:none; letter-spacing:0; font-weight:400; }
[data-baseweb="popover"] ul, [data-baseweb="menu"]{ background:#0f1830 !important; }
[data-testid="stFormSubmitButton"] button, .stButton button, .stDownloadButton button{
  background:var(--gold); color:#0a1124 !important; border:0; border-radius:10px; font-weight:700; height:3rem; }
[data-testid="stFormSubmitButton"] button:hover, .stButton button:hover, .stDownloadButton button:hover{
  filter:brightness(1.08); color:#0a1124 !important; }
[data-testid="stExpander"]{ background:var(--card); border:1px solid var(--line) !important; border-radius:12px; }
[data-testid="stExpander"] summary p{ color:var(--txt); font-weight:600; }

/* ---------- RESULTADOS ---------- */
.res-head{ background:linear-gradient(135deg, rgba(201,168,76,.14), rgba(17,26,51,.9)); border:1px solid var(--line);
  border-radius:18px; padding:1.5rem 1.6rem; margin-top:1.4rem; }
.res-head h2{ font-size:2.8rem; line-height:.95; margin:0 0 .5rem; color:#fff; }
.plate{ display:inline-block; font-family:'Bebas Neue'; font-size:1.8rem; letter-spacing:.14em; color:#0a1124;
  background:var(--gold2); border-radius:8px; padding:.15rem .9rem; margin:.3rem 0 .9rem; }
.kpis{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:.8rem; }
.kpi{ background:rgba(8,14,31,.55); border:1px solid rgba(255,255,255,.08); border-radius:12px; padding:.8rem 1rem; }
.kpi b{ display:block; font-family:'Bebas Neue'; font-size:1.9rem; color:var(--gold2); line-height:1.1; }
.kpi span{ font-size:.66rem; letter-spacing:.14em; text-transform:uppercase; color:var(--mut); }
.jchip{ display:inline-block; border-radius:999px; padding:7px 15px; font-weight:700; font-size:.76rem; margin:0 8px 8px 0;
  text-transform:uppercase; text-decoration:none !important; border:1px solid; }
.card{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:1.2rem 1.3rem; margin-top:1.1rem; }
.card h3{ font-size:1.7rem; margin:0 0 .8rem; color:#fff; display:flex; align-items:center; gap:10px; }
.card h3 i{ width:12px; height:12px; border-radius:50%; display:inline-block; }
.card h3 small{ margin-left:auto; font-family:'DM Sans'; font-size:.9rem; color:var(--gold2); font-weight:700; }
.tablewrap{ overflow-x:auto; }
table.t{ width:100%; border-collapse:collapse; font-size:.85rem; }
table.t th{ background:#0b1329; color:var(--mut); font-size:.68rem; letter-spacing:.14em; text-transform:uppercase;
  padding:.7rem; text-align:center; }
table.t td{ padding:.75rem; text-align:center; color:var(--txt); border-bottom:1px solid rgba(255,255,255,.05); }
table.t tr:nth-child(even) td{ background:rgba(255,255,255,.025); }
table.t td.l{ text-align:left; }
.tag{ display:inline-block; background:linear-gradient(135deg,#7c3aed,#5b21b6); color:#fff; font-size:.6rem; font-weight:800;
  padding:4px 10px; border-radius:999px; margin-bottom:4px; letter-spacing:.04em; }
.warn{ background:rgba(251,146,60,.1); border:1px solid rgba(251,146,60,.4); color:#fdba74; border-radius:12px;
  padding:.85rem 1rem; font-size:.9rem; margin-top:1rem; }
.ok{ background:rgba(74,222,128,.1); border:1px solid rgba(74,222,128,.4); color:#86efac; border-radius:12px;
  padding:.85rem 1rem; font-size:.92rem; margin-top:1rem; }
a.portal{ color:var(--gold2) !important; font-weight:600; text-decoration:none; }
.est{ display:inline-block; border-radius:999px; padding:3px 10px; font-size:.7rem; font-weight:800; }
.est.good{ background:rgba(74,222,128,.15); color:#86efac; }
.est.bad{ background:rgba(248,113,113,.15); color:#fca5a5; }
.est.warn{ background:rgba(251,191,36,.15); color:#fcd34d; }
.est.neutral{ background:rgba(148,163,184,.15); color:#cbd5e1; }

/* Resumen flotante */
.float{ position:fixed; top:90px; right:24px; width:250px; background:#0f1830; z-index:50; border-radius:18px;
  box-shadow:0 14px 40px rgba(0,0,0,.55); padding:1rem; border:1px solid var(--line); }
.float .h{ font-family:'Bebas Neue'; font-size:1.5rem; color:#fff; padding-bottom:.5rem; border-bottom:1px solid rgba(255,255,255,.08); }
.float .s{ font-size:.62rem; letter-spacing:.16em; color:var(--mut); font-weight:700; margin:.7rem 0 .4rem; }
.float .row{ display:flex; justify-content:space-between; align-items:center; border-radius:12px; padding:.5rem .7rem;
  margin-bottom:6px; font-weight:700; font-size:.78rem; border:1px solid; }
.float .row span.m{ text-align:right; font-weight:600; font-size:.78rem; line-height:1.1; color:#fff; }
.float .row span.m small{ display:block; color:var(--mut); font-weight:600; font-size:.62rem; }
.float .tot{ border:1px solid var(--line); border-radius:12px; text-align:center; padding:.6rem; background:#0b1329;
  font-family:'Bebas Neue'; font-size:1.7rem; color:var(--gold2); }
.float .parcial{ font-size:.62rem; color:#fdba74; font-weight:800; margin-top:.4rem; text-align:center; }
@media (max-width:1500px){ .float{ position:static; width:auto; margin-top:1rem; } }

/* ---------- PUBLICIDAD / CTA ---------- */
.cta-box{ background:linear-gradient(135deg, rgba(201,168,76,.2), rgba(17,26,51,.95)); border:1px solid var(--gold);
  border-radius:18px; padding:1.6rem; margin-top:1.4rem; text-align:center; }
.cta-box h3{ font-size:2.2rem; color:#fff; margin:0 0 .3rem; }
.cta-box p{ color:#c3cce0; margin:0 0 1rem; }
.servicios{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-top:.8rem; }
.serv{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:.9rem .6rem; text-align:center;
  font-size:.82rem; font-weight:600; color:#e8ecf5; }
.foot{ border-top:1px solid rgba(255,255,255,.07); margin-top:2.2rem; padding-top:1.2rem; color:var(--mut);
  font-size:.78rem; text-align:center; line-height:1.6; }

/* ---------- OVERLAY DE CARGA ---------- */
.ov{ position:fixed; inset:0; background:rgba(4,8,20,.7); backdrop-filter:blur(6px); z-index:9999;
  display:flex; align-items:center; justify-content:center; }
.ovc{ background:var(--card); border:1px solid var(--line); width:min(520px,90vw); border-radius:20px; padding:1.6rem 1.8rem;
  text-align:center; box-shadow:0 24px 60px rgba(0,0,0,.6); }
.ovc .spin{ width:44px; height:44px; border-radius:50%; border:4px solid rgba(255,255,255,.12); border-top-color:var(--gold);
  animation:sp 1s linear infinite; margin:0 auto .6rem; }
@keyframes sp{ to{ transform:rotate(360deg); } }
.ovc h2{ font-size:2.2rem; margin:.1rem 0; color:#fff; }
.ovc .st{ font-weight:600; color:var(--mut); font-size:.9rem; margin:.5rem 0 1rem; }
.bar{ height:10px; background:rgba(255,255,255,.08); border-radius:99px; overflow:hidden; }
.bar > div{ height:100%; background:var(--gold); border-radius:99px; transition:width .2s; }
.ovc .tip{ font-size:.72rem; color:var(--mut); margin-top:1rem; }

@media (max-width:900px){
  .hero{ grid-template-columns:1fr; } .stats{ flex-direction:row; } .stat{ flex:1; padding:.7rem .3rem; }
  .stat b{ font-size:1.8rem; } .kpis{ grid-template-columns:repeat(2,1fr); } .servicios{ grid-template-columns:repeat(2,1fr); }
  .res-head h2{ font-size:2.2rem; }
}

/* ---------- TABLAS CLARAS (una por jurisdicción, cada una con su color) ---------- */
.card .tablewrap{ background:#fff; border:1px solid #e6e1d2; border-left:8px solid var(--acc,#e6c56a);
  border-radius:14px; overflow-x:auto; }
.card table.t{ font-size:.93rem; }
.card table.t th{ background:var(--acc-soft,#f4f0e3); color:#3b4258; font-weight:700; }
.card table.t td{ color:#0b1430; border-bottom:1px solid #eee9da; }
.card table.t tbody tr:nth-child(odd) td{ background:#fff; }
.card table.t tbody tr:nth-child(even) td{ background:#faf7ee; }
.card table.t tfoot td{ background:var(--acc-soft,#f5f1e3); font-weight:800; color:#0b1430; border-bottom:0; }
.card table.t td.r{ text-align:right; }
.card .est.good{ background:#dcfce7; color:#14663a; } .card .est.bad{ background:#fee2e2; color:#991b1b; }
.card .est.warn{ background:#fef3c7; color:#92400e; } .card .est.neutral{ background:#e5e7eb; color:#374151; }
.card a.portal{ color:#1d4ed8 !important; }
.tag.pv{ background:linear-gradient(135deg,#dc2626,#991b1b); }
.btn.wa{ background:#22c55e; border-color:#22c55e; color:#04210f !important; box-shadow:0 8px 22px rgba(34,197,94,.3); }
.totalbar{ display:flex; justify-content:space-between; align-items:center; background:#0f1830; border:1px solid var(--gold);
  color:#fff; border-radius:16px; padding:1rem 1.4rem; margin-top:1.2rem; font-weight:700; letter-spacing:.06em; }
.totalbar b{ font-family:'Bebas Neue'; font-size:2.1rem; color:var(--gold2); letter-spacing:.04em; font-weight:400; }
.block-container{ padding-bottom:4rem; }

/* Resumen: junto al contenido en pantallas anchas, dentro del flujo en las demás */
.float{ position:static; width:auto; margin-top:1rem; }
@media (min-width:1640px){ .float{ position:fixed; top:90px; left:calc(50% + 556px); right:auto; width:255px; margin-top:0; } }

/* ---------- TABLERO DE SERVIDORES ---------- */
.srvhead{ display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin:1.1rem 0 .3rem; }
.srvhead b{ font-family:'Bebas Neue'; font-size:1.5rem; letter-spacing:.06em; color:#fff; font-weight:400; }
.srvhead span{ font-size:.74rem; color:var(--mut); }
.srvhead i{ display:inline-block; width:8px; height:8px; border-radius:50%; margin:0 2px 0 4px; }
.srvhead i.g{ background:#22c55e; } .srvhead i.r{ background:#ef4444; } .srvhead i.a{ background:#f59e0b; }
.servers{ display:flex; flex-wrap:wrap; gap:8px; margin:.3rem 0 1rem; }
.srv{ display:inline-flex; align-items:center; gap:8px; background:var(--card2); border:1px solid rgba(255,255,255,.1);
  border-radius:999px; padding:7px 14px; font-size:.8rem; color:#e8ecf5; font-weight:600; }
.srv i{ width:10px; height:10px; border-radius:50%; display:inline-block; background:#64748b; }
.srv.ok i{ background:#22c55e; box-shadow:0 0 0 4px rgba(34,197,94,.22); }
.srv.down i{ background:#ef4444; box-shadow:0 0 0 4px rgba(239,68,68,.22); }
.srv.warn i{ background:#f59e0b; box-shadow:0 0 0 4px rgba(245,158,11,.22); }
.srv small{ color:var(--mut); font-weight:500; }
.srv.idle{ opacity:.65; }
.nota{ font-size:.82rem; color:#8a93a8; background:rgba(255,255,255,.04); border-radius:10px; padding:.6rem .8rem; margin-top:.6rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}
TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")


def _secret(nombre: str) -> str:
    try:
        return str(st.secrets.get(nombre, "") or "")
    except Exception:  # noqa: BLE001
        return ""


# =============================================================================
# 2. MODELOS DE DATOS Y ESTADOS
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


class CaptchaError(Exception):
    """Falla del servicio de captcha (saldo, clave, timeout, rechazo)."""


class ConsultaIndeterminada(Exception):
    """El portal respondió pero no se pudo interpretar el resultado."""

    def __init__(self, msg: str, http_status: int | None = None, muestra: str = ""):
        super().__init__(msg)
        self.http_status = http_status
        self.muestra = muestra


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
    total_oficial: float | None = None   # monto total que informa el propio portal (ej. CABA)
    declaradas: int | None = None        # cantidad de infracciones que declara el portal
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
        """Si el portal informa su monto total (con descuentos vigentes), se usa ese; si no, la suma de la lista."""
        return self.total_oficial if self.total_oficial is not None else self.suma_lista


@dataclass
class JurisdiccionConfig:
    nombre: str
    proteccion: str
    url: str
    consultar: Callable[[str, "CaptchaSolver"], Awaitable[RespuestaPortal]] | None = None
    urls_chequeo: tuple = ()          # ((url, permisivo), ...) para el tablero de servidores
    consultar_pausado: Callable | None = None


# =============================================================================
# 3. CLIENTE ANTI-CAPTCHA (CapSolver / 2Captcha)
# =============================================================================
class CaptchaSolver:
    def __init__(self, provider: str = "capsolver", api_key: str = ""):
        self.provider = provider.lower().strip()
        self.api_key = api_key.strip()

    async def solve_recaptcha_v2(self, site_key: str, page_url: str, invisible: bool = False,
                                 enterprise: bool = False) -> str:
        if not self.api_key:
            raise CaptchaError("Falta la API Key del servicio de captcha (ver 'Opciones de desarrollo y Captcha').")

        async with httpx.AsyncClient(timeout=30) as client:
            if self.provider == "capsolver":
                task = {"type": "ReCaptchaV2EnterpriseTaskProxyLess" if enterprise else "ReCaptchaV2TaskProxyLess",
                        "websiteURL": page_url, "websiteKey": site_key}
                if invisible:
                    task["isInvisible"] = True
                r = await client.post("https://api.capsolver.com/createTask",
                                      json={"clientKey": self.api_key, "task": task})
                data = r.json()
                if data.get("errorId", 0) != 0:
                    raise CaptchaError(f"CapSolver: {data.get('errorCode')} - {data.get('errorDescription')}")
                task_id = data["taskId"]

                for _ in range(60):  # hasta ~2 min
                    await asyncio.sleep(2)
                    res = await client.post("https://api.capsolver.com/getTaskResult",
                                            json={"clientKey": self.api_key, "taskId": task_id})
                    rd = res.json()
                    if rd.get("errorId", 0) != 0:
                        raise CaptchaError(f"CapSolver: {rd.get('errorCode')} - {rd.get('errorDescription')}")
                    if rd.get("status") == "ready":
                        return rd["solution"]["gRecaptchaResponse"]
                    if rd.get("status") == "failed":
                        raise CaptchaError("CapSolver: la tarea falló")
            else:
                params = {"key": self.api_key, "method": "userrecaptcha", "googlekey": site_key,
                          "pageurl": page_url, "invisible": 1 if invisible else 0, "json": 1}
                if enterprise:
                    params["enterprise"] = 1
                r = await client.get("http://2captcha.com/in.php", params=params)
                data = r.json()
                if data.get("status") != 1:
                    raise CaptchaError(f"2Captcha: {data.get('request')}")
                req_id = data["request"]

                for _ in range(30):
                    await asyncio.sleep(4)
                    res = await client.get("http://2captcha.com/res.php",
                                           params={"key": self.api_key, "action": "get", "id": req_id, "json": 1})
                    rd = res.json()
                    if rd.get("status") == 1:
                        return rd["request"]
                    if rd.get("request") != "CAPCHA_NOT_READY":
                        raise CaptchaError(f"2Captcha: {rd.get('request')}")

        raise CaptchaError("Tiempo agotado esperando la solución del captcha.")

    async def solve_turnstile(self, site_key: str, page_url: str) -> str:
        """Cloudflare Turnstile (Entre Ríos / Monitoreo Vial)."""
        if not self.api_key:
            raise CaptchaError("Falta la API Key del servicio de captcha.")
        async with httpx.AsyncClient(timeout=30) as client:
            if self.provider == "capsolver":
                task = {"type": "AntiTurnstileTaskProxyLess", "websiteURL": page_url, "websiteKey": site_key}
                r = await client.post("https://api.capsolver.com/createTask",
                                      json={"clientKey": self.api_key, "task": task})
                data = r.json()
                if data.get("errorId", 0) != 0:
                    raise CaptchaError(f"CapSolver: {data.get('errorCode')} - {data.get('errorDescription')}")
                task_id = data["taskId"]
                for _ in range(60):
                    await asyncio.sleep(2)
                    res = await client.post("https://api.capsolver.com/getTaskResult",
                                            json={"clientKey": self.api_key, "taskId": task_id})
                    rd = res.json()
                    if rd.get("errorId", 0) != 0:
                        raise CaptchaError(f"CapSolver: {rd.get('errorCode')} - {rd.get('errorDescription')}")
                    if rd.get("status") == "ready":
                        return rd["solution"]["token"]
                    if rd.get("status") == "failed":
                        raise CaptchaError("CapSolver: la tarea Turnstile falló")
            else:
                params = {"key": self.api_key, "method": "turnstile", "sitekey": site_key,
                          "pageurl": page_url, "json": 1}
                r = await client.get("http://2captcha.com/in.php", params=params)
                data = r.json()
                if data.get("status") != 1:
                    raise CaptchaError(f"2Captcha: {data.get('request')}")
                req_id = data["request"]
                for _ in range(30):
                    await asyncio.sleep(4)
                    res = await client.get("http://2captcha.com/res.php",
                                           params={"key": self.api_key, "action": "get", "id": req_id, "json": 1})
                    rd = res.json()
                    if rd.get("status") == 1:
                        return rd["request"]
                    if rd.get("request") != "CAPCHA_NOT_READY":
                        raise CaptchaError(f"2Captcha: {rd.get('request')}")
        raise CaptchaError("Tiempo agotado esperando la solución de Turnstile.")


class SimulacroListo(Exception):
    """El conector llegó hasta el captcha sin resolverlo (modo simulacro: no gasta saldo)."""


class SolverSimulacro(CaptchaSolver):
    def __init__(self) -> None:
        super().__init__("simulacro", "simulacro")

    async def solve_recaptcha_v2(self, *a, **k) -> str:
        raise SimulacroListo("Llegó hasta el captcha sin resolverlo: portal, formulario y clave OK.")

    async def solve_turnstile(self, *a, **k) -> str:
        raise SimulacroListo("Llegó hasta el captcha sin resolverlo: portal, API y clave OK.")


# =============================================================================
# 4. PARSEO ROBUSTO (HTML + JSON)
# =============================================================================
RE_VACIO = re.compile(
    r"no registra|no posee|no se encontr|sin infracciones|sin deuda|libre de deuda|"
    r"no tiene (infracciones|multas|deuda|actas)|no existen|no hay (infracciones|multas|actas)|"
    r"sin resultados|0 resultados|no se hallaron",
    re.I,
)
RE_CAPTCHA_MAL = re.compile(
    r"re?captcha.{0,60}(inv[aá]lid|incorrect|error|fall|venc|expir|no (es )?v[aá]lid)|"
    r"(inv[aá]lid|incorrect|error|fall).{0,30}re?captcha|captcha (inv[aá]lido|incorrecto|expirado)|"
    r"turnstile.{0,40}(inv[aá]lid|error|fall|expir)",
    re.I,
)


def limpiar_monto(texto) -> float | None:
    if texto is None or texto == "":
        return None
    if isinstance(texto, (int, float)):
        return float(texto)
    limpio = re.sub(r"[^\d,.]", "", str(texto))
    if not re.search(r"\d", limpio):
        return None
    if "," in limpio and "." in limpio:
        if limpio.rfind(",") > limpio.rfind("."):
            limpio = limpio.replace(".", "").replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpio):
        limpio = limpio.replace(".", "")
    try:
        return float(limpio)
    except ValueError:
        return None


def _etiquetas(texto: str) -> List[str]:
    t = (texto or "").lower()
    out: List[str] = []
    if "controlador" in t:
        out.append("MULTA CON CONTROLADOR")
    if re.search(r"pago\s*voluntario", t):
        out.append("PAGO VOLUNTARIO")
    return out


def _etiquetas_json(d: dict) -> List[str]:
    """En JSON hay que mirar claves Y valores: {"pagoVoluntario": false} NO es pago voluntario."""
    out: List[str] = []
    verdadero = (True, 1, "1", "true", "True", "TRUE", "si", "Si", "SI", "S")
    for k, v in d.items():
        kl = _hoja(str(k)).lower()
        if isinstance(v, (dict, list)):
            continue
        if re.search(r"controlador", kl) and v in verdadero and "MULTA CON CONTROLADOR" not in out:
            out.append("MULTA CON CONTROLADOR")
        if re.search(r"pago_?\s*voluntario", kl) and v in verdadero and "PAGO VOLUNTARIO" not in out:
            out.append("PAGO VOLUNTARIO")
        if isinstance(v, str):
            for e in _etiquetas(v):
                if e not in out:
                    out.append(e)
    return out


def texto_visible(soup: BeautifulSoup) -> str:
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def _tabla_a_infracciones(soup: BeautifulSoup) -> List[Infraccion]:
    out: List[Infraccion] = []
    for table in soup.find_all("table"):
        idx_acta = idx_desc = idx_monto = None
        for tr in table.find_all("tr"):
            celdas = tr.find_all(["th", "td"])
            textos = [c.get_text(" ", strip=True) for c in celdas]
            if tr.find("th"):
                for i, h in enumerate(textos):
                    hl = h.lower()
                    if idx_monto is None and re.search(r"monto|importe|total|deuda|saldo|a pagar|valor", hl):
                        idx_monto = i
                    elif idx_acta is None and re.search(r"acta|n[°ºo]\b|nro|n[uú]mero|comprobante|expediente", hl):
                        idx_acta = i
                    elif idx_desc is None and re.search(r"descrip|infracci|falta|motivo|concepto|norma", hl):
                        idx_desc = i
                continue
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            cols = [td.get_text(" ", strip=True) for td in tds]
            acta = cols[idx_acta] if idx_acta is not None and idx_acta < len(cols) else cols[0]
            if not re.search(r"\d", acta):
                continue
            desc = cols[idx_desc] if idx_desc is not None and idx_desc < len(cols) else (cols[1] if len(cols) > 1 else "")
            monto = None
            if idx_monto is not None and idx_monto < len(cols):
                monto = limpiar_monto(cols[idx_monto])
            if monto is None:
                for c in reversed(cols[1:]):
                    if re.search(r"\$|\d+[.,]\d{2}\b", c):
                        monto = limpiar_monto(c)
                        if monto is not None:
                            break
            out.append(Infraccion(
                acta=acta[:30],
                descripcion=(desc or "Infracción de tránsito")[:140],
                monto=monto,
                etiquetas=_etiquetas(" ".join(cols)),
            ))
    return out


def _listas_de_dicts(obj, acc: list, vacias: list) -> None:
    if isinstance(obj, list):
        if not obj:
            vacias.append(True)
        elif all(isinstance(x, dict) for x in obj):
            acc.append(obj)
        for x in obj:
            _listas_de_dicts(x, acc, vacias)
    elif isinstance(obj, dict):
        for v in obj.values():
            _listas_de_dicts(v, acc, vacias)


def _aplanar(d: dict, prefijo: str = "", out: dict | None = None, prof: int = 0) -> dict:
    """{"cupon": {"importe": 1}} -> {"cupon.importe": 1}  (las listas internas se ignoran)."""
    out = {} if out is None else out
    for k, v in d.items():
        ruta = f"{prefijo}.{k}" if prefijo else str(k)
        if isinstance(v, dict) and prof < 3:
            _aplanar(v, ruta, out, prof + 1)
        elif not isinstance(v, (dict, list)):
            out[ruta] = v
    return out


RE_ACTA_VALOR = re.compile(r"^\d{2}-\d{3}-\d{5,9}-\d(?:-\d{1,2})?$")  # 02-032-00124409-2 (PBA)
_PRIO_ACTA = [r"n(ro|um|umero|úmero)?_?acta|acta_?n(ro|um|umero)", r"acta", r"comprobante|expediente|boleta|causa"]
_PRIO_MONTO = [r"^importe$|importe_?(total|actual|vigente|a_?pagar)$", r"importe", r"monto", r"deuda|saldo", r"valor", r"^total$"]
_RE_NO_MONTO = re.compile(r"cant|count|nro|num|id$|cuota|dias|d[ií]as|puntos|estado", re.I)
_PRIO_DESC = [r"descrip", r"infracci", r"detalle", r"norma|articulo|falta|motivo|concepto"]


def _hoja(ruta: str) -> str:
    return ruta.split(".")[-1]


def _es_fecha_epoch(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 9e11 < float(v) < 5e12


def _fmt_fecha(v) -> str:
    try:
        if _es_fecha_epoch(v):
            ms = float(v)
            if ms % 86_400_000 == 0:  # medianoche UTC: es una fecha "pura", no se corre un día por la zona horaria
                return datetime.utcfromtimestamp(ms / 1000).strftime("%d/%m/%Y")
            return datetime.fromtimestamp(ms / 1000, TZ_AR).strftime("%d/%m/%Y")
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v))
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    except (ValueError, OverflowError, OSError):
        pass
    return str(v)


def _extraer_infraccion(d: dict) -> Infraccion | None:
    plano = _aplanar(d)
    # --- acta: primero por FORMA del valor (02-032-00124409-2), después por nombre de campo
    acta = next((str(v) for v in plano.values() if isinstance(v, str) and RE_ACTA_VALOR.match(v.strip())), None)
    if acta is None:
        for patron in _PRIO_ACTA:
            cand = [(k, v) for k, v in plano.items()
                    if re.search(patron, _hoja(k), re.I) and v not in (None, "") and not isinstance(v, bool)]
            cand.sort(key=lambda kv: isinstance(kv[1], str), reverse=True)  # prefiere texto a números
            if cand:
                acta = str(cand[0][1])
                break
    if acta is None:
        return None
    # --- monto: por prioridad de nombre (importe > monto > deuda…), ignorando contadores/ids/estados
    monto = None
    for patron in _PRIO_MONTO:
        for k, v in plano.items():
            h = _hoja(k)
            if re.search(patron, h, re.I) and not _RE_NO_MONTO.search(h) and not isinstance(v, bool):
                m = limpiar_monto(v)
                if m is not None and m > 0:
                    monto = m
                    break
        if monto is not None:
            break
    if monto is None:
        return None
    # --- descripción: texto real (no números ni fechas); si no hay, se arma con estados y vencimiento
    desc = None
    for patron in _PRIO_DESC:
        for k, v in plano.items():
            if (re.search(patron, _hoja(k), re.I) and isinstance(v, str) and len(v.strip()) > 3
                    and not re.fullmatch(r"[\d\s./:-]+", v.strip())):
                desc = v.strip()
                break
        if desc:
            break
    if not desc:
        partes = []
        for etiqueta, patron in (("Causa", r"estado_?causa|causa_?estado"), ("Cupón", r"estado_?cup|cup[oó]n_?estado"),
                                 ("Vence", r"vencim|vto")):
            for k, v in plano.items():
                if re.search(patron, k.replace(".", "_"), re.I) and v not in (None, ""):
                    partes.append(f"{etiqueta}: {_fmt_fecha(v