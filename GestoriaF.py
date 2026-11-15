# -*- coding: utf-8 -*-
"""
Gestoría Integral | Buscador de infracciones por patente (Streamlit + HTTP directo + CapSolver)
Ejecutar con:   streamlit run GestoriaF.py
Requisitos:     pip install streamlit httpx beautifulsoup4

Cambios clave respecto a la versión anterior:
  * Cada portal devuelve un ESTADO explícito (con_multas / sin_multas / error /
    captcha_fallido / indeterminado / sin_conector). Ya no se confunde "no pude leer
    el portal" con "no tiene multas".
  * El parser ignora <script>/<style>, detecta columnas por encabezado y soporta JSON.
  * Se valida el formulario ANTES de gastar un captcha (si el portal es una SPA sin
    formulario, no se consume saldo de CapSolver).
  * El sitekey también se busca dentro de los .js del portal (SPAs).
  * Timeouts coherentes con el tiempo de resolución del captcha.
  * El total se marca como PARCIAL si algún portal falló.
  * Resumen en JSON (con descarga) y panel de diagnóstico por portal.
"""
from __future__ import annotations

import asyncio
import html
import json
import os
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, List
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import httpx
import streamlit as st
from bs4 import BeautifulSoup

# =============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# =============================================================================
st.set_page_config(
    page_title="Buscar infracciones por patente",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;800;900&display=swap');

html, body, [class*="css"], .stApp, input, button { font-family: 'Rubik', sans-serif !important; }
.stApp { background: #f7f6f2; color: #0f172a; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
.block-container { max-width: 1080px; padding-top: 1.2rem; padding-bottom: 4rem; }
#MainMenu, footer { visibility: hidden; }

/* ---------- HERO ---------- */
.hero {
  background: linear-gradient(135deg, #ffe45c 0%, #fff0a0 55%, #f8eeb0 100%);
  border: 1px solid #ecd45a; border-radius: 28px; padding: 2rem 2rem 1.6rem;
  margin-bottom: 1rem;
}
.hero h1 { font-weight: 900; font-size: 3rem; line-height: 1.02; letter-spacing: -0.03em;
  color: #0b1220; margin: 0 0 .8rem 0; }
.hero p.lead { color: #3b3a2f; font-size: 1.02rem; margin: 0 0 1rem 0; font-weight: 500; }
.pill { display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,.55);
  border: 1px solid rgba(0,0,0,.06); border-radius: 999px; padding: 7px 14px;
  font-size: .8rem; font-weight: 700; color: #111827; margin: 0 8px 8px 0; }
.panel { background: rgba(255,255,255,.55); border: 1px solid rgba(0,0,0,.06);
  border-radius: 18px; padding: 1rem 1.2rem; margin-top: .6rem; }
.panel-head { display:flex; justify-content:space-between; align-items:center; }
.panel-title { font-weight: 800; font-size: 1rem; color:#0b1220; }
.panel-tag { font-size:.72rem; font-weight:700; color:#6b6a5c; }
.panel-sub { font-size:.78rem; font-weight:700; color:#6b6a5c; margin:.35rem 0 .7rem; }
.chip { display:inline-flex; align-items:center; gap:7px; background:#fff; border-radius:999px;
  padding:7px 14px; font-size:.82rem; font-weight:500; margin:0 8px 8px 0;
  box-shadow: 0 2px 6px rgba(0,0,0,.06); }
.dot { width:8px; height:8px; border-radius:50%; background:#22c55e; display:inline-block; }
.steps { display:grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: .8rem; }
.step { background: rgba(255,255,255,.6); border: 1px solid rgba(0,0,0,.06); border-radius: 18px;
  padding: .9rem 1.1rem; }
.step b.t { display:flex; align-items:center; gap:10px; font-size:.95rem; color:#0b1220; }
.step .n { background:#ffe45c; border-radius:50%; width:26px; height:26px; display:inline-flex;
  align-items:center; justify-content:center; font-weight:800; font-size:.8rem; }
.step small { color:#6b7280; display:block; margin-top:.4rem; font-size:.78rem; }

/* ---------- BUSCADOR (st.form) ---------- */
[data-testid="stForm"] { background:#fff; border:1px solid #e7e5dc; border-radius: 24px;
  padding: 1.1rem 1.3rem; box-shadow: 0 6px 20px rgba(0,0,0,.04); }
[data-testid="stForm"] label p { font-weight: 800; font-size: 1.05rem; color:#0b1220; }
[data-testid="stForm"] input { border-radius: 14px !important; background:#fff !important;
  color:#0f172a !important; text-transform: uppercase; letter-spacing:.04em; }
[data-testid="stForm"] [data-baseweb="input"] { border-radius: 14px; border:1px solid #d9d7cc;
  background:#fff; }
[data-testid="stFormSubmitButton"] button { background: linear-gradient(135deg,#5b8def,#8db4fa);
  color:#fff; border:0; border-radius:16px; font-weight:600; height:3rem; width:100%; }
[data-testid="stFormSubmitButton"] button:hover { filter: brightness(1.05); color:#fff; }

/* ---------- RESULTADOS ---------- */
.jchip { display:inline-block; border-radius:999px; padding:8px 16px; font-weight:800;
  font-size:.78rem; margin:0 8px 8px 0; text-transform:uppercase; box-shadow:0 3px 8px rgba(0,0,0,.08);
  text-decoration:none !important; color:#111827 !important; }
.card { background:#fff; border:1px solid #e7e5dc; border-radius:22px; padding:1.2rem 1.3rem;
  margin-top:1rem; }
.card h3 { font-weight:900; font-size:1.5rem; margin:0 0 .8rem 0; color:#0b1220; display:flex;
  align-items:center; gap:10px; }
.card h3 i { width:12px; height:12px; border-radius:50%; display:inline-block; }
table.t { width:100%; border-collapse:collapse; font-size:.85rem; }
table.t th { background:#efefef; color:#6b7280; font-size:.7rem; letter-spacing:.12em;
  text-transform:uppercase; padding:.7rem; text-align:center; }
table.t td { padding:.75rem; text-align:center; color:#111827; }
table.t tr:nth-child(odd) td { background:#fffbe6; }
.tag { display:inline-block; background:linear-gradient(135deg,#7c3aed,#5b21b6); color:#fff;
  font-size:.62rem; font-weight:800; padding:4px 10px; border-radius:999px; margin-bottom:4px; }
.warn { background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; border-radius:14px;
  padding:.8rem 1rem; font-size:.88rem; margin-top:1rem; }
.ok { background:#f0fdf4; border:1px solid #bbf7d0; color:#166534; border-radius:14px;
  padding:.8rem 1rem; font-size:.9rem; margin-top:1rem; }
a.portal { color:#2563eb; font-weight:600; text-decoration:none; }
.est { display:inline-block; border-radius:999px; padding:3px 10px; font-size:.72rem; font-weight:800; }
.est.good { background:#dcfce7; color:#166534; }
.est.bad  { background:#fee2e2; color:#991b1b; }
.est.warn { background:#fef3c7; color:#92400e; }
.est.neutral { background:#e5e7eb; color:#374151; }

/* Resumen flotante */
.float { position:fixed; top:90px; right:24px; width:250px; background:#fffef8; z-index:50;
  border-radius:22px; box-shadow:0 12px 40px rgba(0,0,0,.18); padding:1rem; border:1px solid #eee7c0; }
.float .h { font-weight:800; font-size:1rem; padding-bottom:.6rem; border-bottom:1px solid #eee; }
.float .s { font-size:.65rem; letter-spacing:.14em; color:#9ca3af; font-weight:800; margin:.7rem 0 .4rem; }
.float .row { display:flex; justify-content:space-between; align-items:center; border-radius:14px;
  padding:.5rem .7rem; margin-bottom:6px; font-weight:800; font-size:.8rem; }
.float .row span.m { text-align:right; font-weight:500; font-size:.78rem; line-height:1.1; }
.float .row span.m small { display:block; color:#6b7280; font-weight:700; font-size:.65rem; }
.float .tot { border:1px solid #e5e7eb; border-radius:14px; text-align:center; padding:.6rem;
  background:#fff; font-size:1rem; }
.float .parcial { font-size:.65rem; color:#9a3412; font-weight:800; margin-top:.4rem; text-align:center; }
@media (max-width: 1500px) { .float { position:static; width:auto; margin-top:1rem; } }

/* ---------- OVERLAY DE CARGA ---------- */
.ov { position:fixed; inset:0; background:rgba(120,125,135,.45); backdrop-filter: blur(6px);
  z-index:9999; display:flex; align-items:center; justify-content:center; }
.ovc { background:#fafaf6; width:min(560px,90vw); border-radius:28px; padding:1.6rem 1.8rem;
  text-align:center; box-shadow:0 24px 60px rgba(0,0,0,.25); }
.ovc .logo { width:52px; height:52px; border-radius:12px; background:#000; margin:0 auto .6rem;
  display:flex; align-items:center; justify-content:center; }
.ovc .spin { width:28px; height:28px; border-radius:50%; border:4px solid #fff;
  border-top-color:#facc15; animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.ovc h2 { font-weight:500; font-size:1.7rem; margin:.2rem 0; color:#111827; }
.ovc .st { font-weight:800; color:#6b7280; font-size:.9rem; margin:.5rem 0 1rem; }
.bar { height:12px; background:#e5e7eb; border-radius:99px; overflow:hidden; }
.bar > div { height:100%; background:#facc15; border-radius:99px; transition: width .2s; }
.ovc .tip { font-size:.72rem; color:#6b7280; font-weight:700; margin-top:1rem; }

@media (max-width: 800px) { .hero h1 { font-size: 2.1rem; } .steps { grid-template-columns: 1fr; } }
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
# 3. CLIENTE ANTI-CAPTCHA (CapSolver / 2Captcha)
# =============================================================================
class CaptchaSolver:
    def __init__(self, provider: str = "capsolver", api_key: str = ""):
        self.provider = provider.lower().strip()
        self.api_key = api_key.strip()

    async def solve_recaptcha_v2(self, site_key: str, page_url: str, invisible: bool = False) -> str:
        if not self.api_key:
            raise CaptchaError("Falta la API Key del servicio de captcha (ver 'Opciones de desarrollo y Captcha').")

        async with httpx.AsyncClient(timeout=30) as client:
            if self.provider == "capsolver":
                task = {
                    "type": "ReCaptchaV2TaskProxyLess",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                }
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
                params = {
                    "key": self.api_key, "method": "userrecaptcha", "googlekey": site_key,
                    "pageurl": page_url, "invisible": 1 if invisible else 0, "json": 1,
                }
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
        # formato argentino 12.345,67  (o 12,345.67 si el último separador es el punto)
        if limpio.rfind(",") > limpio.rfind("."):
            limpio = limpio.replace(".", "").replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpio):
        limpio = limpio.replace(".", "")  # 12.345 -> 12345
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
            es_encabezado = bool(tr.find("th")) or (
                not tr.find("td") is None and False
            )
            if es_encabezado:
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
            if monto is None:  # buscar de derecha a izquierda una celda con importe
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
            acta = _val(d, r"acta|nro|numero|n[uú]m|comprobante|expediente|^id$")
            monto = _val(d, r"monto|importe|total|deuda|saldo|valor")
            desc = _val(d, r"descrip|infracci|falta|motivo|concepto")
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
    """Convierte la respuesta HTTP en infracciones o lanza un error EXPLÍCITO."""
    ctype = resp.headers.get("content-type", "").lower()
    cuerpo = resp.text or ""
    muestra = re.sub(r"\s+", " ", cuerpo)[:800]

    if resp.status_code >= 400:
        extra = " (posible bloqueo por IP extranjera / WAF)" if resp.status_code in (403, 429) else ""
        raise ConsultaIndeterminada(f"HTTP {resp.status_code}{extra}", resp.status_code, muestra)

    # --- JSON ---
    if "json" in ctype or cuerpo.lstrip().startswith(("{", "[")):
        try:
            data = resp.json()
        except ValueError:
            data = None
        if data is not None:
            items, hay_lista_vacia = _json_a_infracciones(data)
            if items:
                return RespuestaPortal(_dedup(items), resp.status_code, muestra)
            if hay_lista_vacia or RE_VACIO.search(cuerpo):
                return RespuestaPortal([], resp.status_code, muestra)
            raise ConsultaIndeterminada("JSON sin estructura de infracciones reconocible", resp.status_code, muestra)

    # --- HTML ---
    soup = BeautifulSoup(cuerpo, "html.parser")
    items = _tabla_a_infracciones(BeautifulSoup(cuerpo, "html.parser"))
    if items:
        return RespuestaPortal(_dedup(items), resp.status_code, muestra)

    visible = texto_visible(soup)
    muestra = visible[:800] or muestra
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

# Si conocés el sitekey de algún portal, cargalo acá y se evita buscarlo.
SITEKEYS_CONOCIDAS: dict[str, str] = {}


def _buscar_sitekey_en_texto(texto: str) -> str | None:
    for p in RE_SITEKEY:
        m = re.search(p, texto)
        if m:
            return m.group(1)
    return None


async def buscar_sitekey(client: httpx.AsyncClient, url: str, html_text: str) -> str | None:
    """Busca el sitekey en el HTML y, si no está, dentro de los .js del portal (SPAs)."""
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
    datos = {i["name"]: i.get("value", "") for i in scope.find_all("input", {"type": "hidden"}) if i.get("name")}
    datos[campo["name"]] = patente
    btn = scope.find("input", {"type": "submit"}) or scope.find("button", {"type": "submit"})
    if btn is not None and btn.get("name"):
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
            interpretar_respuesta(r_get)  # lanza el error con detalle
        soup = BeautifulSoup(r_get.text, "html.parser")
        metodo, destino, datos = preparar_form(soup, str(r_get.url), patente)  # valida ANTES de gastar captcha

        if solver is not None:
            sitekey = await buscar_sitekey(client, str(r_get.url), r_get.text)
            if not sitekey:
                raise ConsultaIndeterminada("No se encontró el sitekey de reCAPTCHA en el portal.",
                                            r_get.status_code, re.sub(r"\s+", " ", r_get.text)[:400])
            token = await solver.solve_recaptcha_v2(sitekey, str(r_get.url), invisible=invisible)
            datos["g-recaptcha-response"] = token  # se usa de inmediato (dura ~2 min, un solo uso)

        if metodo == "get":
            r_post = await client.get(destino, params=datos)
        else:
            r_post = await client.post(destino, data=datos, headers={"Referer": str(r_get.url)})
        return interpretar_respuesta(r_post)


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
    JurisdiccionConfig("PBA", "reCAPTCHA", URL_PBA,
                       lambda p, s: http_formulario(URL_PBA, p, s, invisible=True)),
    JurisdiccionConfig("CABA", "reCAPTCHA", URL_CABA,
                       lambda p, s: http_formulario(URL_CABA, p, s)),
    JurisdiccionConfig("Ezeiza", "reCAPTCHA", URL_EZEIZA,
                       lambda p, s: http_formulario(URL_EZEIZA, p, s)),
    JurisdiccionConfig("Entre Ríos", "reCAPTCHA", "https://monitoreovialentrerios.info/#/consulta-infracciones",
                       lambda p, s: http_formulario(URL_ER, p, s)),
    JurisdiccionConfig("Misiones", "reCAPTCHA", "https://monitoreovialmisiones.info/#/",
                       lambda p, s: http_formulario(URL_MISIONES, p, s)),
    JurisdiccionConfig("Lanús", "reCAPTCHA", URL_LANUS,
                       lambda p, s: http_formulario(URL_LANUS, p, s)),
    JurisdiccionConfig("Córdoba Caminera", "Sin CAPTCHA", "https://www.rentascordoba.gob.ar/emision/ver-y-pagar/caminera"),
    JurisdiccionConfig("Santa Fe", "CAPTCHA Texto", "https://www.santafe.gov.ar/juzgadovirtual/consultaInfraccion.do?method=BusquedaVehiculo"),
    JurisdiccionConfig("Vicente López", "Cloudflare", "https://infracciones.vicentelopez.gov.ar/causas-vecino"),
    JurisdiccionConfig("Avellaneda", "Cloudflare", "https://multas.mda.gob.ar"),
]

PALETA = [
    ("#ffdf5c", "#f5c400"), ("#a5d8ff", "#3b9cf0"), ("#d4c1ff", "#9b7bf0"),
    ("#b9f0cf", "#34c776"), ("#ffd0c2", "#f4724e"), ("#ffc9e3", "#e8559f"),
    ("#c7f0f0", "#2cb5b5"), ("#e6dcc8", "#a58d62"),
]


def color_de(nombre: str) -> tuple[str, str]:
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


def resumen_json(patente: str, resultados: List[ResultadoJurisdiccion]) -> dict:
    fallos = [r.nombre for r in resultados if r.estado in ESTADOS_FALLO]
    manuales = [r.nombre for r in resultados if r.estado == "sin_conector"]
    todas = [i for r in resultados for i in r.infracciones]
    return {
        "patente": patente,
        "consultado_en": datetime.now(TZ_AR).isoformat(timespec="seconds"),
        "completo": not fallos,
        "total_infracciones": len(todas),
        "total_general": round(sum(r.subtotal for r in resultados), 2),
        "portales_con_fallo": fallos,
        "portales_consulta_manual": manuales,
        "jurisdicciones": [
            {
                "nombre": r.nombre,
                "estado": r.estado,
                "detalle": r.detalle,
                "cantidad": len(r.infracciones),
                "subtotal": round(r.subtotal, 2),
                "url": r.url,
                "infracciones": [
                    {"acta": i.acta, "descripcion": i.descripcion, "monto": i.monto, "con_controlador": i.controlador}
                    for i in r.infracciones
                ],
            }
            for r in resultados
        ],
    }


def overlay(pct: int, estado: str) -> str:
    return (
        '<div class="ov"><div class="ovc">'
        '<div class="logo"><div class="spin"></div></div>'
        '<h2>Buscando multas…</h2>'
        f'<div class="st">{html.escape(estado)}</div>'
        f'<div class="bar"><div style="width:{max(pct, 6)}%"></div></div>'
        '<div class="tip">Tip: el resumen flotante te permitirá navegar rápidamente.</div>'
        '</div></div>'
    )


def _secret(nombre: str) -> str:
    try:
        return str(st.secrets.get(nombre, "") or "")
    except Exception:  # noqa: BLE001
        return ""


# =============================================================================
# 8. INTERFAZ DE USUARIO
# =============================================================================
n_jur = len(JURISDICCIONES)
chips = "".join(f'<span class="chip"><span class="dot"></span>{html.escape(j.nombre)}</span>' for j in JURISDICCIONES)

st.markdown(
    '<div class="hero">'
    '<h1>Buscar infracciones<br>por patente</h1>'
    '<p class="lead">Consulta en todas las jurisdicciones disponibles. Resultados claros y simples.</p>'
    '<span class="pill">⚡ Resultados en segundos</span>'
    '<span class="pill">🛡️ Fuentes oficiales</span>'
    f'<span class="pill">📍 {n_jur} jurisdicciones consultadas</span>'
    '<div class="panel">'
    '<div class="panel-head"><span class="panel-title">Jurisdicciones consultadas</span>'
    '<span class="panel-tag">Servicio activo</span></div>'
    '<div class="panel-sub">Se consultan automáticamente.</div>'
    f'{chips}</div>'
    '<div class="steps">'
    '<div class="step"><b class="t"><span class="n">1</span>Ingresá tu patente (sin espacios)</b>'
    '<small>Formatos válidos: LLLNNN · LLNNNLL · LNNNLLL · NNNLLL</small></div>'
    f'<div class="step"><b class="t"><span class="n">2</span>Consultamos {n_jur} jurisdicciones</b>'
    '<small>Unificamos los resultados.</small></div>'
    '<div class="step"><b class="t"><span class="n">3</span>Resultado completo</b>'
    '<small>Detalle y totales claros.</small></div>'
    '</div></div>',
    unsafe_allow_html=True,
)

with st.form("buscador", clear_on_submit=False, border=True):
    patente_input = st.text_input(
        "Patente",
        placeholder="INGRESÁ TU PATENTE (LLLNNN · LLNNNLL · LNNNLLL · NNNLLL)",
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

with st.expander("⚙️ Opciones de desarrollo y Captcha"):
    col_p, col_k = st.columns([1, 2])
    with col_p:
        proveedor_captcha = st.selectbox("Proveedor de Captcha", ["capsolver", "2captcha"])
    with col_k:
        clave_defecto = _secret("CAPSOLVER_API_KEY") or os.getenv("CAPSOLVER_API_KEY", "") or os.getenv("CAPTCHA_API_KEY", "")
        api_key_captcha = st.text_input(
            "API Key del Captcha pago",
            value=clave_defecto,
            type="password",
            placeholder="Pegá acá tu API Key de CapSolver o 2Captcha (o cargala en Secrets)",
        )
    mostrar_diag = st.checkbox("Mostrar diagnóstico por portal (respuesta cruda del servidor)", value=True)
    demo = st.checkbox(
        "Modo demo (datos SIMULADOS, solo para probar el diseño)",
        value=False,
        help="Apagado por defecto. Con esto activo NO se consulta ningún portal real ni se consume saldo.",
    )

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
    total = sum(r.subtotal for r in con_multas)
    hay_demo = any(r.demo for r in resultados)
    parcial = bool(fallidos)

    # Resumen flotante
    filas = ""
    for r in con_multas:
        bg, _ = color_de(r.nombre)
        n = len(r.infracciones)
        filas += (
            f'<div class="row" style="background:{bg}55"><span>{html.escape(r.nombre.upper()[:9])}</span>'
            f'<span class="m"><small>{n} multa{"s" if n != 1 else ""}</small>{pesos(r.subtotal)}</span></div>'
        )
    if con_multas:
        aviso = f'<div class="parcial">⚠ PARCIAL: {len(fallidos)} portal(es) sin consultar</div>' if parcial else ""
        st.markdown(
            '<div class="float"><div class="h">Resumen</div><div class="s">JURISDICCIONES</div>'
            f'{filas}<div class="s">TOTAL GENERAL</div><div class="tot">{pesos(total)}</div>{aviso}</div>',
            unsafe_allow_html=True,
        )

    # Cabecera de resultados
    jchips = "".join(
        f'<a class="jchip" href="#j{i}" style="background:{color_de(r.nombre)[0]}">'
        f'{html.escape(r.nombre)} ({len(r.infracciones)})</a>'
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
    st.markdown(
        '<div class="hero" style="margin-top:1.2rem">'
        '<h1>Resultado de búsqueda<br>por patente</h1>'
        f'<p class="lead">{intro}</p>'
        f'<span class="pill">Patente &nbsp; <b>{html.escape(dominio)}</b></span>'
        + (
            '<div class="panel"><div class="panel-title">Jurisdicciones</div>'
            '<div class="panel-sub">Tocá una jurisdicción para navegar al detalle (se muestra cantidad de multas).</div>'
            f'{jchips}</div>'
            if con_multas else ""
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    if hay_demo:
        st.markdown('<div class="warn">⚠️ <b>Modo demo:</b> los datos mostrados son simulados, no corresponden a multas reales.</div>', unsafe_allow_html=True)

    if parcial and not hay_demo:
        nombres = ", ".join(html.escape(r.nombre) for r in fallidos)
        st.markdown(
            f'<div class="warn">⚠️ <b>Resultado PARCIAL.</b> No se pudo consultar: {nombres}. '
            'El total puede ser mayor al mostrado. Revisá el detalle más abajo.</div>',
            unsafe_allow_html=True,
        )

    # Tablas por jurisdicción
    for i, r in enumerate(con_multas):
        _, dot = color_de(r.nombre)
        filas_t = ""
        for inf in r.infracciones:
            tag = '<span class="tag">MULTA CON CONTROLADOR</span><br>' if inf.controlador else ""
            filas_t += (
                f"<tr><td>{html.escape(inf.acta)}</td>"
                f"<td>{tag}{html.escape(inf.descripcion)}</td>"
                f"<td>{pesos(inf.monto)}</td></tr>"
            )
        st.markdown(
            f'<div class="card" id="j{i}"><h3><i style="background:{dot}"></i>Multas {html.escape(r.nombre)}</h3>'
            '<table class="t"><thead><tr><th>N° Acta</th><th>Descripción</th><th>Monto</th></tr></thead>'
            f"<tbody>{filas_t}</tbody></table></div>",
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
            f'<td style="text-align:left">{html.escape(r.detalle) or "—"}</td>'
            f'<td><a class="portal" href="{html.escape(r.url)}" target="_blank" rel="noopener">Abrir portal ↗</a></td></tr>'
        )
    st.markdown(
        '<div class="card"><h3><i style="background:#9ca3af"></i>Estado de cada portal</h3>'
        f'<p style="color:#6b7280;font-size:.88rem;margin-top:-.4rem">Patente consultada: <b>{html.escape(dominio)}</b>.</p>'
        '<table class="t"><thead><tr><th>Jurisdicción</th><th>Estado</th><th>Detalle</th><th>Acceso</th></tr></thead>'
        f"<tbody>{filas_p}</tbody></table></div>",
        unsafe_allow_html=True,
    )

    # Resumen en JSON
    datos_json = resumen_json(dominio, resultados)
    with st.expander("📦 Resumen en JSON", expanded=False):
        st.json(datos_json)
        st.download_button(
            "⬇️ Descargar JSON",
            data=json.dumps(datos_json, ensure_ascii=False, indent=2),
            file_name=f"infracciones_{dominio}.json",
            mime="application/json",
        )

    # Diagnóstico
    if mostrar_diag and fallidos:
        with st.expander("🛠️ Diagnóstico de portales con problemas", expanded=True):
            for r in fallidos:
                st.markdown(f"**{r.nombre}** — {ESTADO_UI[r.estado][0]} · HTTP {r.http_status or '—'}")
                st.caption(r.detalle)
                if r.muestra:
                    st.code(r.muestra, language="text")
