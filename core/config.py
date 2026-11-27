from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


RAIZ = Path(__file__).resolve().parent.parent


def _leer_secrets_toml() -> dict[str, Any]:
    for ruta in (
        RAIZ / ".streamlit" / "secrets.toml",
        Path.cwd() / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    ):
        if ruta.is_file():
            try:
                data = tomllib.loads(ruta.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return {}


def obtener_valor(nombre: str, defecto: str = "") -> str:
    val_env = os.environ.get(nombre)
    if val_env is not None and str(val_env).strip() != "":
        return str(val_env).strip()

    secrets = _leer_secrets_toml()
    if nombre in secrets and secrets[nombre] is not None:
        return str(secrets[nombre]).strip()

    return defecto


def cargar_config_captcha() -> dict[str, Any]:
    proveedor = obtener_valor("CAPSOLVER_PROVIDER", "capsolver").lower()
    clave = (
        obtener_valor("CAPSOLVER_API_KEY")
        or obtener_valor("CAPTCHA_API_KEY")
        or obtener_valor("TWOCAPTCHA_API_KEY")
    )
    return {
        "proveedor": proveedor,
        "api_key": clave,
        "tiene_clave": bool(clave),
        "largo_clave": len(clave),
    }


def diagnostico_entorno() -> dict[str, Any]:
    cfg = cargar_config_captcha()
    return {
        "proyecto_raiz": str(RAIZ),
        "captcha_proveedor": cfg["proveedor"],
        "captcha_clave_configurada": cfg["tiene_clave"],
        "captcha_largo_clave": cfg["largo_clave"],
    }
def cargar_en_entorno(sobreescribir: bool = False) -> dict[str, str]:
    cargadas: dict[str, str] = {}
    claves = (
        "CAPSOLVER_PROVIDER",
        "CAPSOLVER_API_KEY",
        "CAPTCHA_API_KEY",
        "TWOCAPTCHA_API_KEY",
        "PROVEEDOR_CAPTCHA",
        "ADMIN_PASSWORD",
        "PORTALES_ACTIVOS",
    )
    for nombre in claves:
        if not sobreescribir and os.environ.get(nombre):
            continue
        val = obtener_valor(nombre)
        if val:
            os.environ[nombre] = val
            cargadas[nombre] = val
    return cargadas
