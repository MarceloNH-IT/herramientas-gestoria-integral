# -*- coding: utf-8 -*-
"""
Conector de infracciones para Entre Ríos (monitoreovialentrerios.info).
Usa Cloudflare Turnstile. Se puede probar ejecutando: py -m conectores.entre_rios
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict
from urllib.parse import urlparse

from conectores.base import descargar_textos_sitio, nuevo_cliente, paginar
from core.captcha import CaptchaSolver, SimulacroListo, SolverSimulacro
from core.modelos import ConsultaIndeterminada, RespuestaPortal
from core.parser import interpretar_respuesta

URL_ENTRE_RIOS = "https://monitoreovialentrerios.info/"
API_ENTRE_RIOS = "https://api.monitoreovialentrerios.ar/api/v3/69fa0e115c1082b8"
POR_PAGINA_MV = 15

RE_TURNSTILE = re.compile(r"\b(0x4[0-9A-Za-z_-]{18,60})\b")
RE_API_MONITOREO = re.compile(r"https://api\.monitoreovial[a-z]+\.[a-z]+/api/v\d+/[0-9a-f]{12,32}")


async def consultar_entre_rios(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    u = urlparse(URL_ENTRE_RIOS)
    origen = f"{u.scheme}://{u.netloc}"

    async with nuevo_cliente(60) as c:
        r0 = await c.get(URL_ENTRE_RIOS)
        if r0.status_code >= 400:
            interpretar_respuesta(r0)

        todo = "\n".join(await descargar_textos_sitio(c, str(r0.url), r0.text))
        m = RE_API_MONITOREO.search(todo)
        api = m.group(0) if m else API_ENTRE_RIOS

        key = os.getenv("SITEKEY_ENTRERIOS", "").strip()
        if not key:
            mk = RE_TURNSTILE.search(todo)
            key = mk.group(1) if mk else ""
        if not key:
            raise ConsultaIndeterminada(
                "No se encontró la clave de Cloudflare Turnstile de Entre Ríos."
            )

        async def obtener(pagina: int) -> RespuestaPortal:
            token = await solver.solve_turnstile(key, URL_ENTRE_RIOS)
            datos = {
                "consulta": "1",
                "id": patente,
                "pagina": str(POR_PAGINA_MV),
                "page": str(pagina),
                "cf_turnstile_token": token,
            }
            r = await c.post(
                api,
                data=datos,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Origin": origen,
                    "Referer": URL_ENTRE_RIOS,
                },
            )
            return interpretar_respuesta(r)

        return await paginar(obtener, POR_PAGINA_MV, max_paginas=4)


if __name__ == "__main__":
    patente_prueba = "AA123BB"
    api_key = os.getenv("CAPSOLVER_API_KEY", "").strip()
    solver = CaptchaSolver("capsolver", api_key) if api_key else SolverSimulacro()

    print(f"Probando Entre Ríos con patente {patente_prueba} (modo: {solver.provider})...")
    try:
        res = asyncio.run(consultar_entre_rios(patente_prueba, solver))
        print(json.dumps(asdict(res), ensure_ascii=False, indent=2))
    except SimulacroListo as e:
        print(f"OK SIMULACRO: {e}")
    except Exception as e:
        print(f"ERROR ({type(e).__name__}): {e}")