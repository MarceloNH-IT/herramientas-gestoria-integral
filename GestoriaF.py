# -*- coding: utf-8 -*-
"""
Gestoría Integral | Buscador de infracciones por patente
Ejecutar con:  streamlit run app.py
Requisitos:    pip install streamlit pandas
IMPORTANTE:    guardar este archivo con codificación UTF-8 (evita los textos rotos "Ã³", "â€”").
"""
from __future__ import annotations

import asyncio
import html
import random
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, List

import streamlit as st

# =============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# =============================================================================
st.set_page_config(
    page_title="Buscar infracciones por patente",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;800;900&display=swap');

html, body, [class*="css"], .stApp, input, button { font-family: 'Rubik', sans-serif !important; }
.stApp { background: #f7f6f2; color: #0f172a; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
.block-container { max-width: 1080px; padding-top: 1.2rem; padding-bottom: 4rem; }
#MainMenu, footer { visibility: hidden; }

/* ---------- HERO ---------- */
.hero {
  background: linear-gradient(135deg, #ffe45c 0%, #fff0a0 55%, #f8eeb0 100%);
  border: 1px solid #ecd45a; border-radius: 28px; padding: 2rem 2rem 1.6rem;
  margin-bottom: 1rem;
}
.hero h1 { font-weight: 900; font-size: 3rem; line-height: 1.02; letter-spacing: -0.03em;
  color: #0b1220; margin: 0 0 .8rem 0; }
.hero p.lead { color: #3b3a2f; font-size: 1.02rem; margin: 0 0 1rem 0; font-weight: 500; }
.pill { display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,.55);
  border: 1px solid rgba(0,0,0,.06); border-radius: 999px; padding: 7px 14px;
  font-size: .8rem; font-weight: 700; color: #111827; margin: 0 8px 8px 0; }
.panel { background: rgba(255,255,255,.55); border: 1px solid rgba(0,0,0,.06);
  border-radius: 18px; padding: 1rem 1.2rem; margin-top: .6rem; }
.panel-head { display:flex; justify-content:space-between; align-items:center; }
.panel-title { font-weight: 800; font-size: 1rem; color:#0b1220; }
.panel-tag { font-size:.72rem; font-weight:700; color:#6b6a5c; }
.panel-sub { font-size:.78rem; font-weight:700; color:#6b6a5c; margin:.35rem 0 .7rem; }
.chip { display:inline-flex; align-items:center; gap:7px; background:#fff; border-radius:999px;
  padding:7px 14px; font-size:.82rem; font-weight:500; margin:0 8px 8px 0;
  box-shadow: 0 2px 6px rgba(0,0,0,.06); }
.dot { width:8px; height:8px; border-radius:50%; background:#22c55e; display:inline-block; }
.steps { display:grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: .8rem; }
.step { background: rgba(255,255,255,.6); border: 1px solid rgba(0,0,0,.06); border-radius: 18px;
  padding: .9rem 1.1rem; }
.step b.t { display:flex; align-items:center; gap:10px; font-size:.95rem; color:#0b1220; }
.step .n { background:#ffe45c; border-radius:50%; width:26px; height:26px; display:inline-flex;
  align-items:center; justify-content:center; font-weight:800; font-size:.8rem; }
.step small { color:#6b7280; display:block; margin-top:.4rem; font-size:.78rem; }

/* ---------- BUSCADOR (st.form) ---------- */
[data-testid="stForm"] { background:#fff; border:1px solid #e7e5dc; border-radius: 24px;
  padding: 1.1rem 1.3rem; box-shadow: 0 6px 20px rgba(0,0,0,.04); }
[data-testid="stForm"] label p { font-weight: 800; font-size: 1.05rem; color:#0b1220; }
[data-testid="stForm"] input { border-radius: 14px !important; background:#fff !important;
  color:#0f172a !important; text-transform: uppercase; letter-spacing:.04em; }
[data-testid="stForm"] [data-baseweb="input"] { border-radius: 14px; border:1px solid #d9d7cc;
  background:#fff; }
[data-testid="stFormSubmitButton"] button { background: linear-gradient(135deg,#5b8def,#8db4fa);
  color:#fff; border:0; border-radius:16px; font-weight:600; height:3rem; width:100%; }
[data-testid="stFormSubmitButton"] button:hover { filter: brightness(1.05); color:#fff; }

/* ---------- RESULTADOS ---------- */
.jchip { display:inline-block; border-radius:999px; padding:8px 16px; font-weight:800;
  font-size:.78rem; margin:0 8px 8px 0; text-transform:uppercase; box-shadow:0 3px 8px rgba(0,0,0,.08);
  text-decoration:none !important; color:#111827 !important; }
.card { background:#fff; border:1px solid #e7e5dc; border-radius:22px; padding:1.2rem 1.3rem;
  margin-top:1rem; }
.card h3 { font-weight:900; font-size:1.5rem; margin:0 0 .8rem 0; color:#0b1220; display:flex;
  align-items:center; gap:10px; }
.card h3 i { width:12px; height:12px; border-radius:50%; display:inline-block; }
table.t { width:100%; border-collapse:collapse; font-size:.85rem; }
table.t th { background:#efefef; color:#6b7280; font-size:.7rem; letter-spacing:.12em;
  text-transform:uppercase; padding:.7rem; text-align:center; }
table.t td { padding:.75rem; text-align:center; color:#111827; }
table.t tr:nth-child(odd) td { background:#fffbe6; }
.tag { display:inline-block; background:linear-gradient(135deg,#7c3aed,#5b21b6); color:#fff;
  font-size:.62rem; font-weight:800; padding:4px 10px; border-radius:999px; margin-bottom:4px; }
.warn { background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; border-radius:14px;
  padding:.8rem 1rem; font-size:.88rem; margin-top:1rem; }
.ok { background:#f0fdf4; border:1px solid #bbf7d0; color:#166534; border-radius:14px;
  padding:.8rem 1rem; font-size:.9rem; margin-top:1rem; }
a.portal { color:#2563eb; font-weight:600; text-decoration:none; }

/* Resumen flotante */
.float { position:fixed; top:90px; right:24px; width:250px; background:#fffef8; z-index:50;
  border-radius:22px; box-shadow:0 12px 40px rgba(0,0,0,.18); padding:1rem; border:1px solid #eee7c0; }
.float .h { font-weight:800; font-size:1rem; padding-bottom:.6rem; border-bottom:1px solid #eee; }
.float .s { font-size:.65rem; letter-spacing:.14em; color:#9ca3af; font-weight:800; margin:.7rem 0 .4rem; }
.float .row { display:flex; justify-content:space-between; align-items:center; border-radius:14px;
  padding:.5rem .7rem; margin-bottom:6px; font-weight:800; font-size:.8rem; }
.float .row span.m { text-align:right; font-weight:500; font-size:.78rem; line-height:1.1; }
.float .row span.m small { display:block; color:#6b7280; font-weight:700; font-size:.65rem; }
.float .tot { border:1px solid #e5e7eb; border-radius:14px; text-align:center; padding:.6rem;
  background:#fff; font-size:1rem; }
@media (max-width: 1500px) { .float { position:static; width:auto; margin-top:1rem; } }

/* ---------- OVERLAY DE CARGA ---------- */
.ov { position:fixed; inset:0; background:rgba(120,125,135,.45); backdrop-filter: blur(6px);
  z-index:9999; display:flex; align-items:center; justify-content:center; }
.ovc { background:#fafaf6; width:min(560px,90vw); border-radius:28px; padding:1.6rem 1.8rem;
  text-align:center; box-shadow:0 24px 60px rgba(0,0,0,.25); }
.ovc .logo { width:52px; height:52px; border-radius:12px; background:#000; margin:0 auto .6rem;
  display:flex; align-items:center; justify-content:center; }
.ovc .spin { width:28px; height:28px; border-radius:50%; border:4px solid #fff;
  border-top-color:#facc15; animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.ovc h2 { font-weight:500; font-size:1.7rem; margin:.2rem 0; color:#111827; }
.ovc .st { font-weight:800; color:#6b7280; font-size:.9rem; margin:.5rem 0 1rem; }
.bar { height:12px; background:#e5e7eb; border-radius:99px; overflow:hidden; }
.bar > div { height:100%; background:#facc15; border-radius:99px; transition: width .2s; }
.ovc .tip { font-size:.72rem; color:#6b7280; font-weight:700; margin-top:1rem; }

@media (max-width: 800px) { .hero h1 { font-size: 2.1rem; } .steps { grid-template-columns: 1fr; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# =============================================================================
# 2. MODELOS DE DATOS
# =============================================================================
@dataclass
class Infraccion:
    acta: str
    descripcion: str
    monto: float | None  # None = sin monto informado
    controlador: bool = False


@dataclass
class ResultadoJurisdiccion:
    nombre: str
    proteccion: str
    url: str
    conectado: bool = False  # True solo cuando existe un scraper real
    error: str = ""
    demo: bool = False
    infracciones: List[Infraccion] = field(default_factory=list)

    @property
    def subtotal(self) -> float:
        return sum(i.monto or 0 for i in self.infracciones)


@dataclass
class JurisdiccionConfig:
    nombre: str
    proteccion: str  # "Sin CAPTCHA" | "reCAPTCHA" | "CAPTCHA Texto" | "Cloudflare"
    url: str
    consultar: Callable[[str], Awaitable[List[Infraccion]]] | None = None
    # `consultar` es el lugar donde se programa el scraper real de cada portal.
    # Debe devolver la lista de Infraccion (vacía si no hay multas) o lanzar excepción.


# =============================================================================
# 3. CONECTORES (acá se enchufan los scrapers reales, uno por jurisdicción)
# =============================================================================
# Ejemplo de cómo se completa un conector real (Playwright / requests):
#
#   async def scrap_rosario(patente: str) -> List[Infraccion]:
#       ...  # navegar, completar la patente, parsear la tabla
#       return [Infraccion("12345", "Exceso de velocidad", 45000.0)]
#
# y luego en JURISDICCIONES poner  consultar=scrap_rosario
JURISDICCIONES: List[JurisdiccionConfig] = [
    JurisdiccionConfig("Posadas (Misiones)", "Sin CAPTCHA", "https://sistema.posadas.gov.ar/mp_sistemas/autogestion/consultarmultadominio"),
    JurisdiccionConfig("Rosario", "Sin CAPTCHA", "https://www.rosario.gob.ar/gdm/patente.do?accion=ir"),
    JurisdiccionConfig("Lomas de Zamora", "Sin CAPTCHA", "https://webextra.lomasdezamora.gov.ar/infracciones/ConsultaFaltasNuevoMP.aspx"),
    JurisdiccionConfig("Córdoba Caminera", "Sin CAPTCHA", "https://www.rentascordoba.gob.ar/emision/ver-y-pagar/caminera"),
    JurisdiccionConfig("PBA", "reCAPTCHA", "https://infraccionesba.gba.gob.ar/consulta-infraccion"),
    JurisdiccionConfig("CABA", "reCAPTCHA", "https://buenosaires.gob.ar/licenciasdeconducir/consulta-de-infracciones/?actas=transito"),
    JurisdiccionConfig("Ezeiza", "reCAPTCHA", "https://consulta-web.infratrack.com.ar/consultas.php?municipio=ezeiza"),
    JurisdiccionConfig("Entre Ríos", "reCAPTCHA", "https://monitoreovialentrerios.info/#/consulta-infracciones"),
    JurisdiccionConfig("Misiones", "reCAPTCHA", "https://monitoreovialmisiones.info/#/"),
    JurisdiccionConfig("Lanús", "reCAPTCHA", "https://tramitesweb.lanus.gob.ar/lanusdigital/mis-dominios"),
    JurisdiccionConfig("Santa Fe", "CAPTCHA Texto", "https://www.santafe.gov.ar/juzgadovirtual/consultaInfraccion.do?method=BusquedaVehiculo"),
    JurisdiccionConfig("Vicente López", "Cloudflare", "https://infracciones.vicentelopez.gov.ar/causas-vecino"),
    JurisdiccionConfig("Avellaneda", "Cloudflare", "https://multas.mda.gob.ar"),
]

# Colores (fondo del chip, color del punto) que se asignan por jurisdicción
PALETA = [
    ("#ffdf5c", "#f5c400"), ("#a5d8ff", "#3b9cf0"), ("#d4c1ff", "#9b7bf0"),
    ("#b9f0cf", "#34c776"), ("#ffd0c2", "#f4724e"), ("#ffc9e3", "#e8559f"),
    ("#c7f0f0", "#2cb5b5"), ("#e6dcc8", "#a58d62"),
]


def color_de(nombre: str) -> tuple[str, str]:
    idx = [j.nombre for j in JURISDICCIONES].index(nombre) % len(PALETA)
    return PALETA[idx]


# =============================================================================
# 4. MOTOR DE EJECUCIÓN
# =============================================================================
PATRON_PATENTE = re.compile(r"^([A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2}|[A-Z]\d{3}[A-Z]{3}|\d{3}[A-Z]{3})$")


def normalizar_patente(texto: str) -> str:
    return re.sub(r"[\s\-.]", "", texto or "").upper()


def pesos(valor: float | None) -> str:
    if valor is None:
        return "-"
    s = f"{valor:,.2f}"  # 1,234.50
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _demo_infracciones(patente: str, nombre: str) -> List[Infraccion]:
    """Datos SIMULADOS, solo para probar el diseño. Nunca se usan salvo modo demo."""
    rnd = random.Random(f"{patente}-{nombre}")
    if rnd.random() < 0.45:
        return []
    textos = [
        "Circular por zona/carril prohibido",
        "Estac. lugar sin ticket/hora vencida",
        "No uso cinturón de seguridad",
        "Exceso de velocidad",
        "Cruzar semáforo en rojo",
    ]
    return [
        Infraccion(
            acta=f"{rnd.choice('QIAF')}{rnd.randint(10_000_000, 99_999_999)}",
            descripcion=rnd.choice(textos),
            monto=float(rnd.randint(40, 600) * 1000) + rnd.choice([0, 0, 62]),
            controlador=rnd.random() < 0.3,
        )
        for _ in range(rnd.randint(1, 4))
    ]


async def _consultar_una(cfg: JurisdiccionConfig, patente: str, demo: bool) -> ResultadoJurisdiccion:
    base = ResultadoJurisdiccion(cfg.nombre, cfg.proteccion, cfg.url)
    try:
        if cfg.consultar is not None:
            base.infracciones = await asyncio.wait_for(cfg.consultar(patente), timeout=45)
            base.conectado = True
        elif demo:
            await asyncio.sleep(random.uniform(0.2, 0.7))
            base.infracciones = _demo_infracciones(patente, cfg.nombre)
            base.conectado = True
            base.demo = True
        else:
            await asyncio.sleep(0.05)  # sin conector todavía
    except Exception as exc:  # un portal caído no debe romper al resto
        base.error = f"{type(exc).__name__}: {exc}"
    return base


async def ejecutar_consultas(patente, lista, demo, on_progress) -> List[ResultadoJurisdiccion]:
    tareas = [asyncio.create_task(_consultar_una(j, patente, demo)) for j in lista]
    resultados: List[ResultadoJurisdiccion] = []
    total = len(tareas)
    for hecha in asyncio.as_completed(tareas):
        r = await hecha
        resultados.append(r)
        on_progress(len(resultados), total, r.nombre)
    orden = {j.nombre: i for i, j in enumerate(JURISDICCIONES)}
    return sorted(resultados, key=lambda r: orden[r.nombre])


def overlay(pct: int, estado: str) -> str:
    return (
        '<div class="ov"><div class="ovc">'
        '<div class="logo"><div class="spin"></div></div>'
        '<h2>Buscando multas…</h2>'
        f'<div class="st">{html.escape(estado)}</div>'
        f'<div class="bar"><div style="width:{max(pct, 6)}%"></div></div>'
        '<div class="tip">Tip: el resumen flotante te permitirá navegar rápidamente.</div>'
        '</div></div>'
    )


# =============================================================================
# 5. INTERFAZ
# =============================================================================
n_jur = len(JURISDICCIONES)
chips = "".join(f'<span class="chip"><span class="dot"></span>{html.escape(j.nombre)}</span>' for j in JURISDICCIONES)

st.markdown(
    '<div class="hero">'
    '<h1>Buscar infracciones<br>por patente</h1>'
    '<p class="lead">Consulta en todas las jurisdicciones disponibles. Resultados claros y simples.</p>'
    '<span class="pill">⚡ Resultados en segundos</span>'
    '<span class="pill">🛡️ Fuentes oficiales</span>'
    f'<span class="pill">📍 {n_jur} jurisdicciones consultadas</span>'
    '<div class="panel">'
    '<div class="panel-head"><span class="panel-title">Jurisdicciones consultadas</span>'
    '<span class="panel-tag">Servicio activo</span></div>'
    '<div class="panel-sub">Se consultan automáticamente.</div>'
    f'{chips}</div>'
    '<div class="steps">'
    '<div class="step"><b class="t"><span class="n">1</span>Ingresá tu patente (sin espacios)</b>'
    '<small>Formatos válidos: LLLNNN · LLNNNLL · LNNNLLL · NNNLLL</small></div>'
    f'<div class="step"><b class="t"><span class="n">2</span>Consultamos {n_jur} jurisdicciones</b>'
    '<small>Unificamos los resultados.</small></div>'
    '<div class="step"><b class="t"><span class="n">3</span>Resultado completo</b>'
    '<small>Detalle y totales claros.</small></div>'
    '</div></div>',
    unsafe_allow_html=True,
)

with st.form("buscador", clear_on_submit=False, border=True):
    patente_input = st.text_input(
        "Patente",
        placeholder="INGRESÁ TU PATENTE (LLLNNN · LLNNNLL · LNNNLLL · NNNLLL)",
        max_chars=10,
    )
    c1, c2 = st.columns([3, 1])
    with c1:
        modo = st.selectbox(
            "Jurisdicciones",
            ["Todas", "Solo sin CAPTCHA", "Solo con CAPTCHA / Cloudflare"],
            label_visibility="collapsed",
        )
    with c2:
        enviar = st.form_submit_button("🔎  Consultar", use_container_width=True)

with st.expander("⚙️ Opciones de desarrollo"):
    demo = st.checkbox(
        "Modo demo (datos SIMULADOS, solo para probar el diseño)",
        value=False,
        help="Apagado por defecto. Con esto activo NO se consulta ningún portal real.",
    )

# --- Ejecución ---------------------------------------------------------------
if enviar:
    dominio = normalizar_patente(patente_input)
    if not PATRON_PATENTE.match(dominio):
        st.error("Formato de patente inválido. Ejemplos: HNQ904, AB123CD, A123BCD, 123ABC.")
    else:
        if modo == "Solo sin CAPTCHA":
            lista = [j for j in JURISDICCIONES if j.proteccion == "Sin CAPTCHA"]
        elif modo == "Solo con CAPTCHA / Cloudflare":
            lista = [j for j in JURISDICCIONES if j.proteccion != "Sin CAPTCHA"]
        else:
            lista = JURISDICCIONES

        ph = st.empty()
        ph.markdown(overlay(0, "Preparando consulta"), unsafe_allow_html=True)

        def _progreso(hechas: int, total: int, nombre: str) -> None:
            ph.markdown(overlay(int(hechas / total * 100), f"Consultado: {nombre} ({hechas}/{total})"), unsafe_allow_html=True)

        res = asyncio.run(ejecutar_consultas(dominio, lista, demo, _progreso))
        ph.empty()
        st.session_state["resultados"] = res
        st.session_state["patente"] = dominio

# --- Resultados --------------------------------------------------------------
if "resultados" in st.session_state:
    resultados: List[ResultadoJurisdiccion] = st.session_state["resultados"]
    dominio = st.session_state["patente"]

    conectados = [r for r in resultados if r.conectado]
    con_multas = [r for r in conectados if r.infracciones]
    sin_conector = [r for r in resultados if not r.conectado]
    total = sum(r.subtotal for r in con_multas)
    hay_demo = any(r.demo for r in resultados)

    # Resumen flotante
    filas = ""
    for r in con_multas:
        bg, _ = color_de(r.nombre)
        n = len(r.infracciones)
        filas += (
            f'<div class="row" style="background:{bg}55"><span>{html.escape(r.nombre.upper()[:9])}</span>'
            f'<span class="m"><small>{n} multa{"s" if n != 1 else ""}</small>{pesos(r.subtotal)}</span></div>'
        )
    if con_multas:
        st.markdown(
            '<div class="float"><div class="h">Resumen</div><div class="s">JURISDICCIONES</div>'
            f'{filas}<div class="s">TOTAL GENERAL</div><div class="tot">{pesos(total)}</div></div>',
            unsafe_allow_html=True,
        )

    # Cabecera de resultados
    jchips = "".join(
        f'<a class="jchip" href="#j{i}" style="background:{color_de(r.nombre)[0]}">'
        f'{html.escape(r.nombre)} ({len(r.infracciones)})</a>'
        for i, r in enumerate(con_multas)
    )
    if con_multas:
        intro = "Encontramos información para la patente consultada."
    elif conectados:
        intro = "No encontramos infracciones en las jurisdicciones consultadas."
    else:
        intro = "Todavía no hay consulta automática activa para estas jurisdicciones."
    st.markdown(
        '<div class="hero" style="margin-top:1.2rem">'
        '<h1>Resultado de búsqueda<br>por patente</h1>'
        f'<p class="lead">{intro}</p>'
        f'<span class="pill">Patente &nbsp; <b>{html.escape(dominio)}</b></span>'
        + (
            '<div class="panel"><div class="panel-title">Jurisdicciones</div>'
            '<div class="panel-sub">Tocá una jurisdicción para navegar al detalle (se muestra cantidad de multas).</div>'
            f'{jchips}</div>'
            if con_multas else ""
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    if hay_demo:
        st.markdown('<div class="warn">⚠️ <b>Modo demo:</b> los datos mostrados son simulados, no corresponden a multas reales.</div>', unsafe_allow_html=True)

    # Tablas por jurisdicción
    for i, r in enumerate(con_multas):
        _, dot = color_de(r.nombre)
        filas_t = ""
        for inf in r.infracciones:
            tag = '<span class="tag">MULTA CON CONTROLADOR</span><br>' if inf.controlador else ""
            filas_t += (
                f"<tr><td>{html.escape(inf.acta)}</td>"
                f"<td>{tag}{html.escape(inf.descripcion)}</td>"
                f"<td>{pesos(inf.monto)}</td></tr>"
            )
        st.markdown(
            f'<div class="card" id="j{i}"><h3><i style="background:{dot}"></i>Multas {html.escape(r.nombre)}</h3>'
            '<table class="t"><thead><tr><th>N° Acta</th><th>Descripción</th><th>Monto</th></tr></thead>'
            f"<tbody>{filas_t}</tbody></table></div>",
            unsafe_allow_html=True,
        )

    if conectados and not con_multas:
        st.markdown(f'<div class="ok">✅ La patente {html.escape(dominio)} no registra infracciones en las jurisdicciones consultadas.</div>', unsafe_allow_html=True)

    # Jurisdicciones sin conector o con error
    if sin_conector:
        filas_p = "".join(
            f'<tr><td>{html.escape(r.nombre)}</td><td>{html.escape(r.proteccion)}</td>'
            f'<td>{"⚠️ " + html.escape(r.error) if r.error else "🛠️ Conector pendiente"}</td>'
            f'<td><a class="portal" href="{html.escape(r.url)}" target="_blank" rel="noopener">Abrir portal ↗</a></td></tr>'
            for r in sin_conector
        )
        st.markdown(
            '<div class="card"><h3><i style="background:#9ca3af"></i>Consulta manual en el portal oficial</h3>'
            f'<p style="color:#6b7280;font-size:.88rem;margin-top:-.4rem">Copiá la patente <b>{html.escape(dominio)}</b> y consultala en cada portal. '
            'Estas jurisdicciones todavía no tienen scraper automático.</p>'
            '<table class="t"><thead><tr><th>Jurisdicción</th><th>Protección</th><th>Estado</th><th>Acceso</th></tr></thead>'
            f"<tbody>{filas_p}</tbody></table></div>",
            unsafe_allow_html=True,
        )
