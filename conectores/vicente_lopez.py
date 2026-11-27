# -*- coding: utf-8 -*-
"""
Conector de infracciones para Vicente López (infracciones.vicentelopez.gov.ar).
Usa Cloudflare Turnstile. Se puede probar ejecutando: py -m conectores.vicente_lopez
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict

from bs4 import BeautifulSoup

from conectores.base import nuevo_cliente
from core.captcha import CaptchaSolver, SimulacroListo, SolverSimulacro
from core.modelos import ConsultaIndeterminada, RespuestaPortal
from core.parser import interpretar_respuesta

URL_VL = "https://infracciones.vicentelopez.gov.ar/causas-vecino"
URL_VL_DATOS = "https://infracciones.vicentelopez.gov.ar/causas-vecino/datos"
SITEKEY_VL_DEFAULT = "0x4AAAAAAB1yAonTiTL0AvK5"

RE_TURNSTILE_VL = re.compile(r'turnstile_sitekey=["\']?["\']?(0x4[0-9A-Za-z_-]{18,60})')


async def consultar_vicente_lopez(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    async with nuevo_cliente(60) as c:
        r0 = await c.get(URL_VL)
        if r0.status_code >= 400:
            interpretar_respuesta(r0)

        soup = BeautifulSoup(r0.text, "html.parser")
        meta_csrf = soup.find("meta", attrs={"name": "csrf-token"})
        csrf = meta_csrf.get("content", "") if meta_csrf else ""

        key = os.getenv("SITEKEY_VL", "").strip()
        if not key:
            m = RE_TURNSTILE_VL.search(r0.text)
            key = m.group(1) if m else SITEKEY_VL_DEFAULT
        if not key:
            raise ConsultaIndeterminada("No se encontró la clave de Cloudflare Turnstile de Vicente López.")

        token = await solver.solve_turnstile(key, URL_VL)

        headers = {
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": URL_VL,
            "Origin": "https://infracciones.vicentelopez.gov.ar",
        }
        if csrf:
            headers["X-CSRF-TOKEN"] = csrf

        params = {
            "domain_or_document": patente.upper(),
            "cf-turnstile-response": token,
            "page": 1,
        }

        r = await c.get(URL_VL_DATOS, params=params, headers=headers)
        if r.status_code == 405:
            r = await c.post(URL_VL_DATOS, json=params, headers=headers)

        return interpretar_respuesta(r)


if __name__ == "__main__":
    patente_prueba = "PKS071"
    api_key = os.getenv("CAPSOLVER_API_KEY", "").strip()
    solver = CaptchaSolver("capsolver", api_key) if api_key else SolverSimulacro()

    print(f"Probando Vicente López con patente {patente_prueba} (modo: {solver.provider})...")
    try:
        res = asyncio.run(consultar_vicente_lopez(patente_prueba, solver))
        print(json.dumps(asdict(res), ensure_ascii=False, indent=2))
    except SimulacroListo as e:
        print(f"OK SIMULACRO: {e}")
    except Exception as e:
        print(f"ERROR ({type(e).__name__}): {e}")