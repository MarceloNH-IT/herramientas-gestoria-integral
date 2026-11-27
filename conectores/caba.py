# -*- coding: utf-8 -*-
"""
Conector de infracciones para CABA (buenosaires.gob.ar).
Se puede probar de forma aislada ejecutando: python -m conectores.caba
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict
from urllib.parse import urljoin

from conectores.base import con_recaptcha, nuevo_cliente, obtener_sitekey
from core.captcha import CaptchaSolver, SimulacroListo, SolverSimulacro
from core.modelos import ConsultaIndeterminada, RespuestaPortal
from core.parser import interpretar_respuesta

URL_CABA = "https://buenosaires.gob.ar/licenciasdeconducir/consulta-de-infracciones/?actas=transito"


async def consultar_caba(patente: str, solver: CaptchaSolver) -> RespuestaPortal:
    async with nuevo_cliente(60) as c:
        r0 = await c.get(URL_CABA)
        if r0.status_code >= 400:
            interpretar_respuesta(r0)
        key = await obtener_sitekey(c, r0, "SITEKEY_CABA")
        if not key:
            raise ConsultaIndeterminada(
                "No se encontró el sitekey de reCAPTCHA en el portal de CABA.",
                r0.status_code,
                re.sub(r"\s+", " ", r0.text)[:400],
            )
        destino = urljoin(str(r0.url), "index.php")

        async def enviar(token: str) -> RespuestaPortal:
            datos = {
                "tipo_consulta": "Dominio",
                "tipo_doc": "DNI",
                "doc": "",
                "filtro_acta": "transito",
                "dominio": patente.lower(),
                "g-recaptcha-response": token,
            }
            r = await c.post(
                destino,
                data=datos,
                headers={"Origin": "https://buenosaires.gob.ar", "Referer": URL_CABA},
            )
            return interpretar_respuesta(r)

        return await con_recaptcha(solver, key, URL_CABA, False, enviar)


if __name__ == "__main__":
    patente_prueba = "AA123BB"
    api_key = os.getenv("CAPSOLVER_API_KEY", "").strip()
    solver = CaptchaSolver("capsolver", api_key) if api_key else SolverSimulacro()

    print(f"Probando CABA con patente {patente_prueba} (modo: {solver.provider})...")
    try:
        res = asyncio.run(consultar_caba(patente_prueba, solver))
        print(json.dumps(asdict(res), ensure_ascii=False, indent=2))
    except SimulacroListo as e:
        print(f"OK SIMULACRO: {e}")
    except Exception as e:
        print(f"ERROR ({type(e).__name__}): {e}")