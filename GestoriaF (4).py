# -*- coding: utf-8 -*-
"""
Marcelo Nuñez Gestiones | Buscador de infracciones por patente
Streamlit + HTTP directo + APIs REST + CapSolver (reCAPTCHA v2 + Cloudflare Turnstile + OCR Imagen).

Archivos que van juntos en el repositorio:
  GestoriaF.py            (este archivo)
  logo.png                (tu logo, al lado del .py)
  requirements.txt
  .streamlit/config.toml  (tema oscuro)
"""
from __future__ import annotations

import asyncio
import base64
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
# 3. CLIENTE ANTI-CAPTCHA (CapSolver / 2Captcha: reCAPTCHA v2 + Turnstile + OCR)
# =============================================================================
class CaptchaSolver:
    def __init__(self, provider: str = "capsolver", api_key: str = ""):
        self.provider = provider.lower().strip()
        self.api_key = api_key.strip()

    async def solve_recaptcha_v2(self, site_key: str, page_url: str, invisible: bool = False) -> str:
        if not self.api_key:
            raise CaptchaError("Falta la API Key del servicio de captcha (ver 'Opciones de desarrollo y Captcha').")

        async with httpx.AsyncClient(timeout=35) as client:
            if self.provider == "capsolver":
                for task_type in ("ReCaptchaV2TaskProxyLess", "ReCaptchaV2EnterpriseTaskProxyLess"):
                    task = {"type": task_type, "websiteURL": page_url, "websiteKey": site_key}
                    if invisible:
                        task["isInvisible"] = True
                    r = await client.post(
                        "https://api.capsolver.com/createTask",
                        json={"clientKey": self.api_key, "task": task},
                    )
                    data = r.json()
                    if data.get("errorId", 0) != 0:
                        if task_type == "ReCaptchaV2EnterpriseTaskProxyLess":
                            raise CaptchaError(f"CapSolver: {data.get('errorCode')} - {data.get('errorDescription')}")
                        continue
                    task_id = data["taskId"]

                    for _ in range(55):
                        await asyncio.sleep(2)
                        res = await client.post(
                            "https://api.capsolver.com/getTaskResult",
                            json={"clientKey": self.api_key, "taskId": task_id},
                        )
                        rd = res.json()
                        if rd.get("errorId", 0) != 0:
                            break
                        if rd.get("status") == "ready":
                            return rd["solution"]["gRecaptchaResponse"]
                        if rd.get("status") == "failed":
                            break
                raise CaptchaError("CapSolver no pudo resolver el reCAPTCHA del portal.")
            else:
                params = {
                    "key": self.api_key,
                    "method": "userrecaptcha",
                    "googlekey": site_key,
                    "pageurl": page_url,
                    "invisible": 1 if invisible else 0,
                    "json": 1,
                }
                r = await client.get("http://2captcha.com/in.php", params=params)
                data = r.json()
                if data.get("status") != 1:
                    raise CaptchaError(f"2Captcha: {data.get('request')}")
                req_id = data["request"]

                for _ in range(35):
                    await asyncio.sleep(3.5)
                    res = await client.get(
                        "http://2captcha.com/res.php",
                        params={"key": self.api_key, "action": "get", "id": req_id, "json": 1},
                    )
                    rd = res.json()
                    if rd.get("status") == 1:
                        return rd["request"]
                    if rd.get("request") != "CAPCHA_NOT_READY":
                        raise CaptchaError(f"2Captcha: {rd.get('request')}")

        raise CaptchaError("Tiempo agotado esperando la solución del captcha.")

    async def solve_turnstile(self, site_key: str, page_url: str) -> str:
        if not self.api_key:
            raise CaptchaError("Falta la API Key del servicio de captcha.")
        async with httpx.AsyncClient(timeout=35) as client:
            if self.provider == "capsolver":
                task = {"type": "AntiTurnstileTaskProxyLess", "websiteURL": page_url, "websiteKey": site_key}
                r = await client.post(
                    "https://api.capsolver.com/createTask",
                    json={"clientKey": self.api_key, "task": task},
                )
                data = r.json()
                if data.get("errorId", 0) != 0:
                    raise CaptchaError(f"CapSolver Turnstile: {data.get('errorCode')} - {data.get('errorDescription')}")
                task_id = data["taskId"]
                for _ in range(45):
                    await asyncio.sleep(2)
                    res = await client.post(
                        "https://api.capsolver.com/getTaskResult",
                        json={"clientKey": self.api_key, "taskId": task_id},
                    )
                    rd = res.json()
                    if rd.get("errorId", 0) != 0:
                        raise CaptchaError(f"CapSolver Turnstile: {rd.get('errorDescription')}")
                    if rd.get("status") == "ready":
                        return rd["solution"]["token"]
                    if rd.get("status") == "failed":
                        raise CaptchaError("CapSolver Turnstile: la tarea falló")
            else:
                params = {
                    "key": self.api_key,
                    "method": "turnstile",
                    "sitekey": site_key,
                    "pageurl": page_url,
                    "json": 1,
                }
                r = await client.get("http://2captcha.com/in.php", params=params)
                data = r.json()
                if data.get("status") != 1:
                    raise CaptchaError(f"2Captcha Turnstile: {data.get('request')}")
                req_id = data["request"]
                for _ in range(35):
                    await asyncio.sleep(3)
                    res = await client.get(
                        "http://2captcha.com/res.php",
                        params={"key": self.api_key, "action": "get", "id": req_id, "json": 1},
                    )
                    rd = res.json()
                    if rd.get("status") == 1:
                        return rd["request"]
                    if rd.get("request") != "CAPCHA_NOT_READY":
                        raise CaptchaError(f"2Captcha Turnstile: {rd.get('request')}")
        raise CaptchaError("Tiempo agotado esperando Cloudflare Turnstile.")

    async def solve_image_captcha(self, img_bytes: bytes) -> str:
        if not self.api_key:
            raise CaptchaError("Falta la API Key del servicio de captcha.")
        b64_img = base64.b64encode(img_bytes).decode()
        async with httpx.AsyncClient(timeout=30) as client:
            if self.provider == "capsolver":
                r = await client.post(
                    "https://api.capsolver.com/createTask",
                    json={"clientKey": self.api_key, "task": {"type": "ImageToTextTask", "body": b64_img}},
                )
                data = r.json()
                if data.get("errorId", 0) != 0:
                    raise CaptchaError(f"CapSolver OCR: {data.get('errorDescription')}")
                sol = data.get("solution", {})
                if sol.get("text"):
                    return sol["text"].strip()
                task_id = data.get("taskId")
                for _ in range(15):
                    await asyncio.sleep(1.5)
                    res = await client.post(
                        "https://api.capsolver.com/getTaskResult",
                        json={"clientKey": self.api_key, "taskId": task_id},
                    )
                    rd = res.json()
                    if rd.get("status") == "ready":
                        return rd["solution"]["text"].strip()
            else:
                r = await client.post(
                    "http://2captcha.com/in.php",
                    data={"key": self.api_key, "method": "base64", "body": b64_img, "json": 1},
                )
                data = r.json()
                if data.get("status") != 1:
                    raise CaptchaError(f"2Captcha OCR: {data.get('request')}")
                req_id = data["request"]
                for _ in range(20):
                    await asyncio.sleep(2.5)
                    res = await client.get(
                        "http://2captcha.com/res.php",
                        params={"key": self.api_key, "action": "get", "id": req_id, "json": 1},
                    )
                    rd = res.json()
                    if rd.get("status") == 1:
                        return rd["request"].strip()
        raise CaptchaError("No se pudo decodificar el captcha de texto.")


