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
  * Resumen en JSON (con descarga) con el mismo orden que el panel de resumen.
  * Explorador de portales: lee cada portal DESDE el servidor de Streamlit y arma un informe con
    formularios, sitekeys y URLs de API que aparecen en el JavaScript. Sirve para conectar los
    portales SPA sin abrir DevTools.
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import html
import json
import os
import random
import re
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
  --bg:#f5f3ec; --ink:#0b1430; --navy:#0b1430; --navy2:#17245a; --gold:#c9a84c; --gold2:#e6c56a;
  --golddk:#8a6d1f; --card:#ffffff; --line:#e6e1d2; --mut:#5b6478;
}
html, body, [class*="css"], .stApp, input, button, select { font-family:'DM Sans', sans-serif !important; }
.stApp{ color:var(--ink);
  background: radial-gradient(900px 420px at 88% -4%, rgba(201,168,76,.18), transparent 60%), var(--bg); }
header[data-testid="stHeader"]{ background:transparent; }
[data-testid="stSidebar"], [data-testid="collapsedControl"]{ display:none; }
.block-container{ max-width:1080px; padding-top:.6rem; padding-bottom:7rem; }
#MainMenu, footer{ visibility:hidden; }
h1,h2,h3{ font-family:'Bebas Neue', sans-serif !important; letter-spacing:.02em; font-weight:400; }

/* ---------- BARRA SUPERIOR ---------- */
.topbar{ display:flex; justify-content:space-between; align-items:center; padding:.8rem 0 1rem;
  border-bottom:1px solid var(--line); margin-bottom:1.3rem; }
.brand b{ display:block; font-size:.95rem; letter-spacing:.22em; font-weight:700; color:var(--navy); }
.brand span{ display:block; font-size:.62rem; letter-spacing:.22em; color:var(--golddk); margin-top:2px; font-weight:600; }
.btn{ display:inline-block; background:var(--gold); color:#0a1124 !important; font-weight:700; font-size:.88rem;
  padding:.72rem 1.25rem; border-radius:10px; text-decoration:none !important; border:1px solid var(--gold);
  box-shadow:0 8px 22px rgba(201,168,76,.25); }
