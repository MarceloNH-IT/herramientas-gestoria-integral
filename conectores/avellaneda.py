# -*- coding: utf-8 -*-
"""
Conector de infracciones para Avellaneda (multas.mda.gob.ar).
No requiere captcha. Se puede probar ejecutando: py -m conectores.avellaneda
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

from conectores.base import nuevo_cliente
from core.captcha import CaptchaSolver
from core.modelos import RespuestaPortal
from core.parser import interpretar_respuesta

URL_AVELLANEDA_API = "https://siac.mda.gob.ar/api/externo/consultar"


async def consultar_avellaneda(patente: str, solver: CaptchaSolver | None = None) -> RespuestaPortal:
    async with nuevo_cliente(40) as c:
        r = await c.post(
            URL_AVELLANEDA_API,
            json={"buscarPor": "PATENTE", "parametroBusqueda": patente.upper()},
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://multas.mda.gob.ar",
                "Referer": "https://multas.mda.gob.ar/",
            },
        )
        return interpretar_respuesta(r)


if __name__ == "__main__":
    patente_prueba = "AA123BB"  # Podés cambiarla por cualquier patente real para probar

    print(f"Consultando Avellaneda en vivo para {patente_prueba}...")
    try:
        res = asyncio.run(consultar_avellaneda(patente_prueba))
        print(json.dumps(asdict(res), ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"ERROR ({type(e).__name__}): {e}")