# =============================================================================
# 4. PARSEO ROBUSTO (HTML + JSON + PBA + EZEIZA + LANÚS + ENTRE RÍOS)
# =============================================================================
RE_VACIO = re.compile(
    r"no registra|no posee|no se encontr|sin infracciones|sin deuda|libre de deuda|"
    r"no tiene (infracciones|multas|deuda|actas)|no existen|no hay (infracciones|multas|actas)|"
    r"sin resultados|0 resultados|no se hallaron|no ten[eé]s infracciones|no registramos",
    re.I,
)
RE_CAPTCHA_MAL = re.compile(
    r"captcha (inv[aá]lido|incorrecto|expirado|vencido)|verificaci[oó]n .{0,30}(fall|inv[aá]lid)|"
    r"recaptcha.{0,30}(fall|inv[aá]lid|error)|robot.{0,40}(fall|error)",
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
                    elif idx_acta is None and re.search(r"acta|n[°ºo]\b|nro|n[uú]mero|comprobante|expediente|causa", hl):
                        idx_acta = i
                    elif idx_desc is None and re.search(r"descrip|infracci|falta|motivo|concepto|norma|detalle", hl):
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
                controlador="controlador" in " ".join(cols).lower(),
            ))
    return out


def _tarjetas_a_infracciones(soup: BeautifulSoup) -> List[Infraccion]:
    out: List[Infraccion] = []
    selectores = ".acta-item, .infraccion-card, .card-infraccion, .panel-infraccion, [class*='infraccion'], [class*='acta'], [class*='causa']"
    for el in soup.select(selectores):
        txt = re.sub(r"\s+", " ", el.get_text(" | ", strip=True))
        if len(txt) < 18 or len(txt) > 1200:
            continue
        m_acta = re.search(r"(?:acta|causa|n[°ºo]|nro)[:\s#]*([A-Z0-9\-]{5,22})|\b([A-Z]{1,2}\d{7,10}|\d{2}-\d{3}-\d{6,9}-\d)\b", txt, re.I)
        m_monto = re.search(r"\$\s*([\d.,]+)", txt)
        if m_acta and m_monto:
            acta = (m_acta.group(1) or m_acta.group(2) or "S/N").strip()
            monto = limpiar_monto(m_monto.group(1))
            out.append(Infraccion(
                acta=acta[:30],
                descripcion=txt[:140],
                monto=monto,
                controlador="controlador" in txt.lower(),
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
    # 1. PBA
    if isinstance(data, dict) and "totalInfracciones" in data and isinstance(data.get("infracciones"), list):
        if data.get("totalInfracciones", 0) == 0 or not data["infracciones"]:
            return [], True
        out_pba: List[Infraccion] = []
        for item in data["infracciones"]:
            if not isinstance(item, dict):
                continue
            acta = str(item.get("nroActa") or item.get("nroCausa") or item.get("id") or "S/N")
            desc = ""
            if isinstance(item.get("infracciones"), list) and item["infracciones"]:
                sub = item["infracciones"][0]
                if isinstance(sub, dict):
                    art = sub.get("articulo", "")
                    d_txt = sub.get("descripcion", "")
                    desc = f"Art. {art} - {d_txt}".strip(" -") if art else d_txt
            autoridad = item.get("autoridadAplicacion") or ""
            if autoridad:
                desc = f"{desc} ({autoridad})".strip()
            estado_pub = ""
            if isinstance(item.get("estadoCausaPublico"), dict):
                estado_pub = str(item["estadoCausaPublico"].get("descripcion", ""))
            monto = limpiar_monto(item.get("importeTotal") or item.get("importe"))
            out_pba.append(Infraccion(
                acta=acta[:30],
                descripcion=(desc or "Infracción PBA")[:140],
                monto=monto,
                controlador=("juzgamiento" in estado_pub.lower() or "controlador" in desc.lower()),
            ))
        return out_pba, True

    # 2. Ezeiza / Lanús / Infratrack
    if isinstance(data, dict) and ("total_infracciones" in data or "sId" in data):
        lista_ez = data.get("infracciones") if isinstance(data.get("infracciones"), list) else []
        if data.get("total_infracciones", 0) == 0 or not lista_ez:
            return [], True
        out_ez: List[Infraccion] = []
        for item in lista_ez:
            if not isinstance(item, dict):
                continue
            acta = str(item.get("nro_acta") or item.get("acta") or item.get("numero") or item.get("id") or "S/N")
            desc = str(item.get("descripcion") or item.get("infraccion") or item.get("motivo") or item.get("falta") or "Infracción")
            monto = limpiar_monto(item.get("monto") or item.get("importe") or item.get("valor") or item.get("total"))
            out_ez.append(Infraccion(acta=acta[:30], descripcion=desc[:140], monto=monto))
        return out_ez, True

    # 3. Entre Ríos / Misiones Monitoreo Vial v3
    if isinstance(data, dict) and isinstance(data.get("datos"), dict) and "data" in data["datos"]:
        bloque = data["datos"]
        lista_mv = bloque.get("data") if isinstance(bloque.get("data"), list) else []
        if bloque.get("total", 0) == 0 or not lista_mv:
            return [], True
        out_mv: List[Infraccion] = []
        for item in lista_mv:
            if not isinstance(item, dict):
                continue
            acta = str(item.get("nro_acta") or item.get("numero_acta") or item.get("acta") or item.get("nroActa") or "S/N")
            desc = str(item.get("descripcion") or item.get("infraccion") or item.get("motivo") or "Infracción Monitoreo Vial")
            monto = limpiar_monto(item.get("monto") or item.get("importe") or item.get("monto_actual") or item.get("valor"))
            out_mv.append(Infraccion(acta=acta[:30], descripcion=desc[:140], monto=monto))
        return out_mv, True

    # 4. Genérico
    listas: list = []
    vacias: list = []
    _listas_de_dicts(data, listas, vacias)
    out: List[Infraccion] = []
    for lista in listas:
        for d in lista:
            if "label" in d and "active" in d and len(d) <= 4:
                continue
            acta = _val(d, r"nroActa|nro_acta|numero_acta|nroCausa|acta|nro|numero|n[uú]m|comprobante|expediente|^id$")
            monto = _val(d, r"importeTotal|monto_actual|monto|importe|total|deuda|saldo|valor")
            desc = _val(d, r"descrip|infracci|falta|motivo|concepto")
            if not desc and isinstance(d.get("infracciones"), list) and d["infracciones"]:
                primera = d["infracciones"][0]
                if isinstance(primera, dict):
                    desc = primera.get("descripcion")
            if acta is None or monto is None:
                continue
            out.append(Infraccion(
                acta=str(acta)[:30],
                descripcion=str(desc or "Infracción de tránsito")[:140],
                monto=limpiar_monto(monto),
                controlador="controlador" in json.dumps(d, ensure_ascii=False).lower(),
            ))
    return out, bool(vacias)


def _dedup(items: List[Infraccion]) -> List[Infraccion]:
    vistos, res = set(), []
    for i in items:
        k = (i.acta, i.monto)
        if k not in vistos:
            vistos.add(k)
            res.append(i)
    return res


def interpretar_respuesta(resp: httpx.Response) -> RespuestaPortal:
    ctype = resp.headers.get("content-type", "").lower()
    cuerpo = resp.text or ""
    muestra = re.sub(r"\s+", " ", cuerpo)[:800]

    if resp.status_code >= 400:
        extra = " (posible bloqueo por IP extranjera / WAF)" if resp.status_code in (403, 429) else ""
        raise ConsultaIndeterminada(f"HTTP {resp.status_code}{extra}", resp.status_code, muestra)

    if "json" in ctype or cuerpo.lstrip().startswith(("{", "[")):
        try:
            data = resp.json()
        except ValueError:
            data = None
        if data is not None:
            if isinstance(data, dict) and data.get("error") is True:
                msg_err = str(data.get("mensaje") or data.get("message") or "Error devuelto por la API")
                if RE_CAPTCHA_MAL.search(msg_err):
                    raise CaptchaError(msg_err)
                raise ConsultaIndeterminada(msg_err, resp.status_code, muestra)
            items, hay_lista_vacia = _json_a_infracciones(data)
            if items:
                return RespuestaPortal(_dedup(items), resp.status_code, muestra)
            if hay_lista_vacia or RE_VACIO.search(cuerpo):
                return RespuestaPortal([], resp.status_code, muestra)
            raise ConsultaIndeterminada("JSON sin estructura de infracciones reconocible", resp.status_code, muestra)

    soup = BeautifulSoup(cuerpo, "html.parser")
    items = _tabla_a_infracciones(soup) or _tarjetas_a_infracciones(soup)
    if items:
        return RespuestaPortal(_dedup(items), resp.status_code, muestra)

    visible = texto_visible(BeautifulSoup(cuerpo, "html.parser"))
    muestra = visible[:800] or muestra
    if RE_CAPTCHA_MAL.search(visible):
        raise CaptchaError("El portal rechazó el token del captcha")
    if RE_VACIO.search(visible):
        return RespuestaPortal([], resp.status_code, muestra)
    raise ConsultaIndeterminada(
        "Respuesta sin tabla de infracciones ni mensaje de 'sin infracciones'",
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
    r'siteKey["\']?\s*[:=]\s*["\']([0-9A-Za-z_-]{40})["\']',
    r'recaptcha/(?:api|enterprise)\.js\?[^"\']*render=([0-9A-Za-z_-]{40})',
    r'[?&]k=([0-9A-Za-z_-]{40})',
    r'["\'](6L[0-9A-Za-z_-]{38})["\']',
]
RE_TURNSTILE_KEY = [
    r'data-sitekey=["\'](0x4[0-9A-Za-z_-]{18,30})["\']',
    r'sitekey["\']?\s*[:=]\s*["\'](0x4[0-9A-Za-z_-]{18,30})["\']',
    r'["\'](0x4[0-9A-Za-z_-]{18,30})["\']',
]

SITEKEYS_CONOCIDAS: dict[str, str] = {
    "infratrack.com.ar": "6LcMR6gZAAAAACdq_y61ZBsOVCZVR2zb3lzk7rAZ",
    "tramitesweb.lanus.gob.ar": "6LfQHDcUAAAAANFP3YIzL4g-bS_0aY1aRsyWjLZz",
}


def _buscar_sitekey_en_texto(texto: str) -> str | None:
    for p in RE_SITEKEY:
        m = re.search(p, texto)
        if m:
            return m.group(1)
    return None


def _buscar_turnstile_en_texto(texto: str) -> str | None:
    for p in RE_TURNSTILE_KEY:
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
    scripts = [s for s in scripts if "google.com" not in s and "gstatic.com" not in s][:10]
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
    campos = soup.find_all(_es_input_texto)
    campo = next((c for c in campos if RE_CAMPO_PATENTE.search((c.get("name") or "") + " " + (c.get("id") or ""))), None)
    campo = campo or (campos[0] if campos else None)
    if campo is None or not campo.get("name"):
        raise ConsultaIndeterminada("No hay formulario con campo de patente en el HTML.")
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
    async with nuevo_cliente(45) as client:
        r_get = await client.get(url)
        if r_get.status_code >= 400:
            interpretar_respuesta(r_get)
        soup = BeautifulSoup(r_get.text, "html.parser")
        metodo, destino, datos = preparar_form(soup, str(r_get.url), patente)

        if solver is not None:
            sitekey = await buscar_sitekey(client, str(r_get.url), r_get.text)
            if not sitekey:
                raise ConsultaIndeterminada("No se encontró el sitekey de reCAPTCHA.", r_get.status_code)
            token = await solver.solve_recaptcha_v2(sitekey, str(r_get.url), invisible=invisible)
            datos["g-recaptcha-response"] = token

        if metodo == "get":
            r_post = await client.get(destino, params=datos)
        else:
            r_post = await client.post(destino, data=datos, headers={"Referer": str(r_get.url)})
        return interpretar_respuesta(r_post)


# --- CONECTOR DEDICADO 1: PBA ---
async def http_pba_api(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    url_web = "https://infraccionesba.gba.gob.ar/consulta-infraccion"
    url_api = "https://infraccionesba.gba.gob.ar/rest/consultar-infraccion"
    async with nuevo_cliente(50) as client:
        r_get = await client.get(url_web)
        if r_get.status_code >= 400:
            return interpretar_respuesta(r_get)
        sitekey = await buscar_sitekey(client, str(r_get.url), r_get.text)
        if not sitekey:
            raise ConsultaIndeterminada("No se pudo extraer el sitekey de PBA.", r_get.status_code)
        token = await solver.solve_recaptcha_v2(sitekey, url_web, invisible=False)
        params = {"dominio": patente, "reCaptcha": token, "cantPorPagina": 10, "paginaActual": 1}
        r_api = await client.get(url_api, params=params, headers={"Referer": url_web, "Accept": "application/json, text/plain, */*"})
        return interpretar_respuesta(r_api)


# --- CONECTOR DEDICADO 2: EZEIZA / INFRATRACK ---
async def http_ezeiza_api(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    url_web = "https://consulta-web.infratrack.com.ar/consultas.php?municipio=ezeiza"
    sitekey = "6LcMR6gZAAAAACdq_y61ZBsOVCZVR2zb3lzk7rAZ"
    async with nuevo_cliente(50) as client:
        r_get = await client.get(url_web)
        if r_get.status_code >= 400:
            return interpretar_respuesta(r_get)
        token = await solver.solve_recaptcha_v2(sitekey, url_web)
        candidatos = [
            "https://consulta-web.infratrack.com.ar/ajax/consultas.php",
            "https://consulta-web.infratrack.com.ar/controladores/consultas.php",
            url_web,
        ]
        payload = {
            "municipio": "ezeiza",
            "tipo_consulta": "DOMINIO",
            "consulta": patente,
            "dominio": patente,
            "patente": patente,
            "tipo": "dominio",
            "page": 1,
            "g-recaptcha-response": token,
            "recaptcha": token,
        }
        ultimo_resp = r_get
        for ep in candidatos:
            r_post = await client.post(ep, data=payload, headers={"Referer": url_web, "X-Requested-With": "XMLHttpRequest"})
            ultimo_resp = r_post
            if "json" in r_post.headers.get("content-type", "").lower() or r_post.text.lstrip().startswith(("{", "[")):
                return interpretar_respuesta(r_post)
        return interpretar_respuesta(ultimo_resp)


# --- CONECTOR DEDICADO 3: LANÚS (Infratrack + 6LfQHDcU...) --------------
async def http_lanus_api(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    url_web = "https://tramitesweb.lanus.gob.ar/lanusdigital/mis-dominios"
    sitekey = "6LfQHDcUAAAAANFP3YIzL4g-bS_0aY1aRsyWjLZz"
    async with nuevo_cliente(50) as client:
        r_get = await client.get(url_web)
        if r_get.status_code >= 400:
            return interpretar_respuesta(r_get)
        token = await solver.solve_recaptcha_v2(sitekey, url_web)
        candidatos = [
            "https://tramitesweb.lanus.gob.ar/lanusdigital/ajax/consultas.php",
            "https://tramitesweb.lanus.gob.ar/lanusdigital/controladores/consultas.php",
            "https://tramitesweb.lanus.gob.ar/lanusdigital/mis-dominios",
            url_web,
        ]
        payload = {
            "municipio": "lanus",
            "tipo_consulta": "DOMINIO",
            "consulta": patente,
            "dominio": patente,
            "patente": patente,
            "tipo": "dominio",
            "page": 1,
            "g-recaptcha-response": token,
            "recaptcha": token,
        }
        ultimo_resp = r_get
        for ep in candidatos:
            try:
                r_post = await client.post(ep, data=payload, headers={"Referer": url_web, "X-Requested-With": "XMLHttpRequest"})
                ultimo_resp = r_post
                if "json" in r_post.headers.get("content-type", "").lower() or r_post.text.lstrip().startswith(("{", "[")):
                    return interpretar_respuesta(r_post)
            except Exception:
                continue
        return interpretar_respuesta(ultimo_resp)


# --- CONECTOR DEDICADO 4: ENTRE RÍOS Y MISIONES ---
async def http_monitoreo_vial_api(url_base: str, api_host: str, patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    async with nuevo_cliente(50) as client:
        r_get = await client.get(url_base)
        if r_get.status_code >= 400:
            return interpretar_respuesta(r_get)
        sitekey = await buscar_sitekey(client, str(r_get.url), r_get.text)
        token = await solver.solve_recaptcha_v2(sitekey, url_base) if sitekey else ""
        candidatos = [
            f"{api_host.rstrip('/')}/api/v3/69fa0e115c1082b8",
            f"{api_host.rstrip('/')}/api/v3/infracciones",
        ]
        headers_api = {"Referer": url_base, "Origin": url_base.rstrip("/"), "Accept": "application/json, text/plain, */*"}
        ultimo_r = r_get
        for ep in candidatos:
            try:
                r_post = await client.post(
                    ep,
                    json={"dominio": patente, "patente": patente, "recaptcha": token, "g-recaptcha-response": token, "page": 1},
                    headers=headers_api,
                )
                if r_post.status_code == 200 and "json" in r_post.headers.get("content-type", "").lower():
                    return interpretar_respuesta(r_post)
            except Exception:
                continue
        return interpretar_respuesta(ultimo_r)


# --- CONECTOR DEDICADO 5: CABA ---
async def http_caba_api(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    url_web = "https://buenosaires.gob.ar/licenciasdeconducir/consulta-de-infracciones/?actas=transito"
    url_post = "https://buenosaires.gob.ar/licenciasdeconducir/consulta-de-infracciones/index.php"
    async with nuevo_cliente(50) as client:
        r_get = await client.get(url_web)
        if r_get.status_code >= 400:
            return interpretar_respuesta(r_get)
        sitekey = await buscar_sitekey(client, str(r_get.url), r_get.text)
        token = await solver.solve_recaptcha_v2(sitekey, str(r_get.url)) if sitekey else ""

        soup = BeautifulSoup(r_get.text, "html.parser")
        datos = serializar_form(soup)
        datos.update({"dominio": patente, "patente": patente, "actas": "transito", "tipo_consulta": "P", "g-recaptcha-response": token})
        form = soup.find("form")
        destino = urljoin(str(r_get.url), form["action"]) if (form and form.get("action")) else url_post
        r_post = await client.post(destino, data=datos, headers={"Referer": url_web})
        return interpretar_respuesta(r_post)


# --- CONECTOR DEDICADO 6: VICENTE LÓPEZ ---
async def http_vicente_lopez(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    url_web = "https://infracciones.vicentelopez.gov.ar/causas-vecino"
    async with nuevo_cliente(50) as client:
        r_get = await client.get(url_web)
        if r_get.status_code >= 400:
            return interpretar_respuesta(r_get)
        ts_key = _buscar_turnstile_en_texto(r_get.text)
        if not ts_key:
            raise ConsultaIndeterminada("No se encontró Cloudflare Turnstile.", r_get.status_code)
        token = await solver.solve_turnstile(ts_key, url_web)
        r_res = await client.get(url_web, params={"domain_or_document": patente, "cf-turnstile-response": token}, headers={"Referer": url_web})
        return interpretar_respuesta(r_res)


# --- CONECTOR DEDICADO 7: SANTA FE OCR ---
async def http_santafe_ocr(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    url_inicio = "https://www.santafe.gov.ar/juzgadovirtual/consultaInfraccion.do?method=inicio"
    url_busq = "https://www.santafe.gov.ar/juzgadovirtual/consultaInfraccion.do?method=BusquedaVehiculo"
    async with nuevo_cliente(45) as client:
        r_get = await client.get(url_inicio)
        if r_get.status_code >= 400:
            return interpretar_respuesta(r_get)
        soup = BeautifulSoup(r_get.text, "html.parser")
        datos = serializar_form(soup)
        img_tag = soup.find("img", src=re.compile(r"captcha|jcaptcha|imagen", re.I))
        if img_tag and img_tag.get("src"):
            r_img = await client.get(urljoin(str(r_get.url), img_tag["src"]))
            if r_img.status_code == 200 and r_img.content:
                texto_ocr = await solver.solve_image_captcha(r_img.content)
                datos.setdefault("captcha", texto_ocr)
        datos.setdefault("dominio", patente)
        r_post = await client.post(url_busq, data=datos, headers={"Referer": str(r_get.url)})
        return interpretar_respuesta(r_post)


# =============================================================================
# 5b. EXPLORADOR
# =============================================================================
async def explorar_portal(nombre: str, url: str) -> dict:
    return {"portal": nombre, "url": url}

async def explorar_todos() -> dict:
    return {}


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
URL_SANTAFE = "https://www.santafe.gov.ar/juzgadovirtual/consultaInfraccion.do?method=inicio"
URL_VLOPEZ = "https://infracciones.vicentelopez.gov.ar/causas-vecino"

JURISDICCIONES: List[JurisdiccionConfig] = [
    JurisdiccionConfig("Posadas (Misiones)", "Sin CAPTCHA", URL_POSADAS, lambda p, s: http_formulario(URL_POSADAS, p)),
    JurisdiccionConfig("Rosario", "Sin CAPTCHA", URL_ROSARIO, lambda p, s: http_formulario(URL_ROSARIO, p)),
    JurisdiccionConfig("Lomas de Zamora", "Sin CAPTCHA", URL_LOMAS, lambda p, s: http_formulario(URL_LOMAS, p)),
    JurisdiccionConfig("PBA", "reCAPTCHA", URL_PBA, lambda p, s: http_pba_api(p, s)),
    JurisdiccionConfig("CABA", "reCAPTCHA", URL_CABA, lambda p, s: http_caba_api(p, s)),
    JurisdiccionConfig("Ezeiza", "reCAPTCHA", URL_EZEIZA, lambda p, s: http_ezeiza_api(p, s)),
    JurisdiccionConfig("Lanús", "reCAPTCHA", URL_LANUS, lambda p, s: http_lanus_api(p, s)),
    JurisdiccionConfig("Entre Ríos", "reCAPTCHA", "https://monitoreovialentrerios.info/#/consulta-infracciones", lambda p, s: http_monitoreo_vial_api(URL_ER, "https://api.monitoreovialentrerios.ar", p, s)),
    JurisdiccionConfig("Misiones", "reCAPTCHA", "https://monitoreovialmisiones.info/#/", lambda p, s: http_monitoreo_vial_api(URL_MISIONES, "https://api.monitoreovialmisiones.ar", p, s)),
    JurisdiccionConfig("Vicente López", "Cloudflare", URL_VLOPEZ, lambda p, s: http_vicente_lopez(p, s)),
    JurisdiccionConfig("Santa Fe", "CAPTCHA Texto", URL_SANTAFE, lambda p, s: http_santafe_ocr(p, s)),
    JurisdiccionConfig("Córdoba Caminera", "Sin CAPTCHA", "https://www.rentascordoba.gob.ar/emision/ver-y-pagar/caminera"),
    JurisdiccionConfig("Avellaneda", "Cloudflare", "https://multas.mda.gob.ar"),
]

PALETA = ["#e6c56a", "#6cb6ff", "#b79bff", "#5fd8a0", "#ff9a7a", "#ff8fc4", "#5fd6d6", "#d4b98a"]


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
    textos = ["Circular por zona/carril prohibido", "Estac. lugar sin ticket/hora vencida", "Exceso de velocidad"]
    return [
        Infraccion(
            acta=f"{rnd.choice('QIAF')}{rnd.randint(10_000_000, 99_999_999)}",
            descripcion=rnd.choice(textos),
            monto=float(rnd.randint(40, 600) * 1000),
            controlador=rnd.random() < 0.3,
        )
        for _ in range(rnd.randint(1, 3))
    ]


async def _consultar_una(cfg: JurisdiccionConfig, patente: str, demo: bool, solver: CaptchaSolver) -> ResultadoJurisdiccion:
    r = ResultadoJurisdiccion(cfg.nombre, cfg.proteccion, cfg.url)
    if demo:
        await asyncio.sleep(0.3)
        r.infracciones = _demo_infracciones(patente, cfg.nombre)
        r.estado = "con_multas" if r.infracciones else "sin_multas"
        r.demo = True
        return r
    if cfg.consultar is None:
        r.estado = "sin_conector"
        r.detalle = f"Sin consulta automática ({cfg.proteccion})."
        return r
    try:
        resp = await asyncio.wait_for(cfg.consultar(patente, solver), timeout=150)
        r.infracciones = resp.infracciones
        r.http_status = resp.http_status
        r.muestra = resp.muestra
        r.estado = "con_multas" if resp.infracciones else "sin_multas"
    except CaptchaError as exc:
        r.estado, r.detalle = "captcha_fallido", str(exc)
    except ConsultaIndeterminada as exc:
        r.estado, r.detalle = "indeterminado", str(exc)
        r.http_status, r.muestra = exc.http_status, exc.muestra
    except Exception as exc:
        r.estado, r.detalle = "error", f"{type(exc).__name__}: {exc}"
    return r


async def ejecutar_consultas(patente, lista, demo, solver, on_progress) -> List[ResultadoJurisdiccion]:
    tareas = [asyncio.create_task(_consultar_una(j, patente, demo, solver)) for j in lista]
    resultados = []
    total = len(tareas)
    for hecha in asyncio.as_completed(tareas):
        r = await hecha
        resultados.append(r)
        on_progress(len(resultados), total, r.nombre)
    orden = {j.nombre: i for i, j in enumerate(JURISDICCIONES)}
    return sorted(resultados, key=lambda x: orden[x.nombre])


def resumen_json(patente: str, resultados: List[ResultadoJurisdiccion]) -> dict:
    fallos = [r.nombre for r in resultados if r.estado in ESTADOS_FALLO]
    manuales = [r.nombre for r in resultados if r.estado == "sin_conector"]
    todas = [i for r in resultados for i in r.infracciones]
    total = round(sum(r.subtotal for r in resultados), 2)
    ordenados = sorted(resultados, key=lambda r: (r.estado != "con_multas", -r.subtotal))
    return {
        "patente": patente,
        "consultado_en": datetime.now(TZ_AR).isoformat(timespec="seconds"),
        "total_general": total,
        "total_infracciones": len(todas),
        "detalle": [{"jurisdiccion": r.nombre, "estado": r.estado, "subtotal": round(r.subtotal, 2), "infracciones": [{"acta": i.acta, "monto": i.monto} for i in r.infracciones]} for r in ordenados]
    }


def overlay(pct: int, estado: str) -> str:
    return (
        '<div class="ov"><div class="ovc">'
        '<div class="spin"></div>'
        '<h2>BUSCANDO MULTAS…</h2>'
        f'<div class="st">{html.escape(estado)}</div>'
        f'<div class="bar"><div style="width:{max(pct, 6)}%"></div></div>'
        '</div></div>'
    )


def _secret(nombre: str) -> str:
    try:
        return str(st.secrets.get(nombre, "") or "")
    except Exception:
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
    '<p class="lead">Consultá infracciones de tránsito por patente en todas las jurisdicciones disponibles.</p>'
    '</div>'
    '<div class="stats">'
    '<div class="stat"><b>+5K</b><span>Trámites</span></div>'
    '<div class="stat"><b>24H</b><span>Atención</span></div>'
    '<div class="stat"><b>100%</b><span>Online</span></div>'
    '</div></div>'
    '<div id="buscador"></div>',
    unsafe_allow_html=True,
)

with st.form("buscador", clear_on_submit=False, border=True):
    patente_input = st.text_input("Patente", placeholder="Ingresá tu patente (ej. LVQ189)", max_chars=10)
    c1, c2 = st.columns([3, 1])
    with c1:
        modo = st.selectbox("Jurisdicciones", ["Todas", "Solo sin CAPTCHA", "Solo con CAPTCHA / Cloudflare"], label_visibility="collapsed")
    with c2:
        enviar = st.form_submit_button("🔎  Consultar", use_container_width=True)

with st.expander("⚙️ Opciones de desarrollo y Captcha"):
    col_p, col_k = st.columns([1, 2])
    with col_p:
        proveedor_captcha = st.selectbox("Proveedor", ["capsolver", "2captcha"])
    with col_k:
        clave_defecto = _secret("CAPSOLVER_API_KEY") or _secret("CAPTCHA_API_KEY") or os.getenv("CAPSOLVER_API_KEY", "")
        api_key_captcha = st.text_input("API Key del Captcha pago", value=clave_defecto, type="password")
    demo = st.checkbox("Modo demo (datos SIMULADOS)", value=False)

if enviar:
    dominio = normalizar_patente(patente_input)
    if not PATRON_PATENTE.match(dominio):
        st.error("Formato de patente inválido.")
    else:
        lista = JURISDICCIONES
        solver = CaptchaSolver(proveedor_captcha, api_key_captcha)
        ph = st.empty()
        ph.markdown(overlay(0, "Preparando consulta"), unsafe_allow_html=True)
        res = asyncio.run(ejecutar_consultas(dominio, lista, demo, solver, lambda h, t, n: ph.markdown(overlay(int(h/t*100), f"Consultado: {n}"), unsafe_allow_html=True)))
        ph.empty()
        st.session_state["resultados"] = res
        st.session_state["patente"] = dominio

if "resultados" in st.session_state:
    resultados = st.session_state["resultados"]
    dominio = st.session_state["patente"]
    con_multas = [r for r in resultados if r.estado == "con_multas"]
    total = sum(r.subtotal for r in con_multas)
    n_multas = sum(len(r.infracciones) for r in con_multas)
    st.markdown(f"<h2>Resultado para {dominio} — Total: {pesos(total)}</h2>", unsafe_allow_html=True)
    for i, r in enumerate(con_multas):
        st.markdown(f"### {r.nombre} ({pesos(r.subtotal)})")
        for inf in r.infracciones:
            st.write(f"- Acta: {inf.acta} | {inf.descripcion} | {pesos(inf.monto)}")
    
    filas_p = "".join(f'<tr><td>{r.nombre}</td><td>{r.estado}</td><td>{r.detalle or "—"}</td></tr>' for r in resultados)
    st.markdown(f"<table><tr><th>Jurisdicción</th><th>Estado</th><th>Detalle</th></tr>{filas_p}</table>", unsafe_allow_html=True)
