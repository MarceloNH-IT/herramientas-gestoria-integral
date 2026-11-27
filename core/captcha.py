# -*- coding: utf-8 -*-
"""
Cliente Anti-Captcha (CapSolver / 2Captcha) y modo Simulacro.
"""
from __future__ import annotations

import asyncio
import httpx

from core.modelos import CaptchaError


class CaptchaSolver:
    def __init__(self, provider: str = "capsolver", api_key: str = ""):
        self.provider = provider.lower().strip()
        self.api_key = api_key.strip()

    async def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        invisible: bool = False,
        enterprise: bool = False,
    ) -> str:
        if not self.api_key:
            raise CaptchaError("Falta la API Key del servicio de captcha.")

        async with httpx.AsyncClient(timeout=30) as client:
            if self.provider == "capsolver":
                task = {
                    "type": "ReCaptchaV2EnterpriseTaskProxyLess" if enterprise else "ReCaptchaV2TaskProxyLess",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                }
                if invisible:
                    task["isInvisible"] = True
                r = await client.post(
                    "https://api.capsolver.com/createTask",
                    json={"clientKey": self.api_key, "task": task},
                )
                data = r.json()
                if data.get("errorId", 0) != 0:
                    raise CaptchaError(f"CapSolver: {data.get('errorCode')} - {data.get('errorDescription')}")
                task_id = data["taskId"]

                for _ in range(60):  # hasta ~2 min
                    await asyncio.sleep(2)
                    res = await client.post(
                        "https://api.capsolver.com/getTaskResult",
                        json={"clientKey": self.api_key, "taskId": task_id},
                    )
                    rd = res.json()
                    if rd.get("errorId", 0) != 0:
                        raise CaptchaError(f"CapSolver: {rd.get('errorCode')} - {rd.get('errorDescription')}")
                    if rd.get("status") == "ready":
                        return rd["solution"]["gRecaptchaResponse"]
                    if rd.get("status") == "failed":
                        raise CaptchaError("CapSolver: la tarea falló")
            else:
                params = {
                    "key": self.api_key,
                    "method": "userrecaptcha",
                    "googlekey": site_key,
                    "pageurl": page_url,
                    "invisible": 1 if invisible else 0,
                    "json": 1,
                }
                if enterprise:
                    params["enterprise"] = 1
                r = await client.get("http://2captcha.com/in.php", params=params)
                data = r.json()
                if data.get("status") != 1:
                    raise CaptchaError(f"2Captcha: {data.get('request')}")
                req_id = data["request"]

                for _ in range(30):
                    await asyncio.sleep(4)
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
        """Cloudflare Turnstile (Entre Ríos / Monitoreo Vial)."""
        if not self.api_key:
            raise CaptchaError("Falta la API Key del servicio de captcha.")

        async with httpx.AsyncClient(timeout=30) as client:
            if self.provider == "capsolver":
                task = {
                    "type": "AntiTurnstileTaskProxyLess",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                }
                r = await client.post(
                    "https://api.capsolver.com/createTask",
                    json={"clientKey": self.api_key, "task": task},
                )
                data = r.json()
                if data.get("errorId", 0) != 0:
                    raise CaptchaError(f"CapSolver: {data.get('errorCode')} - {data.get('errorDescription')}")
                task_id = data["taskId"]

                for _ in range(60):
                    await asyncio.sleep(2)
                    res = await client.post(
                        "https://api.capsolver.com/getTaskResult",
                        json={"clientKey": self.api_key, "taskId": task_id},
                    )
                    rd = res.json()
                    if rd.get("errorId", 0) != 0:
                        raise CaptchaError(f"CapSolver: {rd.get('errorCode')} - {rd.get('errorDescription')}")
                    if rd.get("status") == "ready":
                        return rd["solution"]["token"]
                    if rd.get("status") == "failed":
                        raise CaptchaError("CapSolver: la tarea Turnstile falló")
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
                    raise CaptchaError(f"2Captcha: {data.get('request')}")
                req_id = data["request"]

                for _ in range(30):
                    await asyncio.sleep(4)
                    res = await client.get(
                        "http://2captcha.com/res.php",
                        params={"key": self.api_key, "action": "get", "id": req_id, "json": 1},
                    )
                    rd = res.json()
                    if rd.get("status") == 1:
                        return rd["request"]
                    if rd.get("request") != "CAPCHA_NOT_READY":
                        raise CaptchaError(f"2Captcha: {rd.get('request')}")

        raise CaptchaError("Tiempo agotado esperando la solución de Turnstile.")


class SimulacroListo(Exception):
    """El conector llegó hasta el captcha sin resolverlo (modo simulacro: no gasta saldo)."""


class SolverSimulacro(CaptchaSolver):
    def __init__(self) -> None:
        super().__init__("simulacro", "simulacro")

    async def solve_recaptcha_v2(self, *a, **k) -> str:
        raise SimulacroListo("Llegó hasta el captcha sin resolverlo: portal, formulario y clave OK.")

    async def solve_turnstile(self, *a, **k) -> str:
        raise SimulacroListo("Llegó hasta el captcha sin resolverlo: portal, API y clave OK.")