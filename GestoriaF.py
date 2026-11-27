# -*- coding: utf-8 -*-
"""
Marcelo Nuñez Gestiones | Buscador de infracciones por patente
Interfaz Streamlit conectada a los módulos de core/ y conectores/.
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
from datetime import datetime
from pathlib import Path
from typing import List
from urllib.parse import quote

import httpx
import streamlit as st

from conectores.avellaneda import URL_AVELLANEDA_API, consultar_avellaneda
from conectores.base import nuevo_cliente
from conectores.caba import URL_CABA, consultar_caba
from conectores.entre_rios import API_ENTRE_RIOS, URL_ENTRE_RIOS, consultar_entre_rios
from conectores.lomas import URL_LOMAS, consultar_lomas
from conectores.pba import URL_PBA, URL_PBA_API, consultar_pba
from conectores.vicente_lopez import URL_VL, URL_VL_DATOS, consultar_vicente_lopez
from core.captcha import CaptchaSolver, SimulacroListo, SolverSimulacro
from core.modelos import (
    ESTADO_UI,
    ESTADOS_FALLO,
    ESTADOS_OK,
    CaptchaError,
    ConsultaIndeterminada,
    Infraccion,
    JurisdiccionConfig,
    RespuestaPortal,
    ResultadoJurisdiccion,
)
from core.parser import TZ_AR

# =============================================================================
# 0. DATOS DE MARCA Y CONFIGURACIÓN
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


def _secret(nombre: str) -> str:
    try:
        return str(st.secrets.get(nombre, "") or "")
    except Exception:  # noqa: BLE001
        return ""


# Sincroniza sitekeys opcionales de Streamlit Secrets hacia variables de entorno
for _env_key in ("SITEKEY_CABA", "SITEKEY_PBA", "SITEKEY_ENTRERIOS", "SITEKEY_VL"):
    _val = _secret(_env_key)
    if _val and not os.getenv(_env_key):
        os.environ[_env_key] = _val


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
.block-container{ max-width:1080px; padding-top:.6rem; padding-bottom:7rem; }
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
.btn.wa{ background:#22c55e; border-color:#22c55e; color:#04210f !important; box-shadow:0 8px 22px rgba(34,197,94,.3); }

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

/* ---------- SECCIONES Y FORMULARIO ---------- */
.sec-title{ font-family:'Bebas Neue'; font-size:2.2rem; color:#fff; margin:1.8rem 0 .2rem; }
.sec-title em{ color:var(--gold); font-style:normal; }
.sec-sub{ color:var(--mut); font-size:.9rem; margin-bottom:.9rem; }
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

/* ---------- RESULTADOS Y TABLAS ---------- */
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
.card .tablewrap{ background:#fff; border:1px solid #e6e1d2; border-left:8px solid var(--acc,#e6c56a);
  border-radius:14px; overflow-x:auto; }
table.t{ width:100%; border-collapse:collapse; font-size:.93rem; }
table.t th{ background:var(--acc-soft,#f4f0e3); color:#3b4258; font-size:.68rem; letter-spacing:.14em;
  text-transform:uppercase; padding:.7rem; text-align:center; font-weight:700; }
table.t td{ padding:.75rem; text-align:center; color:#0b1430; border-bottom:1px solid #eee9da; }
table.t tbody tr:nth-child(odd) td{ background:#fff; }
table.t tbody tr:nth-child(even) td{ background:#faf7ee; }
table.t tfoot td{ background:var(--acc-soft,#f5f1e3); font-weight:800; color:#0b1430; border-bottom:0; }
table.t td.l{ text-align:left; }
table.t td.r{ text-align:right; }
.tag{ display:inline-block; background:linear-gradient(135deg,#7c3aed,#5b21b6); color:#fff; font-size:.6rem; font-weight:800;
  padding:4px 10px; border-radius:999px; margin-bottom:4px; letter-spacing:.04em; }
.tag.pv{ background:linear-gradient(135deg,#dc2626,#991b1b); }
.warn{ background:rgba(251,146,60,.1); border:1px solid rgba(251,146,60,.4); color:#fdba74; border-radius:12px;
  padding:.85rem 1rem; font-size:.9rem; margin-top:1rem; }
.ok{ background:rgba(74,222,128,.1); border:1px solid rgba(74,222,128,.4); color:#86efac; border-radius:12px;
  padding:.85rem 1rem; font-size:.92rem; margin-top:1rem; }
.card a.portal{ color:#1d4ed8 !important; font-weight:600; text-decoration:none; }
.est{ display:inline-block; border-radius:999px; padding:3px 10px; font-size:.7rem; font-weight:800; }
.card .est.good{ background:#dcfce7; color:#14663a; }
.card .est.bad{ background:#fee2e2; color:#991b1b; }
.card .est.warn{ background:#fef3c7; color:#92400e; }
.card .est.neutral{ background:#e5e7eb; color:#374151; }

/* Resumen flotante */
.float{ position:static; width:auto; margin-top:1rem; background:#0f1830; z-index:50; border-radius:18px;
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
@media (min-width:1640px){ .float{ position:fixed; top:90px; left:calc(50% + 556px); right:auto; width:255px; margin-top:0; } }

/* ---------- PUBLICIDAD / CTA / PIE ---------- */
.totalbar{ display:flex; justify-content:space-between; align-items:center; background:#0f1830; border:1px solid var(--gold);
  color:#fff; border-radius:16px; padding:1rem 1.4rem; margin-top:1.2rem; font-weight:700; letter-spacing:.06em; }
.totalbar b{ font-family:'Bebas Neue'; font-size:2.1rem; color:var(--gold2); letter-spacing:.04em; font-weight:400; }
.cta-box{ background:linear-gradient(135deg, rgba(201,168,76,.2), rgba(17,26,51,.95)); border:1px solid var(--gold);
  border-radius:18px; padding:1.6rem; margin-top:1.4rem; text-align:center; }
.cta-box h3{ font-size:2.2rem; color:#fff; margin:0 0 .3rem; }
.cta-box p{ color:#c3cce0; margin:0 0 1rem; }
.cta-box .btn{ font-size:1.05rem; padding:.9rem 1.6rem; border-radius:10px; }
.sticky-wa{ position:fixed; left:18px; right:18px; bottom:56px; z-index:999; background:#0f1830; color:#fff;
  border:1.5px solid #22c55e; border-radius:16px; padding:.95rem 1.4rem; display:flex; justify-content:space-between;
  align-items:center; gap:1rem; box-shadow:0 12px 32px rgba(0,0,0,.65); font-weight:700; font-size:1rem; }
.sticky-wa .btn.wa{ font-size:.98rem; padding:.75rem 1.35rem; border-radius:10px; white-space:nowrap; }
.servicios{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-top:.8rem; }
.serv{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:.9rem .6rem; text-align:center;
  font-size:.82rem; font-weight:600; color:#e8ecf5; }
.foot{ border-top:1px solid rgba(255,255,255,.07); margin-top:2.2rem; padding-top:1.2rem; color:var(--mut);
  font-size:.78rem; text-align:center; line-height:1.6; }

/* ---------- OVERLAY Y TABLERO DE SERVIDORES ---------- */
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

@media (max-width:900px){
  .hero{ grid-template-columns:1fr; } .stats{ flex-direction:row; } .stat{ flex:1; padding:.7rem .3rem; }
  .stat b{ font-size:1.8rem; } .kpis{ grid-template-columns:repeat(2,1fr); } .servicios{ grid-template-columns:repeat(2,1fr); }
  .res-head h2{ font-size:2.2rem; } .sticky-wa{ flex-direction:column; text-align:center; gap:.5rem; padding:.6rem; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# =============================================================================
# 2. REGISTRO DE JURISDICCIONES (conectadas a conectores/)
# =============================================================================
JURISDICCIONES: List[JurisdiccionConfig] = [
    # --- 6 JURISDICCIONES AUTOMÁTICAS ---
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
    # --- CONSULTA MANUAL (acceso directo al portal oficial) ---
    JurisdiccionConfig("Posadas (Misiones)", "Sin CAPTCHA", "https://sistema.posadas.gov.ar/mp_sistemas/autogestion/consultarmultadominio"),
    JurisdiccionConfig("Rosario", "Sin CAPTCHA", "https://www.rosario.gob.ar/gdm/patente.do?accion=ir"),
    JurisdiccionConfig("Ezeiza", "reCAPTCHA", "https://consulta-web.infratrack.com.ar/consultas.php?municipio=ezeiza"),
    JurisdiccionConfig("Misiones", "CAPTCHA", "https://monitoreovialmisiones.info/#/"),
    JurisdiccionConfig("Lanús", "reCAPTCHA", "https://tramitesweb.lanus.gob.ar/lanusdigital/mis-dominios"),
    JurisdiccionConfig("Córdoba Caminera", "Sin CAPTCHA", "https://www.rentascordoba.gob.ar/emision/ver-y-pagar/caminera"),
    JurisdiccionConfig("Santa Fe", "CAPTCHA Texto", "https://www.santafe.gov.ar/juzgadovirtual/consultaInfraccion.do?method=BusquedaVehiculo"),
]

_activas_env = _secret("PORTALES_ACTIVOS") or os.getenv("PORTALES_ACTIVOS", "")
ACTIVAS = {
    x.strip()
    for x in (_activas_env or "CABA,PBA,Entre Ríos,Avellaneda,Lomas de Zamora,Vicente López").split(",")
    if x.strip()
}
for _j in JURISDICCIONES:
    if _j.nombre not in ACTIVAS:
        _j.consultar_pausado, _j.consultar = _j.consultar, None

PALETA = ["#e6c56a", "#6cb6ff", "#b79bff", "#5fd8a0", "#ff9a7a", "#ff8fc4", "#5fd6d6", "#d4b98a"]


def color_de(nombre: str) -> str:
    idx = [j.nombre for j in JURISDICCIONES].index(nombre) % len(PALETA)
    return PALETA[idx]


# =============================================================================
# 3. MOTOR DE EJECUCIÓN, CACHÉ Y TABLERO DE SERVIDORES
# =============================================================================
PATRON_PATENTE = re.compile(r"^([A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2}|[A-Z]\d{3}[A-Z]{3}|\d{3}[A-Z]{3})$")
CACHE_TTL_SEG = 600


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
    textos = [
        "Circular por zona/carril prohibido",
        "Estac. lugar sin ticket/hora vencida",
        "No uso cinturón de seguridad",
        "Exceso de velocidad",
        "Cruzar semáforo en rojo",
    ]
    return [
        Infraccion(
            acta=f"{rnd.choice('QIAF')}{rnd.randint(10_000_000, 99_999_999)}",
            descripcion=rnd.choice(textos),
            monto=float(rnd.randint(40, 600) * 1000) + rnd.choice([0, 0, 62]),
            controlador=rnd.random() < 0.3,
        )
        for _ in range(rnd.randint(1, 4))
    ]


async def _consultar_una(
    cfg: JurisdiccionConfig,
    patente: str,
    demo: bool,
    solver: CaptchaSolver,
) -> ResultadoJurisdiccion:
    r = ResultadoJurisdiccion(cfg.nombre, cfg.proteccion, cfg.url)

    if demo:
        await asyncio.sleep(random.uniform(0.2, 0.7))
        r.infracciones = _demo_infracciones(patente, cfg.nombre)
        r.estado = "con_multas" if r.infracciones else "sin_multas"
        r.demo = True
        return r

    if cfg.consultar is None:
        r.estado = "sin_conector"
        r.detalle = "Consulta automática próximamente. Podés abrir el portal oficial."
        return r

    try:
        resp: RespuestaPortal | None = None
        for intento in (1, 2):
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
        r.total_oficial, r.declaradas = resp.total_oficial, resp.declaradas
        r.nota, r.vigencia = resp.nota, resp.vigencia
        r.estado = "con_multas" if resp.infracciones else "sin_multas"
    except SimulacroListo as exc:
        r.estado, r.detalle = "simulacro", str(exc)
    except CaptchaError as exc:
        r.estado, r.detalle = "captcha_fallido", str(exc)
    except ConsultaIndeterminada as exc:
        r.estado, r.detalle = "indeterminado", str(exc)
        r.http_status, r.muestra = exc.http_status, exc.muestra
    except asyncio.TimeoutError:
        r.estado, r.detalle = "error", "Timeout: el portal no respondió a tiempo"
    except Exception as exc:  # noqa: BLE001
        r.estado, r.detalle = "error", f"{type(exc).__name__}: {exc}"
        r.muestra = traceback.format_exc()[-1800:]

    if solver.api_key and len(solver.api_key) >= 12:
        r.detalle = r.detalle.replace(solver.api_key, "***")
        r.muestra = r.muestra.replace(solver.api_key, "***")
    return r


async def _chequear_url(url: str, permisivo: bool, timeout: int = 8) -> tuple[str, int, str]:
    t0 = time.monotonic()
    ultimo = ""
    for _ in range(2):
        try:
            async with nuevo_cliente(timeout) as c:
                r = await c.get(url)
            ms = int((time.monotonic() - t0) * 1000)
            if permisivo or r.status_code < 400:
                return "ok", ms, str(r.status_code)
            if r.status_code in (403, 429):
                return "bloqueado", ms, str(r.status_code)
            if r.status_code >= 500:
                return "caido", ms, str(r.status_code)
            return "ok", ms, str(r.status_code)
        except Exception as exc:  # noqa: BLE001
            ultimo = type(exc).__name__
    return "caido", int((time.monotonic() - t0) * 1000), ultimo


async def _chequear_portal(cfg: JurisdiccionConfig) -> dict:
    urls = cfg.urls_chequeo or ((cfg.url.split("#")[0], False),)
    res = await asyncio.gather(*(_chequear_url(u, perm) for u, perm in urls))
    peso = {"ok": 0, "bloqueado": 1, "caido": 2}
    peor = max(res, key=lambda x: peso[x[0]])
    return {"nombre": cfg.nombre, "estado": peor[0], "ms": max(x[1] for x in res), "detalle": peor[2]}


async def _chequear_todos(cfgs: List[JurisdiccionConfig]) -> list[dict]:
    return list(await asyncio.gather(*(_chequear_portal(c) for c in cfgs)))


@st.cache_data(ttl=120, show_spinner=False)
def estado_servidores(nombres: tuple) -> list[dict]:
    cfgs = [j for j in JURISDICCIONES if j.nombre in nombres]
    return asyncio.run(_chequear_todos(cfgs))


def tablero_servidores(estados: list[dict]) -> str:
    por = {e["nombre"]: e for e in estados}
    chips = ""
    for j in JURISDICCIONES:
        if j.consultar is None:
            chips += f'<span class="srv idle"><i></i>{html.escape(j.nombre)}<small>Próximamente</small></span>'
            continue
        e = por.get(j.nombre)
        est = e["estado"] if e else "pendiente"
        clase = {"ok": "ok", "caido": "down", "bloqueado": "warn"}.get(est, "idle")
        etiqueta = {"ok": f'{e["ms"]} ms' if e else "", "caido": "Caído", "bloqueado": "Bloqueado"}.get(est, "…")
        chips += f'<span class="srv {clase}"><i></i>{html.escape(j.nombre)}<small>{etiqueta}</small></span>'
    hora = datetime.now(TZ_AR).strftime("%H:%M")
    return (
        f'<div class="srvhead"><b>ESTADO DE LOS SERVIDORES</b><span>Actualizado {hora} · '
        '<i class="g"></i> activo &nbsp;<i class="r"></i> caído &nbsp;<i class="a"></i> bloqueado</span></div>'
        f'<div class="servers">{chips}</div>'
    )


@st.cache_resource
def _cache_global() -> dict:
    return {}


def _cache_leer(nombre: str, patente: str) -> ResultadoJurisdiccion | None:
    item = _cache_global().get((nombre, patente))
    if item and time.time() - item[0] < CACHE_TTL_SEG:
        r = copy.deepcopy(item[1])
        r.desde_cache = True
        return r
    return None


def _cache_guardar(r: ResultadoJurisdiccion, patente: str) -> None:
    if r.estado in ESTADOS_OK and not r.demo:
        _cache_global()[(r.nombre, patente)] = (time.time(), copy.deepcopy(r))


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


def detalle_visible(r: ResultadoJurisdiccion, tecnico: bool) -> str:
    if tecnico or r.estado not in ESTADOS_FALLO:
        return r.detalle
    d = r.detalle
    if r.estado == "caido":
        return "El servidor del portal no responde en este momento."
    if r.estado == "captcha_fallido":
        return "No se pudo validar la verificación anti-robot del portal."
    if re.search(r"HTTP 5\d\d", d):
        return "El portal informa un error interno."
    if re.search(r"HTTP 40[13]|HTTP 429|bloqueo", d):
        return "El portal rechazó la consulta (acceso restringido)."
    if re.search(r"[Tt]imeout", d):
        return "El portal tardó demasiado en responder."
    if re.search(r"Connect|Name or service|SSL|Remote|Read", d):
        return "No se pudo conectar con el portal."
    if r.estado == "indeterminado":
        return "El portal respondió en un formato que todavía no se reconoce."
    return "No disponible en este momento. Podés consultarlo en el portal oficial."


def resumen_json(patente: str, resultados: List[ResultadoJurisdiccion], tecnico: bool = False) -> dict:
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
        mensaje = (
            "No se encontraron multas en los portales que respondieron, pero "
            f"{len(fallos)} no pudieron consultarse: {', '.join(fallos)}."
        )
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
                {
                    "jurisdiccion": r.nombre,
                    "multas": len(r.infracciones),
                    "subtotal": round(r.subtotal, 2),
                    "subtotal_formato": pesos(r.subtotal),
                }
                for r in con
            ],
        },
        "jurisdicciones": [
            {
                "jurisdiccion": r.nombre,
                "cantidad": len(r.infracciones),
                "infracciones_declaradas_por_el_portal": r.declaradas,
                "subtotal": round(r.subtotal, 2),
                "subtotal_formato": pesos(r.subtotal),
                "suma_de_las_actas_listadas": round(r.suma_lista, 2),
                "vigente_hasta": r.vigencia or None,
                "nota": r.nota or None,
                "multas": [
                    {
                        "acta": i.acta,
                        "descripcion": i.descripcion,
                        "monto": i.monto,
                        "monto_formato": pesos(i.monto),
                        "etiquetas": i.etiquetas,
                    }
                    for i in r.infracciones
                ],
            }
            for r in con
        ],
        "sin_multas": sin_multas,
        "no_se_pudo_consultar": [
            {"jurisdiccion": r.nombre, "motivo": detalle_visible(r, tecnico)}
            for r in resultados
            if r.estado in ESTADOS_FALLO
        ],
        "consulta_manual": manuales,
    }


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


# =============================================================================
# 4. INTERFAZ WEB
# =============================================================================
n_jur = len(JURISDICCIONES)
n_auto = sum(1 for j in JURISDICCIONES if j.consultar is not None)
logo_html = (
    f'<img class="logo" src="data:image/png;base64,{LOGO_B64}" alt="Marcelo Nuñez Gestiones">'
    if LOGO_B64
    else '<div class="logo-txt">Marcelo Nuñez · GESTIONES</div>'
)
wa_hola = f"{WA_BASE}?text={quote('Hola Marcelo, quiero hacer una consulta.')}"

st.markdown(
    '<div class="topbar"><div class="brand"><b>GESTORÍA AUTOMOTOR</b><span>MARCELO NUÑEZ GESTIONES</span></div>'
    f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
    f'<a class="btn sm wa" href="{wa_hola}" target="_blank" rel="noopener">WhatsApp {WHATSAPP_TXT}</a>'
    '<a class="btn sm ghost" href="#servicios">Contacto</a></div></div>'
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
    enviar = st.form_submit_button("🔎  Consultar", use_container_width=True)

ph_servidores = st.empty()

# --- Configuración segura ---
proveedor_captcha = (_secret("CAPTCHA_PROVIDER") or os.getenv("CAPTCHA_PROVIDER", "capsolver")).lower()
api_key_captcha = _secret("CAPSOLVER_API_KEY") or os.getenv("CAPSOLVER_API_KEY", "") or os.getenv("CAPTCHA_API_KEY", "")
es_admin = bool(st.session_state.get("admin_ok"))
mostrar_diag = False
demo = False
simulacro = False
ignorar_cache = False
portales_sel: list = []

if es_admin:
    with st.expander("🔒 Panel de administración (solo vos)"):
        st.caption("Visible únicamente tras ingresar la contraseña de administrador.")
        st.write(
            f"Proveedor: **{proveedor_captcha}** · Clave cargada: **{'sí' if api_key_captcha else 'NO'}** · "
            f"Portales activos: **{', '.join(sorted(ACTIVAS))}**"
        )
        simulacro = st.checkbox("🧪 Simulacro: prueba todo SIN resolver captchas (no gasta saldo)", value=False)
        portales_sel = st.multiselect(
            "Probar solo estos portales (vacío = todos los activos)",
            [j.nombre for j in JURISDICCIONES if j.consultar is not None],
        )
        ignorar_cache = st.checkbox("Ignorar resultados guardados (vuelve a gastar captcha)", value=False)
        mostrar_diag = st.checkbox("Mostrar respuesta cruda de cada portal", value=True)
        demo = st.checkbox("Modo demo (datos SIMULADOS, solo para probar el diseño)", value=False)
        if st.button("Cerrar sesión de administrador"):
            st.session_state["admin_ok"] = False
            st.rerun()

# --- Ejecución ---
if enviar:
    dominio = normalizar_patente(patente_input)
    if not PATRON_PATENTE.match(dominio):
        st.error("Formato de patente inválido. Ejemplos: HNQ904, AB123CD, A123BCD, 123ABC.")
    else:
        activos = [j for j in JURISDICCIONES if j.consultar is not None]
        manuales = [j for j in JURISDICCIONES if j.consultar is None]
        estados: dict = {}
        caidos: list = []
        previos: dict = {}

        if demo:
            lista_red = list(JURISDICCIONES)
        else:
            elegidos = [j for j in activos if (not portales_sel or j.nombre in portales_sel)]
            try:
                estados = {e["nombre"]: e for e in estado_servidores(tuple(j.nombre for j in activos))}
            except Exception:  # noqa: BLE001
                estados = {}
            caidos = [j for j in elegidos if estados.get(j.nombre, {}).get("estado") == "caido"]
            vivos = [j for j in elegidos if j not in caidos]
            if not ignorar_cache and not simulacro:
                for j in vivos:
                    hit = _cache_leer(j.nombre, dominio)
                    if hit:
                        previos[j.nombre] = hit
            lista_red = [j for j in vivos if j.nombre not in previos] + manuales

        solver = SolverSimulacro() if simulacro else CaptchaSolver(proveedor_captcha, api_key_captcha)
        res_nuevos: List[ResultadoJurisdiccion] = []
        if lista_red:
            ph = st.empty()
            ph.markdown(overlay(0, "Preparando consulta"), unsafe_allow_html=True)

            def _progreso(hechas: int, total: int, nombre: str) -> None:
                ph.markdown(
                    overlay(int(hechas / total * 100), f"Consultado: {nombre} ({hechas}/{total})"),
                    unsafe_allow_html=True,
                )

            res_nuevos = asyncio.run(ejecutar_consultas(dominio, lista_red, demo, solver, _progreso))
            ph.empty()

        if not demo and not simulacro:
            for r_ in res_nuevos:
                _cache_guardar(r_, dominio)

        res_caidos = [
            ResultadoJurisdiccion(
                j.nombre,
                j.proteccion,
                j.url,
                estado="caido",
                detalle=f"El chequeo previo falló ({estados.get(j.nombre, {}).get('detalle', '')})",
            )
            for j in caidos
        ]
        orden = {j.nombre: i for i, j in enumerate(JURISDICCIONES)}
        res = sorted(list(previos.values()) + res_nuevos + res_caidos, key=lambda x: orden[x.nombre])
        st.session_state["resultados"] = res
        st.session_state["patente"] = dominio

# --- Resultados ---
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
        sub_float = "-" if (r.nombre == "Lomas de Zamora" and r.subtotal == 0) else pesos(r.subtotal)
        filas += (
            f'<div class="row" style="background:{c}1f;border-color:{c}66">'
            f'<span style="color:{c}">{html.escape(r.nombre.upper()[:9])}</span>'
            f'<span class="m"><small>{n} multa{"s" if n != 1 else ""}</small>{sub_float}</span></div>'
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
    chips_bloque = f'<div style="margin-top:1rem">{jchips}</div>' if con_multas else ""
    st.markdown(
        '<div class="res-head"><h2>RESULTADO DE LA BÚSQUEDA</h2>'
        f'<div class="plate">{html.escape(dominio)}</div>'
        f'<div class="sec-sub" style="margin:0">{intro}</div>'
        '<div class="kpis">'
        f'<div class="kpi"><b>{pesos(total)}</b><span>Total general</span></div>'
        f'<div class="kpi"><b>{n_multas}</b><span>Multas encontradas</span></div>'
        f'<div class="kpi"><b>{len(con_multas)}</b><span>Jurisdicciones con multas</span></div>'
        f'<div class="kpi"><b>{estado_txt}</b><span>Consulta ({len(consultados_ok)}/{len(resultados) - len(manuales)} portales)</span></div>'
        f'</div>{chips_bloque}</div>',
        unsafe_allow_html=True,
    )

    if hay_demo:
        st.markdown(
            '<div class="warn">⚠️ <b>Modo demo:</b> los datos mostrados son simulados, no corresponden a multas reales.</div>',
            unsafe_allow_html=True,
        )

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
            monto_td = "Ver comprobante" if (r.nombre == "Lomas de Zamora" and inf.monto is None) else pesos(inf.monto)
            filas_t += (
                f"<tr><td>{html.escape(inf.acta)}</td>"
                f'<td class="l">{tag}{html.escape(inf.descripcion)}</td>'
                f"<td>{monto_td}</td></tr>"
            )
        etiqueta_sub = (
            "Monto total informado por el portal"
            if r.total_oficial is not None
            else f"Subtotal {html.escape(r.nombre)}"
        )
        notas = []
        if r.total_oficial is not None and abs(r.total_oficial - r.suma_lista) > 1:
            vig = f", vigente hasta {html.escape(r.vigencia)}" if r.vigencia else ""
            notas.append(
                f"Suma de las actas listadas: {pesos(r.suma_lista)}. "
                f"El portal informa {pesos(r.total_oficial)}{vig} (puede incluir descuentos por pago voluntario)."
            )
        if r.nota:
            notas.append(html.escape(r.nota))
        if r.declaradas is not None and r.declaradas != len(r.infracciones):
            notas.append(f"⚠️ El portal informa {r.declaradas} infracciones y se leyeron {len(r.infracciones)}.")
        if r.desde_cache:
            notas.append("Resultado guardado hace menos de 10 minutos.")
        nota_html = "".join(f'<div class="nota">{n_}</div>' for n_ in notas)
        st.markdown(
            f'<div class="card" id="j{i}" style="--acc:{c};--acc-soft:{c}38">'
            f'<h3><i style="background:{c}"></i>MULTAS {html.escape(r.nombre.upper())}'
            f'<small>{len(r.infracciones)} · {pesos(r.subtotal)}</small></h3>'
            '<div class="tablewrap"><table class="t"><thead><tr><th>N° Acta</th><th>Descripción</th><th>Monto</th></tr></thead>'
            f'<tbody>{filas_t}</tbody><tfoot><tr><td colspan="2" class="r">{etiqueta_sub}</td>'
            f'<td>{pesos(r.subtotal)}</td></tr></tfoot></table></div>{nota_html}</div>',
            unsafe_allow_html=True,
        )

    if con_multas:
        st.markdown(
            f'<div class="totalbar"><span>TOTAL GENERAL · {n_multas} MULTA{"S" if n_multas != 1 else ""}</span>'
            f'<b>{pesos(total)}</b></div>',
            unsafe_allow_html=True,
        )

    if consultados_ok and not con_multas and not parcial:
        st.markdown(
            f'<div class="ok">✅ La patente {html.escape(dominio)} no registra infracciones en las jurisdicciones consultadas automáticamente.</div>',
            unsafe_allow_html=True,
        )

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

    # CTA a WhatsApp
    if con_multas and not hay_demo:
        msg = (
            f"Hola Marcelo, consulté la patente {dominio} en tu buscador y tiene {n_multas} multa(s) por "
            f"{pesos(total)}. Quiero que me ayudes a gestionarlas."
        )
        st.markdown(
            '<div class="cta-box"><h3>¿TENÉS MULTAS? LAS GESTIONAMOS POR VOS</h3>'
            '<p>Descargos, fotomultas y pagos. Atención personalizada, 100% online.</p>'
            f'<a class="btn" href="{WA_BASE}?text={quote(msg)}" target="_blank" rel="noopener">Hablar por WhatsApp ahora</a></div>'
            '<div class="sticky-wa"><span>¿Querés sacarte estas multas de encima? Te ayudamos.</span>'
            f'<a class="btn wa" href="{WA_BASE}?text={quote(msg)}" target="_blank" rel="noopener">Hablar por WhatsApp</a></div>',
            unsafe_allow_html=True,
        )

    # Resumen en JSON
    datos_json = resumen_json(dominio, resultados, tecnico=es_admin)
    texto_json = json.dumps(datos_json, ensure_ascii=False, indent=2)
    with st.expander("📦 Resumen en JSON", expanded=False):
        st.code(texto_json, language="json")
        st.download_button(
            "⬇️ Descargar JSON",
            data=texto_json,
            file_name=f"infracciones_{dominio}.json",
            mime="application/json",
        )

    # Diagnóstico admin
    if es_admin and mostrar_diag:
        with st.expander("🛠️ Respuesta cruda de cada portal (solo admin)", expanded=False):
            for r in resultados:
                if not r.muestra and not r.detalle:
                    continue
                st.markdown(f"**{r.nombre}** — {ESTADO_UI.get(r.estado, (r.estado,))[0]} · HTTP {r.http_status or '—'}")
                if r.detalle:
                    st.caption(r.detalle)
                if r.muestra:
                    st.code(r.muestra, language="json" if r.muestra.lstrip().startswith(("{", "[")) else "text")

# --- Tablero de servidores ---
try:
    _estados_tab = estado_servidores(tuple(j.nombre for j in JURISDICCIONES if j.consultar is not None))
except Exception:  # noqa: BLE001
    _estados_tab = []
ph_servidores.markdown(tablero_servidores(_estados_tab), unsafe_allow_html=True)

# --- Acceso administrador (?admin=1) ---
if (not es_admin) and _secret("ADMIN_PASSWORD") and st.query_params.get("admin") == "1":
    with st.form("login_admin"):
        pwd = st.text_input("Contraseña de administrador", type="password")
        if st.form_submit_button("Ingresar"):
            if hmac.compare_digest(pwd.encode(), _secret("ADMIN_PASSWORD").encode()):
                st.session_state["admin_ok"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")

# --- Servicios y pie ---
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