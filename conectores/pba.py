# -*- coding: utf-8 -*-
"""
Conector de infracciones para Provincia de Buenos Aires (infraccionesba.gba.gob.ar).
Se puede probar de forma aislada ejecutando: py -m conectores.pba
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict

from conectores.base import con_recaptcha, nuevo_cliente, obtener_sitekey, paginar
from core.captcha import CaptchaSolver, SimulacroListo, SolverSimulacro
from core.modelos import ConsultaIndeterminada, RespuestaPortal
from core.parser import interpretar_respuesta

URL_PBA = "https://infraccionesba.gba.gob.ar/consulta-infraccion"
URL_PBA_API = "https://infraccionesba.gba.gob.ar/rest/consultar-infraccion"
POR_PAGINA_PBA = 10


async def consultar_pba(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    async with nuevo_cliente(60) as c:
        r0 = await c.get(URL_PBA)
        if r0.status_code >= 400:
            interpretar_respuesta(r0)
        key = await obtener_sitekey(c, r0, "SITEKEY_PBA")
        if not key:
            raise ConsultaIndeterminada(
                "No se encontró el sitekey de reCAPTCHA de PBA.",
                r0.status_code,
                re.sub(r"\s+", " ", r0.text)[:400],
            )

        async def obtener(pagina: int) -> RespuestaPortal:
            async def enviar(token: str) -> RespuestaPortal:
                headers_pba = {
                    "Accept": "application/json, text/plain, */*",
                    "Referer": URL_PBA,
                    "X-Requested-With": "XMLHttpRequest",
                }
                for dom_fmt in (patente.upper(), patente.lower()):
                    params = {
                        "dominio": dom_fmt,
                        "reCaptcha": token,
                        "cantPorPagina": POR_PAGINA_PBA,
                        "paginaActual": pagina,
                    }
                    r = await c.get(URL_PBA_API, params=params, headers=headers_pba)
                    if r.status_code == 200:
                        resp = interpretar_respuesta(r)
                        if resp.infracciones or dom_fmt == patente.lower():
                            return resp
                return interpretar_respuesta(r)

            return await con_recaptcha(solver, key, URL_PBA, False, enviar)

        return await paginar(obtener, POR_PAGINA_PBA)


if __name__ == "__main__":
    patente_prueba = "AA123BB"
    api_key = os.getenv("CAPSOLVER_API_KEY", "").strip()
    solver = CaptchaSolver("capsolver", api_key) if api_key else SolverSimulacro()

    print(f"Probando PBA con patente {patente_prueba} (modo: {solver.provider})...")
    try:
        res = asyncio.run(consultar_pba(patente_prueba, solver))
        print(json.dumps(asdict(res), ensure_ascii=False, indent=2))
    except SimulacroListo as e:
        print(f"OK SIMULACRO: {e}")
    except Exception as e:
        print(f"ERROR ({type(e).__name__}): {e}")