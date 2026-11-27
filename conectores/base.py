# -*- coding: utf-8 -*-
"""
Utilidades HTTP compartidas por todos los conectores (cliente, sitekeys y paginación).
No depende de Streamlit: se puede ejecutar directo desde la terminal.
"""
from __future__ import annotations

import os
import re
from typing import List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from core.captcha import CaptchaSolver
from core.modelos import CaptchaError, ConsultaIndeterminada, Infraccion, RespuestaPortal

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

RE_SITEKEY = [
    r'data-sitekey=["\']([0-9A-Za-z_-]{40})["\']',
    r'sitekey["\']?\s*[:=]\s*["\']([0-9A-Za-z_-]{40})["\']',
    r'recaptcha/(?:api|enterprise)\.js\?[^"\']*render=([0-9A-Za-z_-]{40})',
    r'[?&]k=([0-9A-Za-z_-]{40})',
    r'["\'](6L[0-9A-Za-z_-]{38})["\']',
]

RE_LIBS = re.compile(
    r"google|gstatic|googletagmanager|facebook|cloudflareinsights|jquery|bootstrap|fontawesome",
    re.I,
)


def nuevo_cliente(timeout: int = 40) -> httpx.AsyncClient:
    return httpx.AsyncClient(verify=False, follow_redirects=True, timeout=timeout, headers=HEADERS_HTTP)


def buscar_sitekey_en_texto(texto: str) -> str | None:
    for patron in RE_SITEKEY:
        m = re.search(patron, texto)
        if m:
            return m.group(1)
    return None


async def descargar_textos_sitio(
    client: httpx.AsyncClient,
    url: str,
    html_text: str,
    max_scripts: int = 10,
    max_chunks: int = 8,
) -> list[str]:
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


async def obtener_sitekey(client: httpx.AsyncClient, r0: httpx.Response, env_var: str) -> str | None:
    key = os.getenv(env_var, "").strip()
    if key:
        return key
    key = buscar_sitekey_en_texto(r0.text)
    if key:
        return key
    for t in await descargar_textos_sitio(client, str(r0.url), r0.text):
        key = buscar_sitekey_en_texto(t)
        if key:
            return key
    return None


async def con_recaptcha(
    solver: CaptchaSolver,
    key: str,
    page_url: str,
    invisible: bool,
    enviar,
) -> RespuestaPortal:
    """Resuelve reCAPTCHA v2 y envía. Si el portal rechaza el token, reintenta UNA vez como Enterprise."""
    token = await solver.solve_recaptcha_v2(key, page_url, invisible=invisible)
    try:
        return await enviar(token)
    except CaptchaError as exc:
        if "rechaz" not in str(exc):
            raise
    token = await solver.solve_recaptcha_v2(key, page_url, invisible=invisible, enterprise=True)
    return await enviar(token)


async def paginar(obtener, por_pagina: int, max_paginas: int = 5) -> RespuestaPortal:
    acumulado: List[Infraccion] = []
    vistos: set = set()
    ultima: RespuestaPortal | None = None
    for pagina in range(1, max_paginas + 1):
        try:
            resp = await obtener(pagina)
        except ConsultaIndeterminada:
            if pagina == 1:
                raise
            break
        ultima = resp
        nuevos = [i for i in resp.infracciones if (i.acta, i.monto) not in vistos]
        vistos.update((i.acta, i.monto) for i in nuevos)
        acumulado += nuevos
        if len(resp.infracciones) < por_pagina or not nuevos:
            break
    assert ultima is not None
    return RespuestaPortal(acumulado, ultima.http_status, ultima.muestra)