# -*- coding: utf-8 -*-
"""
Conector de infracciones para Lomas de Zamora (flujo ASP.NET en 3 pasos + lectura de PDF).
No requiere captcha. Se puede probar ejecutando: py -m conectores.lomas
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict
from io import BytesIO
from typing import List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from conectores.base import nuevo_cliente
from core.captcha import CaptchaSolver
from core.modelos import Infraccion, RespuestaPortal
from core.parser import _etiquetas, interpretar_respuesta, limpiar_monto, texto_visible

URL_LOMAS = "https://webextra.lomasdezamora.gov.ar/infracciones/ConsultaFaltasNuevoMP.aspx"
_RE_CAUSA_LOMAS = re.compile(r"^\d{3,}-\d{1,4}-\d{4}$")


def _serializar_form(scope) -> dict:
    datos: dict = {}
    for el in scope.find_all(["input", "select", "textarea"]):
        nombre = el.get("name")
        if not nombre:
            continue
        if el.name == "input":
            t = (el.get("type") or "text").lower()
            if t in ("submit", "button", "image", "reset", "file"):
                continue
            if t in ("checkbox", "radio"):
                if el.has_attr("checked"):
                    datos[nombre] = el.get("value", "on")
                continue
            datos[nombre] = el.get("value", "")
        elif el.name == "select":
            opt = el.find("option", selected=True) or el.find("option")
            datos[nombre] = opt.get("value", opt.get_text(strip=True)) if opt else ""
        else:
            datos[nombre] = el.get_text()
    return datos


def _extraer_texto_pdf_bytes(pdf_bytes: bytes) -> str:
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        texto = "\n".join(page.extract_text() or "" for page in reader.pages)
        if texto.strip():
            return texto
    except Exception:
        pass

    textos: list[str] = []
    for m in re.finditer(rb"\(([^()\\]{1,200})\)", pdf_bytes):
        try:
            parte = m.group(1).decode("latin-1", errors="ignore").strip()
            if parte and re.search(r"[\w$]", parte):
                textos.append(parte)
        except Exception:
            continue
    return " ".join(textos)


def _buscar_importe_en_respuesta(resp_obj: httpx.Response) -> float | None:
    if not resp_obj or resp_obj.status_code >= 400:
        return None
    ctype = (resp_obj.headers.get("content-type") or "").lower()
    raw = resp_obj.content or b""
    if not raw:
        return None

    if "pdf" in ctype or raw.startswith(b"%PDF"):
        visible = _extraer_texto_pdf_bytes(raw)
    else:
        soup = BeautifulSoup(resp_obj.text or "", "html.parser")
        visible = texto_visible(soup)

    if not visible:
        return None

    for m in re.finditer(
        r"(?:importe|monto|total\s*(?:a\s*pagar)?|arancel|recibo|comprobante|valor|a\s*abonar)\s*:?\s*\$?\s*([\d.]+,[\d]{2}|[\d,]+\.[\d]{2}|[\d.]{3,})",
        visible,
        re.I,
    ):
        val = limpiar_monto(m.group(1))
        if val is not None and val > 0:
            return val

    for m in re.finditer(r"\$\s*([\d.]+,[\d]{2}|[\d,]+\.[\d]{2}|[\d.]{3,})", visible):
        val = limpiar_monto(m.group(1))
        if val is not None and val > 0:
            return val

    return None


def _extraer_causas_lomas(html_text: str) -> List[tuple[Infraccion, int, dict[str, str]]]:
    soup = BeautifulSoup(html_text, "html.parser")
    encontrados: List[tuple[Infraccion, int, dict[str, str]]] = []
    for tr in soup.find_all("tr"):
        cols = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cols) < 4:
            continue
        causa = next((c for c in cols if _RE_CAUSA_LOMAS.match(c.strip())), None)
        if not causa:
            continue
        idx = cols.index(causa)
        monto_hallado: float | None = None
        for c in cols:
            cs = c.strip()
            if cs == causa.strip() or re.fullmatch(r"\d{2}/\d{2}/\d{4}", cs) or re.fullmatch(r"\d{6,9}", cs):
                continue
            if re.search(r"\$|\d+[.,]\d{2}\b", cs):
                val = limpiar_monto(cs)
                if val is not None and val > 0:
                    monto_hallado = val
                    break

        infraccion_txt = cols[idx + 4] if len(cols) > idx + 4 else (cols[idx + 3] if len(cols) > idx + 3 else "")
        fecha_txt = cols[idx + 5] if len(cols) > idx + 5 else ""
        lugar_txt = cols[idx + 6] if len(cols) > idx + 6 else ""

        partes = [
            p for p in (
                infraccion_txt,
                f"Fecha: {fecha_txt}" if fecha_txt else "",
                f"Lugar: {lugar_txt}" if lugar_txt else "",
            ) if p
        ]
        desc = " — ".join(partes) if partes else "Infracción de tránsito"
        inf = Infraccion(
            acta=causa.strip()[:30],
            descripcion=desc[:140],
            monto=monto_hallado,
            etiquetas=_etiquetas(" ".join(cols)),
        )

        extra_post: dict[str, str] = {}
        for ctrl in tr.find_all(["input", "a", "button"]):
            cid = ctrl.get("id") or ""
            cname = ctrl.get("name") or ""
            cval = (ctrl.get("value") or ctrl.get_text(" ", strip=True) or "").lower()
            if "recibo" in cval or "recibo" in cid.lower() or "recibo" in cname.lower():
                if cname:
                    extra_post[cname] = ctrl.get("value") or "Recibo"
                    break

        encontrados.append((inf, len(encontrados), extra_post))

    vistos: set = set()
    unicos: List[tuple[Infraccion, int, dict[str, str]]] = []
    for inf, fila_idx, extra_post in encontrados:
        clave = (inf.acta, inf.monto)
        if clave not in vistos:
            vistos.add(clave)
            unicos.append((inf, fila_idx, extra_post))
    return unicos


def _extraer_campos_ocultos_aspnet(html_text: str) -> dict[str, str]:
    soup = BeautifulSoup(html_text, "html.parser")
    datos: dict[str, str] = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "text").lower()
        if itype == "hidden":
            datos[name] = inp.get("value", "")
    return datos


async def _consultar_comprobante_lomas(
    client: httpx.AsyncClient,
    destino: str,
    referer_url: str,
    hidden_grilla: dict[str, str],
    patente: str,
    fila_idx: int,
    extra_fila: dict[str, str],
) -> float | None:
    headers = {
        "Origin": "https://webextra.lomasdezamora.gov.ar",
        "Referer": referer_url,
    }
    try:
        # PASO 2: Clic en el botón "Recibo" de la fila (abre el modal y genera nuevo VIEWSTATE)
        datos_modal = dict(hidden_grilla)
        datos_modal["__EVENTTARGET"] = ""
        datos_modal["__EVENTARGUMENT"] = ""
        datos_modal["__LASTFOCUS"] = ""
        datos_modal["txtDominio"] = patente.lower()
        datos_modal["txtDocumento"] = ""
        datos_modal["txtCuit"] = ""
        datos_modal["SelOP"] = "rdbReciboImpreso"
        datos_modal["txtmail"] = ""
        datos_modal["lblindex"] = str(fila_idx)
        datos_modal.update(extra_fila)

        r_modal = await client.post(destino, data=datos_modal, headers=headers)
        monto = _buscar_importe_en_respuesta(r_modal)
        if monto is not None:
            return monto

        # PASO 3: Clic en "Siguiente" dentro del modal (descarga el PDF del recibo)
        hidden_modal = _extraer_campos_ocultos_aspnet(r_modal.text or "") or hidden_grilla
        datos_pdf = dict(hidden_modal)
        datos_pdf["__EVENTTARGET"] = "inSiguiente"
        datos_pdf["__EVENTARGUMENT"] = ""
        datos_pdf["__LASTFOCUS"] = ""
        datos_pdf["txtDominio"] = patente.lower()
        datos_pdf["txtDocumento"] = ""
        datos_pdf["txtCuit"] = ""
        datos_pdf["SelOP"] = "rdbReciboImpreso"
        datos_pdf["txtmail"] = ""
        datos_pdf["lblindex"] = hidden_modal.get("lblindex") or str(fila_idx)

        r_comp = await client.post(destino, data=datos_pdf, headers=headers)
        monto = _buscar_importe_en_respuesta(r_comp)
        if monto is not None:
            return monto

        if r_comp.status_code < 400 and r_comp.text:
            soup_c = BeautifulSoup(r_comp.text, "html.parser")
            for tag in soup_c.find_all(["a", "iframe", "embed"]):
                link = tag.get("href") or tag.get("src") or ""
                if link and re.search(r"recibo|comprobante|boleta|pdf|imprimir|report", link, re.I):
                    r_doc = await client.get(urljoin(str(r_comp.url), link), headers={"Referer": str(r_comp.url)})
                    monto_doc = _buscar_importe_en_respuesta(r_doc)
                    if monto_doc is not None:
                        return monto_doc
    except httpx.HTTPError:
        return None
    return None


async def consultar_lomas(patente: str, solver: CaptchaSolver | None = None) -> RespuestaPortal:
    async with nuevo_cliente(45) as client:
        r_get = await client.get(URL_LOMAS)
        if r_get.status_code >= 400:
            interpretar_respuesta(r_get)
        soup = BeautifulSoup(r_get.text, "html.parser")
        datos = _serializar_form(soup)

        datos["__EVENTTARGET"] = ""
        datos["__EVENTARGUMENT"] = ""
        datos["__LASTFOCUS"] = ""
        datos["txtDominio"] = patente.lower()
        datos.setdefault("txtDocumento", "")
        datos.setdefault("txtCuit", "")
        datos["cmdConfirmaTurno"] = "Buscar"
        datos.setdefault("SelOP", "rdbReciboImpreso")
        datos.setdefault("txtmail", "")
        datos.setdefault("lblindex", "")

        form = soup.find("form")
        destino = urljoin(str(r_get.url), form["action"]) if (form and form.get("action")) else str(r_get.url)
        r_post = await client.post(
            destino,
            data=datos,
            headers={
                "Origin": "https://webextra.lomasdezamora.gov.ar",
                "Referer": str(r_get.url),
            },
        )
        if r_post.status_code < 400:
            pares = _extraer_causas_lomas(r_post.text or "")
            if pares:
                hidden_post = _extraer_campos_ocultos_aspnet(r_post.text or "")
                items: List[Infraccion] = []
                for inf, fila_idx, extra_fila in pares:
                    if inf.monto is None:
                        monto_comp = await _consultar_comprobante_lomas(
                            client,
                            destino,
                            str(r_get.url),
                            hidden_post or datos,
                            patente,
                            fila_idx,
                            extra_fila,
                        )
                        if monto_comp is not None:
                            inf.monto = monto_comp
                    items.append(inf)
                muestra = re.sub(r"\s+", " ", r_post.text or "")[:800]
                return RespuestaPortal(items, r_post.status_code, muestra)
        return interpretar_respuesta(r_post)


if __name__ == "__main__":
    patente_prueba = "LVQ189"

    print(f"Consultando Lomas de Zamora en vivo para {patente_prueba}...")
    try:
        res = asyncio.run(consultar_lomas(patente_prueba))
        print(json.dumps(asdict(res), ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"ERROR ({type(e).__name__}): {e}")