.btn.ghost{ background:transparent; color:#fff !important; border:1px solid rgba(255,255,255,.35); box-shadow:none; }
.btn.wa{ background:#22c55e; border-color:#22c55e; color:#04210f !important; box-shadow:0 8px 22px rgba(34,197,94,.3); }
.btn.sm{ padding:.5rem .95rem; font-size:.78rem; }

/* ---------- HERO (bloque de marca) ---------- */
.hero{ display:grid; grid-template-columns:1.5fr .6fr; gap:2rem; align-items:center; margin-bottom:1.4rem;
  background:linear-gradient(135deg,#0b1430 0%,#17245a 100%); border-radius:24px; padding:2rem;
  box-shadow:0 22px 50px rgba(11,20,48,.22); color:#fff; }
.hero img.logo{ width:min(420px,100%); display:block; border-radius:6px; box-shadow:0 0 60px rgba(201,168,76,.3); }
.logo-txt{ font-family:'Bebas Neue'; font-size:2.6rem; color:#ff9a3c; }
.contactos{ display:flex; flex-direction:column; gap:10px; margin:14px 0 18px; align-items:flex-start; }
.cchip{ display:inline-block; padding:.5rem .9rem; border-radius:10px; font-size:.86rem; font-weight:600;
  text-decoration:none !important; border:1px solid; }
.cchip.wa{ color:#157a3c !important; border-color:rgba(21,122,60,.4); background:rgba(21,122,60,.08); }
.cchip.ig{ color:#b02a73 !important; border-color:rgba(176,42,115,.4); background:rgba(176,42,115,.07); }
.cchip.ml{ color:var(--golddk) !important; border-color:rgba(138,109,31,.45); background:rgba(201,168,76,.12); }
.hero .cchip.wa{ color:#4ade80 !important; border-color:rgba(74,222,128,.5); background:rgba(74,222,128,.1); }
.hero .cchip.ig{ color:#f9a8d4 !important; border-color:rgba(244,114,182,.5); background:rgba(244,114,182,.1); }
.hero .cchip.ml{ color:var(--gold2) !important; border-color:rgba(230,197,106,.5); background:rgba(230,197,106,.1); }
.tagline{ display:inline-block; border:1px solid rgba(201,168,76,.45); border-radius:999px; padding:.3rem .9rem;
  font-size:.7rem; letter-spacing:.18em; color:var(--gold2); margin-bottom:.8rem; }
.hero h1{ font-size:clamp(3rem, 7vw, 5rem); line-height:.92; margin:.2rem 0 1rem; color:#fff; }
.hero h1 em{ color:var(--gold2); font-style:normal; display:block; }
.lead{ color:#c9d2ea; font-size:1rem; line-height:1.7; max-width:560px; margin-bottom:1.3rem; }
.stats{ display:flex; flex-direction:column; gap:14px; }
.stat{ background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14); border-radius:14px; text-align:center; padding:1rem; }
.stat b{ display:block; font-family:'Bebas Neue'; font-size:2.6rem; color:var(--gold2); line-height:1; }
.stat span{ font-size:.66rem; letter-spacing:.16em; color:#9fb0d6; text-transform:uppercase; }

/* ---------- SECCIONES ---------- */
.sec-title{ font-family:'Bebas Neue'; font-size:2.3rem; color:var(--navy); margin:1.6rem 0 .1rem; }
.sec-title em{ color:var(--golddk); font-style:normal; }
.sec-sub{ color:var(--mut); font-size:.95rem; margin-bottom:.9rem; }

/* ---------- FORMULARIO ---------- */
[data-testid="stForm"]{ background:#fff; border:1px solid var(--line); border-radius:18px; padding:1.3rem 1.4rem;
  box-shadow:0 10px 30px rgba(11,20,48,.07); }
[data-testid="stForm"] label p{ font-weight:700; font-size:1rem; color:var(--navy); }
[data-testid="stForm"] input{ text-transform:uppercase; letter-spacing:.08em; font-weight:700; font-size:1.05rem; }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div{ background:#fff !important; border-radius:12px !important; }
[data-baseweb="input"], [data-baseweb="select"] > div{ border:1.5px solid #cfc7b0 !important; }
[data-baseweb="input"]:focus-within{ border-color:var(--gold) !important; box-shadow:0 0 0 3px rgba(201,168,76,.25); }
input{ color:var(--navy) !important; }
input::placeholder{ color:#8b93a7 !important; text-transform:none; letter-spacing:0; font-weight:400; }
[data-testid="stFormSubmitButton"] button, .stButton button, .stDownloadButton button{
  background:var(--gold); color:#0a1124 !important; border:0; border-radius:12px; font-weight:700; height:3rem; }
[data-testid="stFormSubmitButton"] button:hover, .stButton button:hover, .stDownloadButton button:hover{
  filter:brightness(1.06); color:#0a1124 !important; }
[data-testid="stExpander"]{ background:#fff; border:1px solid var(--line) !important; border-radius:14px; }
[data-testid="stExpander"] summary p{ font-weight:600; color:var(--navy); }

/* ---------- RESULTADOS ---------- */
.res-head{ background:linear-gradient(135deg,#fff6d8,#fffdf5); border:1px solid #ecd98f; border-radius:20px;
  padding:1.5rem 1.6rem; margin-top:1.4rem; }
.res-head h2{ font-size:2.8rem; line-height:.95; margin:0 0 .5rem; color:var(--navy); }
.plate{ display:inline-block; font-family:'Bebas Neue'; font-size:1.9rem; letter-spacing:.14em; color:var(--gold2);
  background:var(--navy); border-radius:10px; padding:.15rem 1rem; margin:.3rem 0 .9rem; }
.kpis{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:.8rem; }
.kpi{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:.8rem 1rem; }
.kpi b{ display:block; font-family:'Bebas Neue'; font-size:1.9rem; color:var(--navy); line-height:1.1; }
.kpi span{ font-size:.68rem; letter-spacing:.14em; text-transform:uppercase; color:var(--mut); font-weight:600; }
.jchip{ display:inline-block; border-radius:999px; padding:8px 16px; font-weight:700; font-size:.78rem; margin:0 8px 8px 0;
  text-transform:uppercase; text-decoration:none !important; border:1px solid; }
.card{ background:#fff; border:1px solid var(--line); border-radius:20px; padding:1.3rem 1.4rem; margin-top:1.2rem;
  box-shadow:0 10px 28px rgba(11,20,48,.06); }
.card h3{ font-size:1.8rem; margin:0 0 .9rem; color:var(--navy); display:flex; align-items:center; gap:10px; }
.card h3 i{ width:13px; height:13px; border-radius:50%; display:inline-block; }
.card h3 small{ margin-left:auto; font-family:'DM Sans'; font-size:.95rem; color:var(--golddk); font-weight:700; }
.tablewrap{ overflow-x:auto; border-radius:14px; border:1px solid var(--line); }
table.t{ width:100%; border-collapse:collapse; font-size:.93rem; }
table.t th{ background:#f1ede0; color:var(--mut); font-size:.7rem; letter-spacing:.14em; text-transform:uppercase;
  padding:.85rem; text-align:center; font-weight:700; }
table.t td{ padding:.9rem .8rem; text-align:center; color:var(--ink); border-bottom:1px solid #eee9da; }
table.t tbody tr:nth-child(odd) td{ background:#fbf8ee; }
table.t td.l{ text-align:left; }
table.t td.r{ text-align:right; }
table.t tfoot td{ background:#f5f1e3; font-weight:800; border-bottom:0; color:var(--navy); }
.tag.pv{ background:linear-gradient(135deg,#dc2626,#991b1b); }
.tag{ display:inline-block; background:linear-gradient(135deg,#7c3aed,#5b21b6); color:#fff; font-size:.62rem; font-weight:800;
  padding:4px 10px; border-radius:999px; margin-bottom:4px; letter-spacing:.04em; }
.totalbar{ display:flex; justify-content:space-between; align-items:center; background:var(--navy); color:#fff;
  border-radius:16px; padding:1rem 1.4rem; margin-top:1.2rem; font-weight:700; letter-spacing:.06em; }
.totalbar b{ font-family:'Bebas Neue'; font-size:2.1rem; color:var(--gold2); letter-spacing:.04em; font-weight:400; }
.warn{ background:#fff4e5; border:1px solid #f3c892; color:#8a4b0a; border-radius:14px; padding:.9rem 1.1rem;
  font-size:.92rem; margin-top:1rem; }
.ok{ background:#e9f8ee; border:1px solid #a9dfbb; color:#14663a; border-radius:14px; padding:.9rem 1.1rem;
  font-size:.95rem; margin-top:1rem; }
a.portal{ color:#1d4ed8 !important; font-weight:600; text-decoration:none; }
.est{ display:inline-block; border-radius:999px; padding:3px 10px; font-size:.72rem; font-weight:800; }
.est.good{ background:#dcfce7; color:#14663a; } .est.bad{ background:#fee2e2; color:#991b1b; }
.est.warn{ background:#fef3c7; color:#92400e; } .est.neutral{ background:#e5e7eb; color:#374151; }

/* Resumen flotante */
.float{ position:fixed; top:90px; right:24px; width:255px; background:#fff; z-index:50; border-radius:20px;
  box-shadow:0 16px 44px rgba(11,20,48,.2); padding:1rem; border:1px solid var(--line); }
.float .h{ font-family:'Bebas Neue'; font-size:1.6rem; color:var(--navy); padding-bottom:.4rem; border-bottom:1px solid var(--line); }
.float .s{ font-size:.64rem; letter-spacing:.16em; color:var(--mut); font-weight:800; margin:.7rem 0 .4rem; }
.float .row{ display:flex; justify-content:space-between; align-items:center; border-radius:14px; padding:.5rem .75rem;
  margin-bottom:6px; font-weight:800; font-size:.8rem; border:1px solid; }
.float .row span.m{ text-align:right; font-weight:700; font-size:.82rem; line-height:1.1; color:var(--navy); }
.float .row span.m small{ display:block; color:var(--mut); font-weight:700; font-size:.64rem; }
.float .tot{ border:1px solid #ecd98f; border-radius:14px; text-align:center; padding:.6rem; background:#fffaf0;
  font-family:'Bebas Neue'; font-size:1.8rem; color:var(--navy); }
.float .parcial{ font-size:.64rem; color:#8a4b0a; font-weight:800; margin-top:.4rem; text-align:center; }
@media (max-width:1500px){ .float{ position:static; width:auto; margin-top:1rem; } }

/* ---------- LLAMADO A LA ACCIÓN ---------- */
.cta-box{ background:linear-gradient(135deg,#0b1430,#17245a); border-radius:20px; padding:1.7rem; margin-top:1.3rem;
  text-align:center; box-shadow:0 18px 44px rgba(11,20,48,.22); }
.cta-box h3{ font-size:2.3rem; color:#fff; margin:0 0 .3rem; }
.cta-box p{ color:#c9d2ea; margin:0 0 1rem; }
.sticky-wa{ position:fixed; left:0; right:0; bottom:0; z-index:60; background:#0b1430; color:#fff;
  padding:.8rem 1.4rem; display:flex; justify-content:space-between; align-items:center; gap:1rem;
  box-shadow:0 -10px 30px rgba(0,0,0,.25); font-weight:600; }
.servicios{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-top:.8rem; }
.serv{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:1rem .6rem; text-align:center;
  font-size:.86rem; font-weight:700; color:var(--navy); }
.foot{ border-top:1px solid var(--line); margin-top:2.2rem; padding-top:1.2rem; color:var(--mut);
  font-size:.8rem; text-align:center; line-height:1.6; }

/* ---------- OVERLAY DE CARGA ---------- */
.ov{ position:fixed; inset:0; background:rgba(245,243,236,.78); backdrop-filter:blur(6px); z-index:9999;
  display:flex; align-items:center; justify-content:center; }
.ovc{ background:#fff; border:1px solid var(--line); width:min(520px,90vw); border-radius:24px; padding:1.7rem 1.9rem;
  text-align:center; box-shadow:0 24px 60px rgba(11,20,48,.2); }
.ovc .spin{ width:46px; height:46px; border-radius:50%; border:4px solid #ece7d6; border-top-color:var(--gold);
  animation:sp 1s linear infinite; margin:0 auto .6rem; }
@keyframes sp{ to{ transform:rotate(360deg); } }
.ovc h2{ font-size:2.2rem; margin:.1rem 0; color:var(--navy); }
.ovc .st{ font-weight:700; color:var(--mut); font-size:.92rem; margin:.5rem 0 1rem; }
.bar{ height:10px; background:#ece7d6; border-radius:99px; overflow:hidden; }
.bar > div{ height:100%; background:var(--gold); border-radius:99px; transition:width .2s; }
.ovc .tip{ font-size:.74rem; color:var(--mut); margin-top:1rem; }

@media (max-width:900px){
  .hero{ grid-template-columns:1fr; padding:1.3rem; } .stats{ flex-direction:row; } .stat{ flex:1; padding:.7rem .3rem; }
  .stat b{ font-size:1.8rem; } .kpis{ grid-template-columns:repeat(2,1fr); } .servicios{ grid-template-columns:repeat(2,1fr); }
  .res-head h2{ font-size:2.2rem; } .sticky-wa{ flex-direction:column; text-align:center; gap:.5rem; padding:.6rem; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}
TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")


# =============================================================================
# 2. MODELOS DE DATOS Y ESTADOS
# =============================================================================
ESTADOS_OK = ("con_multas", "sin_multas")
ESTADOS_FALLO = ("error", "captcha_fallido", "indeterminado")

ESTADO_UI = {
    "con_multas": ("Con multas", "good"),
    "sin_multas": ("Sin multas", "good"),
    "error": ("Error de conexión", "bad"),
    "captcha_fallido": ("Captcha falló", "bad"),
    "indeterminado": ("No se pudo leer", "warn"),
    "sin_conector": ("Consulta manual", "neutral"),
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

    @property
    def conectado(self) -> bool:
        return self.estado in ESTADOS_OK

    @property
    def subtotal(self) -> float:
        return sum(i.monto or 0 for i in self.infracciones)


@dataclass
class JurisdiccionConfig:
    nombre: str
    proteccion: str
    url: str
    consultar: Callable[[str, "CaptchaSolver"], Awaitable[RespuestaPortal]] | None = None


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
        kl = str(k).lower()
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


def _val(d: dict, patron: str):
    for k, v in d.items():
        if re.search(patron, str(k), re.I) and v not in (None, "") and not isinstance(v, (dict, list)):
            return v
    return None


def _json_a_infracciones(data) -> tuple[List[Infraccion], bool]:
    listas: list = []
    vacias: list = []
    _listas_de_dicts(data, listas, vacias)
    out: List[Infraccion] = []
    for lista in listas:
        for d in lista:
            acta = _val(d, r"acta|nro|numero|n[uú]m|comprobante|expediente|causa|boleta|^id$")
            monto = _val(d, r"monto|importe|total|deuda|saldo|valor|precio|pagar")
            desc = _val(d, r"descrip|infracci|falta|motivo|concepto")
            if acta is None or monto is None:
                continue
            out.append(Infraccion(
                acta=str(acta)[:30],
                descripcion=str(desc or "Infracción de tránsito")[:140],
                monto=limpiar_monto(monto),
                etiquetas=_etiquetas_json(d),
            ))
    return out, bool(vacias)


RE_ACTA_TEXTO = re.compile(
    r"Acta\s*N[°º]?\s*([A-Z]?\d[A-Z0-9-]*)\s*[-–]\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})(?:\s+\d{2}:\d{2})?\s*(.*?)\s*(\$\s*[\d.,]+)",
    re.I | re.S,
)


def _actas_en_texto(texto: str) -> List[Infraccion]:
    """Portales que no usan <table>: 'Acta N°Q123 - 2022-07-02 22:59  Descripción  $21.999,00'."""
    out: List[Infraccion] = []
    for m in RE_ACTA_TEXTO.finditer(texto):
        desc = re.sub(r"\s+", " ", re.sub(r"(?i)pago\s*voluntario", "", m.group(3))).strip(" -–")
        out.append(Infraccion(
            acta=m.group(1)[:30],
            descripcion=(desc or "Infracción de tránsito")[:140],
            monto=limpiar_monto(m.group(4)),
            etiquetas=_etiquetas(m.group(0)),
        ))
    return out


def _dedup(items: List[Infraccion]) -> List[Infraccion]:
    vistos, res = set(), []
    for i in items:
        k = (i.acta, i.monto)
        if k not in vistos:
            vistos.add(k)
            res.append(i)
    return res


def interpretar_respuesta(resp: httpx.Response) -> RespuestaPortal:
    """Convierte la respuesta HTTP en infracciones o lanza un error EXPLÍCITO."""
    ctype = resp.headers.get("content-type", "").lower()
    cuerpo = resp.text or ""
    muestra = re.sub(r"\s+", " ", cuerpo)[:800]

    if resp.status_code >= 400:
        if RE_CAPTCHA_MAL.search(cuerpo):
            raise CaptchaError("El portal rechazó el token del captcha")
        extra = " (posible bloqueo por IP extranjera / WAF)" if resp.status_code in (403, 429) else ""
        raise ConsultaIndeterminada(f"HTTP {resp.status_code}{extra}", resp.status_code, muestra)

    if "json" in ctype or cuerpo.lstrip().startswith(("{", "[")):
        try:
            data = resp.json()
        except ValueError:
            data = None
        if data is not None:
            items, hay_lista_vacia = _json_a_infracciones(data)
            if items:
                return RespuestaPortal(_dedup(items), resp.status_code, muestra)
            if RE_CAPTCHA_MAL.search(cuerpo):
                raise CaptchaError("El portal rechazó el token del captcha")
            if hay_lista_vacia or RE_VACIO.search(cuerpo):
                return RespuestaPortal([], resp.status_code, muestra)
            raise ConsultaIndeterminada("JSON sin estructura de infracciones reconocible", resp.status_code, muestra)

    items = _tabla_a_infracciones(BeautifulSoup(cuerpo, "html.parser"))
    if items:
        return RespuestaPortal(_dedup(items), resp.status_code, muestra)

    visible = texto_visible(BeautifulSoup(cuerpo, "html.parser"))
    muestra = visible[:800] or muestra
    items = _actas_en_texto(visible)
    if items:
        return RespuestaPortal(_dedup(items), resp.status_code, muestra)
    if RE_CAPTCHA_MAL.search(visible):
        raise CaptchaError("El portal rechazó el token del captcha")
    if RE_VACIO.search(visible):
        return RespuestaPortal([], resp.status_code, muestra)
    raise ConsultaIndeterminada(
        "Respuesta sin tabla de infracciones ni mensaje de 'sin infracciones' (¿cambió el portal?)",
        resp.status_code, muestra,
    )


# =============================================================================
# 5. CONECTORES HTTP
# =============================================================================
def nuevo_cliente(timeout: int = 40) -> httpx.AsyncClient:
    return httpx.AsyncClient(verify=False, follow_redirects=True, timeout=timeout, headers=HEADERS_HTTP)


RE_CAMPO_PATENTE = re.compile(r"domin|patent|vehic|plac", re.I)
RE_SITEKEY = [
    r'data-sitekey=["\']([0-9A-Za-z_-]{40})["\']',
    r'sitekey["\']?\s*[:=]\s*["\']([0-9A-Za-z_-]{40})["\']',
    r'recaptcha/(?:api|enterprise)\.js\?[^"\']*render=([0-9A-Za-z_-]{40})',
    r'[?&]k=([0-9A-Za-z_-]{40})',
    r'["\'](6L[0-9A-Za-z_-]{38})["\']',
]

# Si conocés el sitekey de algún portal, cargalo acá: {"fragmento_de_url": "6Lxxxx..."}
SITEKEYS_CONOCIDAS: dict[str, str] = {}


def _buscar_sitekey_en_texto(texto: str) -> str | None:
    for p in RE_SITEKEY:
        m = re.search(p, texto)
        if m:
            return m.group(1)
    return None


async def buscar_sitekey(client: httpx.AsyncClient, url: str, html_text: str) -> str | None:
    for dominio, key in SITEKEYS_CONOCIDAS.items():
        if dominio in url:
            return key
    key = _buscar_sitekey_en_texto(html_text)
    if key:
        return key
    soup = BeautifulSoup(html_text, "html.parser")
    scripts = [urljoin(url, s["src"]) for s in soup.find_all("script", src=True)]
    scripts = [s for s in scripts if "google.com" not in s and "gstatic.com" not in s][:8]
    for s in scripts:
        try:
            r = await client.get(s)
            key = _buscar_sitekey_en_texto(r.text)
            if key:
                return key
        except httpx.HTTPError:
            continue
    return None


def _es_input_texto(tag) -> bool:
    return tag.name == "input" and (tag.get("type") or "text").lower() in ("text", "search")


def serializar_form(scope) -> dict:
    """Serializa TODO el formulario como lo haría un navegador (hidden, texto, select, checks)."""
    datos: dict = {}
    for el in scope.find_all(["input", "select", "textarea"]):
        nombre = el.get("name")
        if not nombre:
            continue
        if el.name == "input":
            t = (el.get("type") or "text").lower()
            if t in ("submit", "button", "image", "reset", "file"):
                continue
            if t in ("checkbox", "radio"):
                if el.has_attr("checked"):
                    datos[nombre] = el.get("value", "on")
                continue
            datos[nombre] = el.get("value", "")
        elif el.name == "select":
            opt = el.find("option", selected=True) or el.find("option")
            datos[nombre] = (opt.get("value", opt.get_text(strip=True)) if opt else "")
        else:
            datos[nombre] = el.get_text()
    return datos


def _elegir_boton(scope):
    botones = scope.find_all(
        lambda t: (t.name == "input" and (t.get("type") or "").lower() in ("submit", "image"))
        or (t.name == "button" and (t.get("type") or "submit").lower() == "submit")
    )
    if not botones:
        return None

    def afinidad(b) -> int:
        txt = (str(b.get("name", "")) + str(b.get("id", "")) + str(b.get("value", "")) + b.get_text()).lower()
        if re.search(r"domin|patent", txt):
            return 2
        if re.search(r"dni|cuit|cuil|direcc|document|causa|limpiar|volver", txt):
            return 0
        return 1

    return max(botones, key=afinidad)


def preparar_form(soup: BeautifulSoup, base_url: str, patente: str):
    """Devuelve (metodo, url_destino, datos) del formulario que contiene el campo patente."""
    campos = soup.find_all(_es_input_texto)
    campo = next((c for c in campos if RE_CAMPO_PATENTE.search((c.get("name") or "") + " " + (c.get("id") or ""))), None)
    campo = campo or (campos[0] if campos else None)
    if campo is None or not campo.get("name"):
        raise ConsultaIndeterminada(
            "No hay formulario con campo de patente en el HTML (portal SPA/JS: requiere conocer su API)."
        )
    form = campo.find_parent("form")
    scope = form or soup
    datos = serializar_form(scope)
    datos[campo["name"]] = patente
    btn = _elegir_boton(scope)
    if btn is not None and btn.get("name"):
        if (btn.get("type") or "").lower() == "image":
            datos[btn["name"] + ".x"] = "1"
            datos[btn["name"] + ".y"] = "1"
        else:
            datos[btn["name"]] = btn.get("value", "") or "Consultar"
    metodo = ((form.get("method") if form else None) or "post").lower()
    destino = urljoin(base_url, form["action"]) if (form and form.get("action")) else base_url
    return metodo, destino, datos


async def http_formulario(url: str, patente: str, solver: CaptchaSolver | None = None,
                          invisible: bool = False) -> RespuestaPortal:
    """Conector genérico: GET del formulario → (captcha) → envío → interpretación."""
    async with nuevo_cliente(45) as client:
        r_get = await client.get(url)
        if r_get.status_code >= 400:
            interpretar_respuesta(r_get)
        soup = BeautifulSoup(r_get.text, "html.parser")
        metodo, destino, datos = preparar_form(soup, str(r_get.url), patente)  # valida ANTES de gastar captcha

        if solver is not None:
            sitekey = await buscar_sitekey(client, str(r_get.url), r_get.text)
            if not sitekey:
                raise ConsultaIndeterminada("No se encontró el sitekey de reCAPTCHA en el portal.",
                                            r_get.status_code, re.sub(r"\s+", " ", r_get.text)[:400])
            token = await solver.solve_recaptcha_v2(sitekey, str(r_get.url), invisible=invisible)
            datos["g-recaptcha-response"] = token

        if metodo == "get":
            r_post = await client.get(destino, params=datos)
        else:
            r_post = await client.post(destino, data=datos, headers={"Referer": str(r_get.url)})
        return interpretar_respuesta(r_post)


# =============================================================================
# 5a. CONECTORES ESPECÍFICOS (armados con las llamadas reales de cada portal)
# =============================================================================
from urllib.parse import urlparse  # noqa: E402

RE_TURNSTILE = re.compile(r"\b(0x4[0-9A-Za-z_-]{18,60})\b")
RE_API_MONITOREO = re.compile(r"https://api\.monitoreovial[a-z]+\.[a-z]+/api/v\d+/[0-9a-f]{12,32}")
API_ENTRE_RIOS = "https://api.monitoreovialentrerios.ar/api/v3/69fa0e115c1082b8"
URL_AVELLANEDA_API = "https://siac.mda.gob.ar/api/externo/consultar"


def _clave_config(nombre: str) -> str:
    """Claves opcionales en Secrets (p. ej. SITEKEY_PBA) por si un portal cambia."""
    return _secret(nombre) or os.getenv(nombre, "")


async def descargar_textos_sitio(client: httpx.AsyncClient, url: str, html_text: str,
                                 max_scripts: int = 10, max_chunks: int = 8) -> list[str]:
    textos = [html_text]
    soup = BeautifulSoup(html_text, "html.parser")
    scripts = [urljoin(url, s["src"]) for s in soup.find_all("script", src=True)]
    scripts = [s for s in scripts if not RE_LIBS.search(s)][:max_scripts]
    vistos = set(scripts)
    cuerpos: list[tuple[str, str]] = []
    for sc in scripts:
        try:
            rs = await client.get(sc)
            if rs.status_code == 200:
                cuerpos.append((sc, rs.text[:3_000_000]))
        except httpx.HTTPError:
            continue
    chunks: list[str] = []
    for sc, t in cuerpos:
        for m in re.findall(r'["\']([\w\-./]{3,80}\.js)["\']', t):
            if m.startswith("http") or "node_modules" in m:
                continue
            u = urljoin(sc, m)
            if u not in vistos and u not in chunks and not RE_LIBS.search(u):
                chunks.append(u)
    textos += [t for _, t in cuerpos]
    for u in chunks[:max_chunks]:
        try:
            rs = await client.get(u)
            if rs.status_code == 200:
                textos.append(rs.text[:3_000_000])
        except httpx.HTTPError:
            continue
    return textos


async def obtener_sitekey(client: httpx.AsyncClient, r0: httpx.Response, config: str) -> str | None:
    key = _clave_config(config)
    if key:
        return key
    key = _buscar_sitekey_en_texto(r0.text)
    if key:
        return key
    for t in await descargar_textos_sitio(client, str(r0.url), r0.text):
        key = _buscar_sitekey_en_texto(t)
        if key:
            return key
    return None


async def _con_recaptcha(solver: CaptchaSolver, key: str, page_url: str, invisible: bool, enviar) -> RespuestaPortal:
    """Resuelve reCAPTCHA v2 y envía. Si el portal rechaza el token, reintenta UNA vez como Enterprise."""
    token = await solver.solve_recaptcha_v2(key, page_url, invisible=invisible)
    try:
        return await enviar(token)
    except CaptchaError as exc:
        if "rechaz" not in str(exc):
            raise
    token = await solver.solve_recaptcha_v2(key, page_url, invisible=invisible, enterprise=True)
    return await enviar(token)


async def _paginar(obtener, por_pagina: int, max_paginas: int = 5) -> RespuestaPortal:
    acumulado: List[Infraccion] = []
    vistos: set = set()
    ultima: RespuestaPortal | None = None
    for pagina in range(1, max_paginas + 1):
        try:
            resp = await obtener(pagina)
        except ConsultaIndeterminada:
            if pagina == 1:
                raise
            break  # la página siguiente no se pudo leer: nos quedamos con lo ya obtenido
        ultima = resp
        nuevos = [i for i in resp.infracciones if (i.acta, i.monto) not in vistos]
        vistos.update((i.acta, i.monto) for i in nuevos)
        acumulado += nuevos
        if len(resp.infracciones) < por_pagina or not nuevos:
            break
    assert ultima is not None
    return RespuestaPortal(acumulado, ultima.http_status, ultima.muestra)


# --- CABA: POST a index.php con reCAPTCHA, respuesta HTML -------------------------------------
async def http_caba(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    async with nuevo_cliente(60) as c:
        r0 = await c.get(URL_CABA)
        if r0.status_code >= 400:
            interpretar_respuesta(r0)
        key = await obtener_sitekey(c, r0, "SITEKEY_CABA")
        if not key:
            raise ConsultaIndeterminada("No se encontró el sitekey de reCAPTCHA en el portal de CABA.",
                                        r0.status_code, re.sub(r"\s+", " ", r0.text)[:400])
        destino = urljoin(str(r0.url), "index.php")

        async def enviar(token: str) -> RespuestaPortal:
            datos = {"tipo_consulta": "Dominio", "tipo_doc": "DNI", "doc": "", "filtro_acta": "transito",
                     "dominio": patente.lower(), "g-recaptcha-response": token}
            r = await c.post(destino, data=datos, headers={"Origin": "https://buenosaires.gob.ar", "Referer": URL_CABA})
            return interpretar_respuesta(r)

        return await _con_recaptcha(solver, key, URL_CABA, False, enviar)


# --- PBA: API REST (JSON) con reCAPTCHA invisible, paginada ---------------------------------------
URL_PBA_API = "https://infraccionesba.gba.gob.ar/rest/consultar-infraccion"
POR_PAGINA_PBA = 10


async def http_pba(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    async with nuevo_cliente(60) as c:
        r0 = await c.get(URL_PBA)
        if r0.status_code >= 400:
            interpretar_respuesta(r0)
        key = await obtener_sitekey(c, r0, "SITEKEY_PBA")
        if not key:
            raise ConsultaIndeterminada(
                "No se encontró el sitekey de reCAPTCHA de PBA (podés cargarlo en Secrets como SITEKEY_PBA).",
                r0.status_code, re.sub(r"\s+", " ", r0.text)[:400])

        async def obtener(pagina: int) -> RespuestaPortal:
            async def enviar(token: str) -> RespuestaPortal:
                params = {"dominio": patente.lower(), "reCaptcha": token,
                          "cantPorPagina": POR_PAGINA_PBA, "paginaActual": pagina}
                r = await c.get(URL_PBA_API, params=params,
                                headers={"Accept": "application/json", "Content-Type": "application/json",
                                         "Referer": URL_PBA})
                return interpretar_respuesta(r)
            return await _con_recaptcha(solver, key, URL_PBA, True, enviar)

        return await _paginar(obtener, POR_PAGINA_PBA)


# --- Monitoreo Vial (Entre Ríos / Misiones): API con Cloudflare Turnstile ----------------------------
POR_PAGINA_MV = 15


async def http_monitoreo_vial(base_url: str, patente: str, solver: CaptchaSolver,
                              api_defecto: str | None, config_key: str) -> RespuestaPortal:
    u = urlparse(base_url)
    origen = f"{u.scheme}://{u.netloc}"
    async with nuevo_cliente(60) as c:
        r0 = await c.get(base_url)
        if r0.status_code >= 400:
            interpretar_respuesta(r0)
        todo = "\n".join(await descargar_textos_sitio(c, str(r0.url), r0.text))
        m = RE_API_MONITOREO.search(todo)
        api = m.group(0) if m else api_defecto
        if not api:
            raise ConsultaIndeterminada("No se encontró la dirección de la API de este portal en su JavaScript.")
        key = _clave_config(config_key)
        if not key:
            mk = RE_TURNSTILE.search(todo)
            key = mk.group(1) if mk else ""
        if not key:
            raise ConsultaIndeterminada(
                f"No se encontró la clave de Cloudflare Turnstile (podés cargarla en Secrets como {config_key}).")

        async def obtener(pagina: int) -> RespuestaPortal:
            token = await solver.solve_turnstile(key, base_url)
            datos = {"consulta": "1", "id": patente, "pagina": str(POR_PAGINA_MV), "page": str(pagina),
                     "cf_turnstile_token": token}
            r = await c.post(api, data=datos, headers={
                "Accept": "application/json, text/plain, */*", "Origin": origen, "Referer": base_url})
            return interpretar_respuesta(r)

        return await _paginar(obtener, POR_PAGINA_MV, max_paginas=4)


# --- Avellaneda: API JSON sin captcha -----------------------------------------------------------------
async def http_avellaneda(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    async with nuevo_cliente(40) as c:
        r = await c.post(URL_AVELLANEDA_API, json={"buscarPor": "PATENTE", "parametroBusqueda": patente.upper()},
                         headers={"Accept": "application/json, text/plain, */*",
                                  "Origin": "https://multas.mda.gob.ar", "Referer": "https://multas.mda.gob.ar/"})
        return interpretar_respuesta(r)


# =============================================================================
# 5b. EXPLORADOR DE PORTALES (diagnóstico para conectar portales SPA)
# =============================================================================
RE_URL_JS = re.compile(
    r"""["'`]((?:https?:)?//[^"'`\s<>]{6,200}|/[A-Za-z0-9_\-./]{2,120}(?:\?[^"'`\s<>]{0,80})?)["'`]"""
)
RE_PALABRAS_API = re.compile(r"api|consult|infraccion|dominio|patente|multa|acta|captcha|buscar|search|token|scoring", re.I)
RE_IGNORAR = re.compile(
    r"\.(png|jpe?g|gif|svg|css|woff2?|ttf|ico|map|webp|html)(\?|$)|w3\.org|googleapis|gstatic|schema\.org|"
    r"googletagmanager|facebook|twitter|youtube|mozilla|github|angular\.io|reactjs|npmjs|momentjs|ngsw",
    re.I,
)
RE_CONFIG_JS = re.compile(
    r"""(?:baseURL|baseUrl|apiUrl|API_URL|apiBase|apiEndpoint|backend|endpoint|serverUrl)["']?\s*[:=]\s*["'`]([^"'`]{4,200})["'`]""",
    re.I,
)
RE_LIBS = re.compile(r"google|gstatic|googletagmanager|facebook|cloudflareinsights|jquery|bootstrap|fontawesome", re.I)


async def explorar_portal(nombre: str, url: str) -> dict:
    url = url.split("#")[0]
    info: dict = {"portal": nombre, "url": url}
    try:
        async with nuevo_cliente(30) as c:
            r = await c.get(url)
            info.update(http=r.status_code, url_final=str(r.url), bytes=len(r.content),
                        content_type=r.headers.get("content-type", "")[:60])
            soup = BeautifulSoup(r.text, "html.parser")
            info["titulo"] = (soup.title.get_text(strip=True) if soup.title else "")[:120]
            info["formularios"] = [
                {
                    "method": f.get("method", "get"),
                    "action": f.get("action", ""),
                    "campos": [
                        {"name": i.get("name"), "type": i.get("type", i.name), "id": i.get("id")}
                        for i in f.find_all(["input", "select", "textarea"])
                    ][:25],
                }
                for f in soup.find_all("form")[:6]
            ]
            info["inputs_en_pagina"] = len(soup.find_all("input"))
            info["texto_inicial"] = texto_visible(BeautifulSoup(r.text, "html.parser"))[:300]

            scripts = [urljoin(str(r.url), s["src"]) for s in soup.find_all("script", src=True)]
            scripts = [s for s in scripts if not RE_LIBS.search(s)]
            info["scripts"] = scripts[:15]

            textos: list[tuple[str, str]] = [(str(r.url), r.text)]
            for s in scripts[:10]:
                try:
                    rs = await c.get(s)
                    if rs.status_code == 200:
                        textos.append((s, rs.text[:3_000_000]))
                except httpx.HTTPError:
                    continue

            # chunks (Angular/webpack): scripts que se cargan de forma diferida
            vistos = {s for s, _ in textos}
            chunks: list[str] = []
            for s, t in list(textos[1:]):
                for m in re.findall(r'["\']([\w\-./]{3,80}\.js)["\']', t):
                    if m.startswith("http") or "node_modules" in m:
                        continue
                    u = urljoin(s, m)
                    if u not in vistos and u not in chunks and not RE_LIBS.search(u):
                        chunks.append(u)
            for u in chunks[:10]:
                try:
                    rs = await c.get(u)
                    if rs.status_code == 200:
                        textos.append((u, rs.text[:3_000_000]))
                except httpx.HTTPError:
                    continue

            endpoints: list[str] = []
            sitekeys: set[str] = set()
            configs: list[str] = []
            for _, t in textos:
                for m in RE_URL_JS.findall(t):
                    if RE_PALABRAS_API.search(m) and not RE_IGNORAR.search(m) and m not in endpoints:
                        endpoints.append(m)
                for p in RE_SITEKEY:
                    for k in re.findall(p, t):
                        sitekeys.add(k)
                for m in RE_CONFIG_JS.findall(t):
                    if m not in configs:
                        configs.append(m)
            info["js_analizados"] = len(textos) - 1
            info["sitekeys"] = sorted(sitekeys)[:6]
            info["config_urls"] = configs[:20]
            info["endpoints_candidatos"] = endpoints[:60]
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


async def explorar_todos() -> dict:
    ip: dict = {}
    try:
        async with nuevo_cliente(15) as c:
            ip = (await c.get("https://ipinfo.io/json")).json()
    except Exception as exc:  # noqa: BLE001
        ip = {"error": str(exc)}
    objetivos = [(j.nombre, j.url) for j in JURISDICCIONES if j.consultar is not None]
    informes = await asyncio.gather(*(explorar_portal(n, u) for n, u in objetivos))
    return {
        "ip_de_salida": {k: ip.get(k) for k in ("ip", "country", "region", "city", "org", "error")},
        "generado": datetime.now(TZ_AR).isoformat(timespec="seconds"),
        "portales": list(informes),
    }


# =============================================================================
# 6. JURISDICCIONES Y COLORES
# =============================================================================
URL_POSADAS = "https://sistema.posadas.gov.ar/mp_sistemas/autogestion/consultarmultadominio"
URL_ROSARIO = "https://www.rosario.gob.ar/gdm/patente.do?accion=ir"
URL_LOMAS = "https://webextra.lomasdezamora.gov.ar/infracciones/ConsultaFaltasNuevoMP.aspx"
URL_PBA = "https://infraccionesba.gba.gob.ar/consulta-infraccion"
URL_CABA = "https://buenosaires.gob.ar/licenciasdeconducir/consulta-de-infracciones/?actas=transito"
URL_EZEIZA = "https://consulta-web.infratrack.com.ar/consultas.php?municipio=ezeiza"
URL_ER = "https://monitoreovialentrerios.info/"
URL_MISIONES = "https://monitoreovialmisiones.info/"
URL_LANUS = "https://tramitesweb.lanus.gob.ar/lanusdigital/mis-dominios"

JURISDICCIONES: List[JurisdiccionConfig] = [
    JurisdiccionConfig("Posadas (Misiones)", "Sin CAPTCHA", URL_POSADAS,
                       lambda p, s: http_formulario(URL_POSADAS, p)),
    JurisdiccionConfig("Rosario", "Sin CAPTCHA", URL_ROSARIO,
                       lambda p, s: http_formulario(URL_ROSARIO, p)),
    JurisdiccionConfig("Lomas de Zamora", "Sin CAPTCHA", URL_LOMAS,
                       lambda p, s: http_formulario(URL_LOMAS, p)),
    JurisdiccionConfig("PBA", "reCAPTCHA", URL_PBA, lambda p, s: http_pba(p, s)),
    JurisdiccionConfig("CABA", "reCAPTCHA", URL_CABA, lambda p, s: http_caba(p, s)),
    JurisdiccionConfig("Ezeiza", "reCAPTCHA", URL_EZEIZA,
                       lambda p, s: http_formulario(URL_EZEIZA, p, s)),
    JurisdiccionConfig("Entre Ríos", "Cloudflare Turnstile", "https://monitoreovialentrerios.info/#/consulta-infracciones",
                       lambda p, s: http_monitoreo_vial(URL_ER, p, s, API_ENTRE_RIOS, "SITEKEY_ENTRERIOS")),
    JurisdiccionConfig("Misiones", "CAPTCHA", "https://monitoreovialmisiones.info/#/",
                       lambda p, s: http_monitoreo_vial(URL_MISIONES, p, s, None, "SITEKEY_MISIONES")),
    JurisdiccionConfig("Lanús", "reCAPTCHA", URL_LANUS,
                       lambda p, s: http_formulario(URL_LANUS, p, s)),
    JurisdiccionConfig("Córdoba Caminera", "Sin CAPTCHA", "https://www.rentascordoba.gob.ar/emision/ver-y-pagar/caminera"),
    JurisdiccionConfig("Santa Fe", "CAPTCHA Texto", "https://www.santafe.gov.ar/juzgadovirtual/consultaInfraccion.do?method=BusquedaVehiculo"),
    JurisdiccionConfig("Vicente López", "Cloudflare", "https://infracciones.vicentelopez.gov.ar/causas-vecino"),
    JurisdiccionConfig("Avellaneda", "Sin CAPTCHA", "https://multas.mda.gob.ar",
                       lambda p, s: http_avellaneda(p, s)),
]

PALETA = ["#9a7412", "#1d6fb8", "#6d4bd1", "#1a8a5c", "#c8481f", "#b82a75", "#0f7c82", "#7a5f2e"]


def color_de(nombre: str) -> str:
    idx = [j.nombre for j in JURISDICCIONES].index(nombre) % len(PALETA)
    return PALETA[idx]


# =============================================================================
# 7. MOTOR DE EJECUCIÓN ASÍNCRONO
# =============================================================================
PATRON_PATENTE = re.compile(r"^([A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2}|[A-Z]\d{3}[A-Z]{3}|\d{3}[A-Z]{3})$")


def normalizar_patente(texto: str) -> str:
    return re.sub(r"[\s\-.]", "", texto or "").upper()


def pesos(valor: float | None) -> str:
    if valor is None:
        return "-"
    s = f"{valor:,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _demo_infracciones(patente: str, nombre: str) -> List[Infraccion]:
    rnd = random.Random(f"{patente}-{nombre}")
    if rnd.random() < 0.45:
        return []
    textos = ["Circular por zona/carril prohibido", "Estac. lugar sin ticket/hora vencida",
              "No uso cinturón de seguridad", "Exceso de velocidad", "Cruzar semáforo en rojo"]
    return [
        Infraccion(
            acta=f"{rnd.choice('QIAF')}{rnd.randint(10_000_000, 99_999_999)}",
            descripcion=rnd.choice(textos),
            monto=float(rnd.randint(40, 600) * 1000) + rnd.choice([0, 0, 62]),
            controlador=rnd.random() < 0.3,
        )
        for _ in range(rnd.randint(1, 4))
    ]


async def _consultar_una(cfg: JurisdiccionConfig, patente: str, demo: bool, solver: CaptchaSolver) -> ResultadoJurisdiccion:
    r = ResultadoJurisdiccion(cfg.nombre, cfg.proteccion, cfg.url)

    if demo:
        await asyncio.sleep(random.uniform(0.2, 0.7))
        r.infracciones = _demo_infracciones(patente, cfg.nombre)
        r.estado = "con_multas" if r.infracciones else "sin_multas"
        r.demo = True
        return r

    if cfg.consultar is None:
        r.estado = "sin_conector"
        r.detalle = f"Sin consulta automática ({cfg.proteccion}). Abrir el portal."
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
        r.estado = "con_multas" if resp.infracciones else "sin_multas"
    except CaptchaError as exc:
        r.estado, r.detalle = "captcha_fallido", str(exc)
    except ConsultaIndeterminada as exc:
        r.estado, r.detalle = "indeterminado", str(exc)
        r.http_status, r.muestra = exc.http_status, exc.muestra
    except asyncio.TimeoutError:
        r.estado, r.detalle = "error", "Timeout: el portal no respondió a tiempo"
    except Exception as exc:  # noqa: BLE001
        r.estado, r.detalle = "error", f"{type(exc).__name__}: {exc}"
    if solver.api_key:  # nunca dejar la clave en mensajes
        r.detalle = r.detalle.replace(solver.api_key, "***")
        r.muestra = r.muestra.replace(solver.api_key, "***")
    return r


async def ejecutar_consultas(patente, lista, demo, solver, on_progress) -> List[ResultadoJurisdiccion]:
    tareas = [asyncio.create_task(_consultar_una(j, patente, demo, solver)) for j in lista]
    resultados: List[ResultadoJurisdiccion] = []
    total = len(tareas)
    for hecha in asyncio.as_completed(tareas):
        r = await hecha
        resultados.append(r)
        on_progress(len(resultados), total, r.nombre)
    orden = {j.nombre: i for i, j in enumerate(JURISDICCIONES)}
    return sorted(resultados, key=lambda x: orden[x.nombre])


def resumen_json(patente: str, resultados: List[ResultadoJurisdiccion], tecnico: bool = False) -> dict:
    """Misma estructura que la pantalla: resumen general → jurisdicciones con sus multas → estado de portales."""
    fallos = [r.nombre for r in resultados if r.estado in ESTADOS_FALLO]
    manuales = [r.nombre for r in resultados if r.estado == "sin_conector"]
    sin_multas = [r.nombre for r in resultados if r.estado == "sin_multas"]
    con = sorted([r for r in resultados if r.estado == "con_multas"], key=lambda r: -r.subtotal)
    n = sum(len(r.infracciones) for r in con)
    total = round(sum(r.subtotal for r in con), 2)

    if n:
        mensaje = f"Se encontraron {n} multa(s) por {pesos(total)} en {len(con)} jurisdicción(es)."
        if fallos:
            mensaje += f" ATENCIÓN: no se pudo consultar {', '.join(fallos)}; el total puede ser mayor."
    elif fallos:
        mensaje = ("No se encontraron multas en los portales que respondieron, pero "
                   f"{len(fallos)} no pudieron consultarse: {', '.join(fallos)}.")
    else:
        mensaje = "No se encontraron multas en las jurisdicciones consultadas automáticamente."

    return {
        "patente": patente,
        "consultado_en": datetime.now(TZ_AR).isoformat(timespec="seconds"),
        "mensaje": mensaje,
        "resultado_completo": not fallos,
        "resumen": {
            "cantidad_multas": n,
            "jurisdicciones_con_multas": len(con),
            "total_general": total,
            "total_general_formato": pesos(total),
            "por_jurisdiccion": [
                {"jurisdiccion": r.nombre, "multas": len(r.infracciones), "subtotal": round(r.subtotal, 2),
                 "subtotal_formato": pesos(r.subtotal)}
                for r in con
            ],
        },
        "jurisdicciones": [
            {
                "jurisdiccion": r.nombre,
                "cantidad": len(r.infracciones),
                "subtotal": round(r.subtotal, 2),
                "subtotal_formato": pesos(r.subtotal),
                "multas": [
                    {"acta": i.acta, "descripcion": i.descripcion, "monto": i.monto,
                     "monto_formato": pesos(i.monto), "etiquetas": i.etiquetas}
                    for i in r.infracciones
                ],
            }
            for r in con
        ],
        "sin_multas": sin_multas,
        "no_se_pudo_consultar": [
            {"jurisdiccion": r.nombre, "motivo": detalle_visible(r, tecnico)}
            for r in resultados if r.estado in ESTADOS_FALLO
        ],
        "consulta_manual": manuales,
    }


def detalle_visible(r: ResultadoJurisdiccion, tecnico: bool) -> str:
    if tecnico or r.estado not in ESTADOS_FALLO:
        return r.detalle
    return "No disponible en este momento. Podés consultarlo en el portal oficial."


def overlay(pct: int, estado: str) -> str:
    return (
        '<div class="ov"><div class="ovc">'
        '<div class="spin"></div>'
        '<h2>BUSCANDO MULTAS…</h2>'
        f'<div class="st">{html.escape(estado)}</div>'
        f'<div class="bar"><div style="width:{max(pct, 6)}%"></div></div>'
        '<div class="tip">Consultamos todas las jurisdicciones en simultáneo. Puede tardar hasta 1 minuto.</div>'
        '</div></div>'
    )


def _secret(nombre: str) -> str:
    try:
        return str(st.secrets.get(nombre, "") or "")
    except Exception:  # noqa: BLE001
        return ""


# =============================================================================
# 8. INTERFAZ
# =============================================================================
n_jur = len(JURISDICCIONES)
n_auto = sum(1 for j in JURISDICCIONES if j.consultar is not None)
logo_html = (
    f'<img class="logo" src="data:image/png;base64,{LOGO_B64}" alt="Marcelo Nuñez Gestiones">'
    if LOGO_B64 else '<div class="logo-txt">Marcelo Nuñez · GESTIONES</div>'
)
wa_hola = f"{WA_BASE}?text={quote('Hola Marcelo, quiero hacer una consulta.')}"

st.markdown(
    '<div class="topbar"><div class="brand"><b>GESTORÍA AUTOMOTOR</b><span>MARCELO NUÑEZ GESTIONES</span></div>'
    f'<a class="btn sm" href="{wa_hola}" target="_blank" rel="noopener">Contacto</a></div>'
    '<div class="hero"><div>'
    f'{logo_html}'
    '<div class="contactos">'
    f'<a class="cchip wa" href="{wa_hola}" target="_blank" rel="noopener">WhatsApp &nbsp;{WHATSAPP_TXT}</a>'
    f'<a class="cchip ig" href="https://instagram.com/{INSTAGRAM}" target="_blank" rel="noopener">@{INSTAGRAM}</a>'
    f'<a class="cchip ml" href="mailto:{EMAIL}">{EMAIL}</a>'
    '</div>'
    '<span class="tagline">● GESTORÍA AUTOMOTOR · BUENOS AIRES</span>'
    '<h1>TUS MULTAS,<em>SIN VUELTAS.</em></h1>'
    '<p class="lead">Consultá infracciones de tránsito por patente en todas las jurisdicciones disponibles. '
    'Gestiones automotoras rápidas y seguras: informes de dominio, transferencias, radicaciones, '
    'infracciones de tránsito y descargos de fotomultas. Atención personalizada con más de 5 años de experiencia.</p>'
    '<a class="btn" href="#buscador">Consultar ahora</a> &nbsp; <a class="btn ghost" href="#servicios">Ver servicios</a>'
    '</div>'
    '<div class="stats">'
    '<div class="stat"><b>+5K</b><span>Trámites realizados</span></div>'
    '<div class="stat"><b>24H</b><span>Tiempo promedio</span></div>'
    '<div class="stat"><b>100%</b><span>Trámites online</span></div>'
    '</div></div>'
    '<div id="buscador"></div>'
    '<div class="sec-title">BUSCADOR DE <em>INFRACCIONES</em></div>'
    f'<div class="sec-sub">{n_jur} jurisdicciones relevadas · {n_auto} con consulta automática · '
    f'{n_jur - n_auto} con acceso directo al portal oficial.</div>',
    unsafe_allow_html=True,
)

with st.form("buscador", clear_on_submit=False, border=True):
    patente_input = st.text_input(
        "Patente",
        placeholder="Ingresá tu patente sin espacios (ABC123 · AB123CD · A123BCD · 123ABC)",
        max_chars=10,
    )
    c1, c2 = st.columns([3, 1])
    with c1:
        modo = st.selectbox(
            "Jurisdicciones",
            ["Todas", "Solo sin CAPTCHA", "Solo con CAPTCHA / Cloudflare"],
            label_visibility="collapsed",
        )
    with c2:
        enviar = st.form_submit_button("🔎  Consultar", use_container_width=True)

# --- Configuración SEGURA ----------------------------------------------------
# La clave del captcha vive SOLO en Streamlit Secrets / variables de entorno.
# Nunca se pone en un campo de la pantalla ni se envía al navegador.
proveedor_captcha = (_secret("CAPTCHA_PROVIDER") or os.getenv("CAPTCHA_PROVIDER", "capsolver")).lower()
api_key_captcha = _secret("CAPSOLVER_API_KEY") or os.getenv("CAPSOLVER_API_KEY", "") or os.getenv("CAPTCHA_API_KEY", "")
es_admin = bool(st.session_state.get("admin_ok"))
mostrar_diag = False
demo = False

if es_admin:
    with st.expander("🔒 Panel de administración (solo vos)"):
        st.caption("Visible únicamente tras ingresar la contraseña de administrador. "
                   "La clave del captcha NO se muestra: se lee de Secrets.")
        st.write(f"Proveedor: **{proveedor_captcha}** · Clave cargada: **{'sí' if api_key_captcha else 'NO'}**")
        mostrar_diag = st.checkbox("Mostrar diagnóstico técnico por portal", value=True)
        demo = st.checkbox("Modo demo (datos SIMULADOS, solo para probar el diseño)", value=False)
        st.markdown("---")
        st.caption("🧪 **Explorador de portales**: lee cada portal desde este servidor (no gasta captcha).")
        if st.button("🧪 Explorar portales ahora"):
            with st.spinner("Explorando portales… (hasta 1 minuto)"):
                st.session_state["explorador"] = asyncio.run(explorar_todos())
        if "explorador" in st.session_state:
            st.code(json.dumps(st.session_state["explorador"], ensure_ascii=False, indent=1), language="json")
        if st.button("Cerrar sesión de administrador"):
            st.session_state["admin_ok"] = False
            st.rerun()

# --- Ejecución ---------------------------------------------------------------
if enviar:
    dominio = normalizar_patente(patente_input)
    if not PATRON_PATENTE.match(dominio):
        st.error("Formato de patente inválido. Ejemplos: HNQ904, AB123CD, A123BCD, 123ABC.")
    else:
        if modo == "Solo sin CAPTCHA":
            lista = [j for j in JURISDICCIONES if j.proteccion == "Sin CAPTCHA"]
        elif modo == "Solo con CAPTCHA / Cloudflare":
            lista = [j for j in JURISDICCIONES if j.proteccion != "Sin CAPTCHA"]
        else:
            lista = JURISDICCIONES

        solver = CaptchaSolver(proveedor_captcha, api_key_captcha)
        ph = st.empty()
        ph.markdown(overlay(0, "Preparando consulta"), unsafe_allow_html=True)

        def _progreso(hechas: int, total: int, nombre: str) -> None:
            ph.markdown(overlay(int(hechas / total * 100), f"Consultado: {nombre} ({hechas}/{total})"),
                        unsafe_allow_html=True)

        res = asyncio.run(ejecutar_consultas(dominio, lista, demo, solver, _progreso))
        ph.empty()
        st.session_state["resultados"] = res
        st.session_state["patente"] = dominio

# --- Resultados --------------------------------------------------------------
if "resultados" in st.session_state:
    resultados: List[ResultadoJurisdiccion] = st.session_state["resultados"]
    dominio = st.session_state["patente"]

    con_multas = [r for r in resultados if r.estado == "con_multas"]
    consultados_ok = [r for r in resultados if r.conectado]
    fallidos = [r for r in resultados if r.estado in ESTADOS_FALLO]
    manuales = [r for r in resultados if r.estado == "sin_conector"]
    total = sum(r.subtotal for r in con_multas)
    n_multas = sum(len(r.infracciones) for r in con_multas)
    hay_demo = any(r.demo for r in resultados)
    parcial = bool(fallidos)

    # Resumen flotante
    filas = ""
    for r in con_multas:
        c = color_de(r.nombre)
        n = len(r.infracciones)
        filas += (
            f'<div class="row" style="background:{c}1f;border-color:{c}66"><span style="color:{c}">{html.escape(r.nombre.upper()[:9])}</span>'
            f'<span class="m"><small>{n} multa{"s" if n != 1 else ""}</small>{pesos(r.subtotal)}</span></div>'
        )
    if con_multas:
        aviso = f'<div class="parcial">⚠ PARCIAL: {len(fallidos)} portal(es) sin consultar</div>' if parcial else ""
        st.markdown(
            '<div class="float"><div class="h">RESUMEN</div><div class="s">JURISDICCIONES</div>'
            f'{filas}<div class="s">TOTAL GENERAL</div><div class="tot">{pesos(total)}</div>{aviso}</div>',
            unsafe_allow_html=True,
        )

    # Cabecera de resultados
    jchips = "".join(
        f'<a class="jchip" href="#j{i}" style="color:{color_de(r.nombre)};border-color:{color_de(r.nombre)}88;'
        f'background:{color_de(r.nombre)}1a">{html.escape(r.nombre)} ({len(r.infracciones)})</a>'
        for i, r in enumerate(con_multas)
    )
    if con_multas:
        intro = "Encontramos información para la patente consultada."
    elif consultados_ok and not parcial:
        intro = "No encontramos infracciones en las jurisdicciones consultadas."
    elif consultados_ok:
        intro = "Sin multas en los portales que respondieron, pero algunos no pudieron consultarse."
    else:
        intro = "No se pudo completar la consulta automática. Revisá el estado de cada portal."
    estado_txt = "Parcial" if parcial else "Completo"
    st.markdown(
        '<div class="res-head"><h2>RESULTADO DE LA BÚSQUEDA</h2>'
        f'<div class="plate">{html.escape(dominio)}</div>'
        f'<div class="sec-sub" style="margin:0">{intro}</div>'
        '<div class="kpis">'
        f'<div class="kpi"><b>{pesos(total)}</b><span>Total general</span></div>'
        f'<div class="kpi"><b>{n_multas}</b><span>Multas encontradas</span></div>'
        f'<div class="kpi"><b>{len(con_multas)}</b><span>Jurisdicciones con multas</span></div>'
        f'<div class="kpi"><b>{estado_txt}</b><span>Consulta ({len(consultados_ok)}/{len(resultados) - len(manuales)} portales)</span></div>'
        '</div>'
        + (f'<div style="margin-top:1rem">{jchips}</div>' if con_multas else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    if hay_demo:
        st.markdown('<div class="warn">⚠️ <b>Modo demo:</b> los datos mostrados son simulados, no corresponden a multas reales.</div>', unsafe_allow_html=True)

    if parcial and not hay_demo:
        nombres = ", ".join(html.escape(r.nombre) for r in fallidos)
        st.markdown(
            f'<div class="warn">⚠️ <b>Resultado PARCIAL.</b> No se pudo consultar: {nombres}. '
            'El total puede ser mayor al mostrado.</div>',
            unsafe_allow_html=True,
        )

    # Tablas por jurisdicción
    for i, r in enumerate(con_multas):
        c = color_de(r.nombre)
        filas_t = ""
        for inf in r.infracciones:
            tag = "".join(
                f'<span class="tag{" pv" if "VOLUNTARIO" in e else ""}">{html.escape(e)}</span> ' for e in inf.etiquetas
            )
            tag = (tag + "<br>") if tag else ""
            filas_t += (
                f"<tr><td>{html.escape(inf.acta)}</td>"
                f'<td class="l">{tag}{html.escape(inf.descripcion)}</td>'
                f"<td>{pesos(inf.monto)}</td></tr>"
            )
        st.markdown(
            f'<div class="card" id="j{i}"><h3><i style="background:{c}"></i>MULTAS {html.escape(r.nombre.upper())}'
            f'<small>{len(r.infracciones)} · {pesos(r.subtotal)}</small></h3>'
            '<div class="tablewrap"><table class="t"><thead><tr><th>N° Acta</th><th>Descripción</th><th>Monto</th></tr></thead>'
            f"<tbody>{filas_t}</tbody><tfoot><tr><td colspan=\"2\" class=\"r\">Subtotal {html.escape(r.nombre)}</td>"
            f"<td>{pesos(r.subtotal)}</td></tr></tfoot></table></div></div>",
            unsafe_allow_html=True,
        )

    if con_multas:
        st.markdown(
            f'<div class="totalbar"><span>TOTAL GENERAL · {n_multas} MULTA{"S" if n_multas != 1 else ""}</span>'
            f'<b>{pesos(total)}</b></div>',
            unsafe_allow_html=True,
        )

    if consultados_ok and not con_multas and not parcial:
        st.markdown(f'<div class="ok">✅ La patente {html.escape(dominio)} no registra infracciones en las jurisdicciones consultadas automáticamente.</div>', unsafe_allow_html=True)

    # Estado de TODOS los portales
    filas_p = ""
    for r in resultados:
        etiqueta, clase = ESTADO_UI.get(r.estado, (r.estado, "neutral"))
        extra = f" · {len(r.infracciones)} multa(s)" if r.estado == "con_multas" else ""
        filas_p += (
            f'<tr><td>{html.escape(r.nombre)}</td>'
            f'<td><span class="est {clase}">{etiqueta}</span>{extra}</td>'
            f'<td class="l">{html.escape(detalle_visible(r, es_admin)) or "—"}</td>'
            f'<td><a class="portal" href="{html.escape(r.url)}" target="_blank" rel="noopener">Abrir portal ↗</a></td></tr>'
        )
    st.markdown(
        '<div class="card"><h3><i style="background:#64748b"></i>ESTADO DE CADA PORTAL</h3>'
        '<div class="tablewrap"><table class="t"><thead><tr><th>Jurisdicción</th><th>Estado</th><th>Detalle</th><th>Acceso</th></tr></thead>'
        f"<tbody>{filas_p}</tbody></table></div></div>",
        unsafe_allow_html=True,
    )

    # CTA a WhatsApp con la patente y el total
    if con_multas and not hay_demo:
        msg = (f"Hola Marcelo, consulté la patente {dominio} en tu buscador y tiene {n_multas} multa(s) por "
               f"{pesos(total)}. Quiero que me ayudes a gestionarlas.")
        st.markdown(
            '<div class="cta-box"><h3>¿TENÉS MULTAS? LAS GESTIONAMOS POR VOS</h3>'
            '<p>Descargos, fotomultas y pagos. Atención personalizada, 100% online.</p>'
            f'<a class="btn" href="{WA_BASE}?text={quote(msg)}" target="_blank" rel="noopener">Hablar por WhatsApp ahora</a></div>'
            f'<div class="sticky-wa"><span>¿Querés sacarte estas multas de encima? Te ayudamos.</span>'
            f'<a class="btn wa" href="{WA_BASE}?text={quote(msg)}" target="_blank" rel="noopener">Hablar por WhatsApp</a></div>',
            unsafe_allow_html=True,
        )

    # Resumen en JSON
    datos_json = resumen_json(dominio, resultados, tecnico=es_admin)
    texto_json = json.dumps(datos_json, ensure_ascii=False, indent=2)
    with st.expander("📦 Resumen en JSON", expanded=bool(con_multas)):
        st.json(datos_json, expanded=2)
        st.download_button("⬇️ Descargar JSON", data=texto_json, file_name=f"infracciones_{dominio}.json",
                           mime="application/json")

    # Diagnóstico
    if es_admin and mostrar_diag and fallidos:
        with st.expander("🛠️ Diagnóstico de portales con problemas", expanded=False):
            for r in fallidos:
                st.markdown(f"**{r.nombre}** — {ESTADO_UI[r.estado][0]} · HTTP {r.http_status or '—'}")
                st.caption(r.detalle)
                if r.muestra:
                    st.code(r.muestra, language="text")

# --- Acceso de administrador (oculto) -----------------------------------------
# Solo aparece al entrar con  ?admin=1  Y si configuraste ADMIN_PASSWORD en Secrets.
if (not es_admin) and _secret("ADMIN_PASSWORD") and st.query_params.get("admin") == "1":
    with st.form("login_admin"):
        pwd = st.text_input("Contraseña de administrador", type="password")
        if st.form_submit_button("Ingresar"):
            if hmac.compare_digest(pwd.encode(), _secret("ADMIN_PASSWORD").encode()):
                st.session_state["admin_ok"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")

# --- Servicios y pie ---------------------------------------------------------
st.markdown(
    '<div id="servicios"></div><div class="sec-title">NUESTROS <em>SERVICIOS</em></div>'
    '<div class="servicios">'
    '<div class="serv">Informes de dominio</div><div class="serv">Transferencias</div>'
    '<div class="serv">Radicaciones</div><div class="serv">Infracciones de tránsito</div>'
    '<div class="serv">Descargos de fotomultas</div></div>'
    '<div class="contactos" style="flex-direction:row;flex-wrap:wrap;margin-top:1.2rem">'
    f'<a class="cchip wa" href="{wa_hola}" target="_blank" rel="noopener">WhatsApp &nbsp;{WHATSAPP_TXT}</a>'
    f'<a class="cchip ig" href="https://instagram.com/{INSTAGRAM}" target="_blank" rel="noopener">@{INSTAGRAM}</a>'
    f'<a class="cchip ml" href="mailto:{EMAIL}">{EMAIL}</a></div>'
    '<div class="foot">Marcelo Nuñez Gestiones · Gestoría Automotor · Buenos Aires<br>'
    'La información se obtiene de los portales oficiales de cada jurisdicción y es de carácter informativo. '
    'Puede haber infracciones en proceso de carga.</div>',
    unsafe_allow_html=True,
)
