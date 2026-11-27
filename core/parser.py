# -*- coding: utf-8 -*-
"""
Parseo y traducción de respuestas HTTP (HTML y JSON) a modelos estándar.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from core.modelos import CaptchaError, ConsultaIndeterminada, Infraccion, RespuestaPortal

TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")

RE_VACIO = re.compile(
    r"no registra|no posee|no se encontr|sin infracciones|sin deuda|libre de deuda|"
    r"no tiene (infracciones|multas|deuda|actas)|no existen|no hay (infracciones|multas|actas)|"
    r"sin resultados|0 resultados|no se hallaron",
    re.I,
)
RE_CAPTCHA_MAL = re.compile(
    r"re?captcha.{0,60}(inv[aá]lid|incorrect|error|fall|venc|expir|no (es )?v[aá]lid)|"
    r"(inv[aá]lid|incorrect|error|fall).{0,30}re?captcha|captcha (inv[aá]lido|incorrecto|expirado)|"
    r"turnstile.{0,40}(inv[aá]lid|error|fall|expir)",
    re.I,
)

RE_ACTA_VALOR = re.compile(r"^\d{2}-\d{3}-\d{5,9}-\d(?:-\d{1,2})?$")
_PRIO_ACTA = [r"n(ro|um|umero|úmero)?_?acta|acta_?n(ro|um|umero)", r"acta", r"comprobante|expediente|boleta|causa"]
_PRIO_MONTO = [r"^importe$|importe_?(total|actual|vigente|a_?pagar)$", r"importe", r"monto", r"deuda|saldo", r"valor", r"^total$"]
_RE_NO_MONTO = re.compile(r"cant|count|nro|num|id$|cuota|dias|d[ií]as|puntos|estado", re.I)
_PRIO_DESC = [r"descrip", r"infracci", r"detalle", r"norma|articulo|falta|motivo|concepto"]

RE_ACTA_INICIO = re.compile(
    r"Acta\s*N[°º]?\s*([A-Z]?\d[A-Z0-9-]*)\s*[-–]\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})(?:\s+\d{2}:\d{2})?",
    re.I,
)
RE_CORTE_ACTA = re.compile(
    r"Total seleccionado|Seleccionar todas|Pagar seleccionadas|Imprimir|Se deja constancia|Ver (?:m[aá]s|menos)",
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
        if limpio.rfind(",") > limpio.rfind("."):
            limpio = limpio.replace(".", "").replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpio):
        limpio = limpio.replace(".", "")
    try:
        return float(limpio)
    except ValueError:
        return None


def _hoja(ruta: str) -> str:
    return ruta.split(".")[-1]


def _etiquetas(texto: str) -> List[str]:
    t = (texto or "").lower()
    out: List[str] = []
    if "controlador" in t:
        out.append("MULTA CON CONTROLADOR")
    if re.search(r"pago\s*voluntario", t):
        out.append("PAGO VOLUNTARIO")
    return out


def _etiquetas_json(d: dict) -> List[str]:
    out: List[str] = []
    verdadero = (True, 1, "1", "true", "True", "TRUE", "si", "Si", "SI", "S")
    for k, v in d.items():
        kl = _hoja(str(k)).lower()
        if isinstance(v, (dict, list)):
            continue
        if re.search(r"controlador", kl) and v in verdadero and "MULTA CON CONTROLADOR" not in out:
            out.append("MULTA CON CONTROLADOR")
        if re.search(r"pago_?\s*voluntario", kl) and v in verdadero and "PAGO VOLUNTARIO" not in out:
            out.append("PAGO VOLUNTARIO")
        if isinstance(v, str):
            for e in _etiquetas(v):
                if e not in out:
                    out.append(e)
    return out


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
            if tr.find("th"):
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
            if monto is None:
                for c in reversed(cols[1:]):
                    if re.search(r"\$|\d+[.,]\d{2}\b", c):
                        monto = limpiar_monto(c)
                        if monto is not None:
                            break
            out.append(Infraccion(
                acta=acta[:30],
                descripcion=(desc or "Infracción de tránsito")[:140],
                monto=monto,
                etiquetas=_etiquetas(" ".join(cols)),
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


def _aplanar(d: dict, prefijo: str = "", out: dict | None = None, prof: int = 0) -> dict:
    out = {} if out is None else out
    for k, v in d.items():
        ruta = f"{prefijo}.{k}" if prefijo else str(k)
        if isinstance(v, dict) and prof < 3:
            _aplanar(v, ruta, out, prof + 1)
        elif not isinstance(v, (dict, list)):
            out[ruta] = v
    return out


def _es_fecha_epoch(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 9e11 < float(v) < 5e12


def _fmt_fecha(v) -> str:
    try:
        if _es_fecha_epoch(v):
            ms = float(v)
            if ms % 86_400_000 == 0:
                return datetime.utcfromtimestamp(ms / 1000).strftime("%d/%m/%Y")
            return datetime.fromtimestamp(ms / 1000, TZ_AR).strftime("%d/%m/%Y")
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v))
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    except (ValueError, OverflowError, OSError):
        pass
    return str(v)


def _extraer_infraccion(d: dict) -> Infraccion | None:
    plano = _aplanar(d)
    acta = next((str(v) for v in plano.values() if isinstance(v, str) and RE_ACTA_VALOR.match(v.strip())), None)
    if acta is None:
        for patron in _PRIO_ACTA:
            cand = [
                (k, v) for k, v in plano.items()
                if re.search(patron, _hoja(k), re.I) and v not in (None, "") and not isinstance(v, bool)
            ]
            cand.sort(key=lambda kv: isinstance(kv[1], str), reverse=True)
            if cand:
                acta = str(cand[0][1])
                break
    if acta is None:
        return None

    monto = None
    for patron in _PRIO_MONTO:
        for k, v in plano.items():
            h = _hoja(k)
            if re.search(patron, h, re.I) and not _RE_NO_MONTO.search(h) and not isinstance(v, bool):
                m = limpiar_monto(v)
                if m is not None and m > 0:
                    monto = m
                    break
        if monto is not None:
            break
    if monto is None:
        return None

    desc = None
    if isinstance(d.get("infracciones"), list) and d["infracciones"]:
        sub = d["infracciones"][0]
        if isinstance(sub, dict):
            art = str(sub.get("articulo") or "").strip()
            sub_desc = str(sub.get("descripcion") or sub.get("detalle") or "").strip()
            if sub_desc:
                desc = f"Art. {art} - {sub_desc}" if art else sub_desc
    if not desc:
        for patron in _PRIO_DESC:
            for k, v in plano.items():
                if (
                    re.search(patron, _hoja(k), re.I)
                    and isinstance(v, str)
                    and len(v.strip()) > 3
                    and not re.fullmatch(r"[\d\s./:-]+", v.strip())
                ):
                    desc = v.strip()
                    break
            if desc:
                break
    autoridad = str(plano.get("autoridadAplicacion") or d.get("autoridadAplicacion") or "").strip()
    if autoridad and desc and autoridad.lower() not in desc.lower():
        desc = f"{desc} ({autoridad})"
    if not desc:
        partes = []
        for etiqueta, patron in (
            ("Causa", r"estado_?causa|causa_?estado"),
            ("Cupón", r"estado_?cup|cup[oó]n_?estado"),
            ("Vence", r"vencim|vto"),
        ):
            for k, v in plano.items():
                if re.search(patron, k.replace(".", "_"), re.I) and v not in (None, ""):
                    partes.append(f"{etiqueta}: {_fmt_fecha(v) if etiqueta == 'Vence' else v}")
                    break
        desc = " · ".join(partes) or "Infracción de tránsito"

    etiquetas = _etiquetas_json(plano)
    estado_pub = d.get("estadoCausaPublico")
    if isinstance(estado_pub, dict):
        ep_txt = str(estado_pub.get("descripcion") or "")
        if "juzgamiento" in ep_txt.lower() or "controlador" in ep_txt.lower():
            if "MULTA CON CONTROLADOR" not in etiquetas:
                etiquetas.append("MULTA CON CONTROLADOR")
    return Infraccion(acta=acta[:30], descripcion=desc[:140], monto=monto, etiquetas=etiquetas)


def _json_a_infracciones(data) -> tuple[List[Infraccion], bool]:
    if isinstance(data, dict) and isinstance(data.get("infracciones"), list):
        if data.get("totalInfracciones", len(data["infracciones"])) == 0 and not data["infracciones"]:
            return [], True
        out_pba: List[Infraccion] = []
        for d in data["infracciones"]:
            if isinstance(d, dict):
                inf = _extraer_infraccion(d)
                if inf is not None:
                    out_pba.append(inf)
        if out_pba or data.get("totalInfracciones") == 0:
            return out_pba, True

    listas: list = []
    vacias: list = []
    _listas_de_dicts(data, listas, vacias)
    out: List[Infraccion] = []
    for lista in listas:
        for d in lista:
            inf = _extraer_infraccion(d)
            if inf is not None:
                out.append(inf)
    return out, bool(vacias)


def _limpiar_desc(texto: str) -> str:
    t = re.sub(r"(?i)se debe resolver con un controlador\.?", " ", texto)
    t = re.sub(r"(?i)puntos\s+a\s+(?:descontar|resignar):?\s*\d*(?:\s*puntos?(?:\s+a\s+(?:descontar|resignar))?)?", " ", t)
    t = re.sub(r"(?i)pago\s*voluntario", " ", t)
    return re.sub(r"\s+", " ", t).strip(" -–.:")


def _actas_en_texto(texto: str) -> List[Infraccion]:
    marcas = list(RE_ACTA_INICIO.finditer(texto))
    out: List[Infraccion] = []
    for n, m in enumerate(marcas):
        fin = marcas[n + 1].start() if n + 1 < len(marcas) else len(texto)
        resto = RE_CORTE_ACTA.split(texto[m.end():fin], maxsplit=1)[0][:600]
        ma = re.search(r"\$\s*[\d.,]+", resto)
        desc_raw = resto[: ma.start()] if ma else resto[:220]
        out.append(Infraccion(
            acta=m.group(1)[:30],
            descripcion=(_limpiar_desc(desc_raw) or "Infracción de tránsito")[:140],
            monto=limpiar_monto(ma.group(0)) if ma else None,
            etiquetas=_etiquetas(resto),
        ))
    return out


def _meta_listado(texto: str) -> dict:
    meta: dict = {}
    m = re.search(r"Infracciones\s+(?:totales|cometidas):?\s*(\d+)", texto, re.I)
    if m:
        meta["declaradas"] = int(m.group(1))
    m = re.search(r"Monto\s+total:?\s*(?:Hasta:?\s*(\d{2}-\d{2}-\d{4}))?\s*((?:\$\s*[\d.,]+\s*){1,3})", texto, re.I)
    if m:
        valores = [v for v in (limpiar_monto(x) for x in re.findall(r"\$\s*[\d.,]+", m.group(2))) if v is not None]
        if valores:
            meta["total_oficial"] = valores[-1]
        if m.group(1):
            meta["vigencia"] = m.group(1)
    if re.search(r"no incluye las actas inhabilitadas a resolver con un controlador", texto, re.I):
        meta["nota"] = "El total informado no incluye las actas a resolver con un controlador."
    return meta


def _hay_listas_con_datos(data) -> bool:
    acc: list = []
    _listas_de_dicts(data, acc, [])
    return bool(acc)


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
    muestra = re.sub(r"\s+", " ", cuerpo)[: 4000 if "json" in ctype else 800]

    if resp.status_code >= 400:
        if RE_CAPTCHA_MAL.search(cuerpo):
            raise CaptchaError("El portal rechazó el token del captcha")
        extra = " (posible bloqueo por IP extranjera / WAF)" if resp.status_code in (403, 429) else ""
        raise ConsultaIndeterminada(f"HTTP {resp.status_code}{extra}", resp.status_code, muestra)

    if "json" in ctype or cuerpo.lstrip().startswith(("{", "[")):
        try:
            data = resp.json()
        except ValueError:
            data = None
        if data is not None:
            items, hay_lista_vacia = _json_a_infracciones(data)
            if items:
                return RespuestaPortal(_dedup(items), resp.status_code, muestra)
            if RE_CAPTCHA_MAL.search(cuerpo):
                raise CaptchaError("El portal rechazó el token del captcha")
            if _hay_listas_con_datos(data):
                raise ConsultaIndeterminada(
                    "El portal devolvió datos con un formato que todavía no se reconoce.",
                    resp.status_code,
                    muestra,
                )
            if hay_lista_vacia or RE_VACIO.search(cuerpo):
                return RespuestaPortal([], resp.status_code, muestra)
            raise ConsultaIndeterminada("JSON sin estructura de infracciones reconocible", resp.status_code, muestra)

    items = _tabla_a_infracciones(BeautifulSoup(cuerpo, "html.parser"))
    if items:
        return RespuestaPortal(_dedup(items), resp.status_code, muestra)

    visible = texto_visible(BeautifulSoup(cuerpo, "html.parser"))
    muestra = visible[:800] or muestra
    items = _actas_en_texto(visible)
    if items:
        meta = _meta_listado(visible)
        return RespuestaPortal(
            _dedup(items),
            resp.status_code,
            muestra,
            total_oficial=meta.get("total_oficial"),
            declaradas=meta.get("declaradas"),
            nota=meta.get("nota", ""),
            vigencia=meta.get("vigencia", ""),
        )
    if RE_CAPTCHA_MAL.search(visible):
        raise CaptchaError("El portal rechazó el token del captcha")
    if RE_VACIO.search(visible):
        return RespuestaPortal([], resp.status_code, muestra)
    raise ConsultaIndeterminada(
        "Respuesta sin tabla de infracciones ni mensaje de 'sin infracciones' (¿cambió el portal?)",
        resp.status_code,
        muestra,
    )