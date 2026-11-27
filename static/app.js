const WA_NUM = "5491122533325";
let ultimoJsonTexto = "";
let ultimaPatente = "";

function construirUrlWhatsApp(texto) {
  return `https://wa.me/${WA_NUM}?text=${encodeURIComponent(texto)}`;
}

function inicializarEnlacesContacto() {
  const saludo = "Hola Marcelo, quiero hacer una consulta por infracciones / gestoría.";
  const url = construirUrlWhatsApp(saludo);
  const navWa = document.getElementById("nav-wa");
  const heroWa = document.getElementById("hero-wa");
  const fabWa = document.getElementById("fab-wa");
  if (navWa) navWa.href = url;
  if (heroWa) heroWa.href = url;
  if (fabWa) fabWa.href = url;
}

function escaparHtml(texto) {
  return String(texto ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function cargarServidores() {
  const listaEl = document.getElementById("servers-list");
  const actEl = document.getElementById("servers-updated");
  if (!listaEl || !actEl) return;

  try {
    const resp = await fetch("/api/servidores");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    const hora = new Date(data.actualizado_en).toLocaleTimeString("es-AR", {
      hour: "2-digit",
      minute: "2-digit",
    });
    actEl.textContent = `Actualizado ${hora}`;

    listaEl.innerHTML = data.servidores
      .map((s) => {
        const estado = s.estado || "pendiente";
        const detalle = estado === "ok" ? `${s.ms} ms` : estado;
        return `
          <span class="srv-chip">
            <span class="dot ${escaparHtml(estado)}"></span>
            ${escaparHtml(s.jurisdiccion)}
            <small style="color:#9aa8c7;">${escaparHtml(detalle)}</small>
          </span>
        `;
      })
      .join("");
  } catch (err) {
    actEl.textContent = "Sin conexión con API";
    listaEl.innerHTML = `<span class="srv-chip">No se pudo verificar el estado de portales</span>`;
  }
}

function mostrarError(msg) {
  const el = document.getElementById("form-error");
  if (!el) return;
  el.textContent = msg;
  el.style.display = "block";
}

function ocultarError() {
  const el = document.getElementById("form-error");
  if (!el) return;
  el.style.display = "none";
}

function abrirModalCarga(patente) {
  const statusEl = document.getElementById("loading-status");
  const barEl = document.getElementById("loading-bar");
  const modalEl = document.getElementById("loading-modal");
  if (statusEl) statusEl.textContent = `Consultando jurisdicciones para ${patente}...`;
  if (barEl) barEl.style.width = "55%";
  if (modalEl) modalEl.style.display = "flex";
}

function cerrarModalCarga() {
  const barEl = document.getElementById("loading-bar");
  const modalEl = document.getElementById("loading-modal");
  if (barEl) barEl.style.width = "100%";
  setTimeout(() => {
    if (modalEl) modalEl.style.display = "none";
  }, 180);
}

function renderizarResultados(data) {
  const sec = document.getElementById("resultados-section");
  const headEl = document.getElementById("res-header");
  const alertsEl = document.getElementById("res-alerts");
  const jurEl = document.getElementById("res-jurisdicciones");
  const portalesEl = document.getElementById("res-portales");
  const floatEl = document.getElementById("resumen-flotante");

  if (sec) sec.style.display = "block";
  ultimaPatente = data.patente;

  const conMultas = (data.jurisdicciones || []).filter((j) => j.estado === "con_multas");
  const porJur = (data.resumen && data.resumen.por_jurisdiccion) || [];

  const chipsHtml = porJur
    .map(
      (item, idx) =>
        `<a class="nav-chip" href="#jur-${idx}">${escaparHtml(item.jurisdiccion)} (${item.multas})</a>`
    )
    .join("");

  if (headEl) {
    headEl.innerHTML = `
      <h2>RESULTADO DE LA BÚSQUEDA</h2>
      <div class="plate-pill">${escaparHtml(data.patente)}</div>
      <p style="margin:0;color:#c6d0e6;">
        ${
          data.resumen.cantidad_multas > 0
            ? "Se encontraron infracciones registradas en los portales consultados."
            : "No se encontraron infracciones en las jurisdicciones que respondieron."
        }
      </p>
      <div class="kpis-grid">
        <div class="kpi-box">
          <strong>${escaparHtml(data.resumen.total_general_formato)}</strong>
          <span>Total general</span>
        </div>
        <div class="kpi-box">
          <strong>${data.resumen.cantidad_multas}</strong>
          <span>Multas encontradas</span>
        </div>
        <div class="kpi-box">
          <strong>${data.resumen.jurisdicciones_con_multas}</strong>
          <span>Jurisdicciones c/ multas</span>
        </div>
        <div class="kpi-box">
          <strong>${data.resultado_completo ? "COMPLETO" : "PARCIAL"}</strong>
          <span>Estado consulta</span>
        </div>
      </div>
      ${chipsHtml ? `<div class="chips-nav">${chipsHtml}</div>` : ""}
    `;
  }

  let alertasHtml = "";
  if (!data.resultado_completo && Array.isArray(data.no_se_pudo_consultar) && data.no_se_pudo_consultar.length > 0) {
    const nombres = data.no_se_pudo_consultar.map((x) => x.jurisdiccion).join(", ");
    alertasHtml += `
      <div class="alert alert-warn">
        <strong>Resultado parcial:</strong> no se pudo completar la consulta en ${escaparHtml(nombres)}.
      </div>
    `;
  }
  if (alertsEl) alertsEl.innerHTML = alertasHtml;

  if (floatEl) {
    if (conMultas.length > 0) {
      floatEl.style.display = "block";
      const rowsHtml = porJur
        .map(
          (item) => `
          <div class="summary-row">
            <div>
              <strong>${escaparHtml(item.jurisdiccion)}</strong>
              <small>${item.multas} multa${item.multas === 1 ? "" : "s"}</small>
            </div>
            <span class="summary-amount">${escaparHtml(item.subtotal_formato)}</span>
          </div>
        `
        )
        .join("");

      floatEl.innerHTML = `
        <h3>RESUMEN</h3>
        ${rowsHtml}
        <div class="summary-total">
          <span>TOTAL GENERAL</span>
          <strong>${escaparHtml(data.resumen.total_general_formato)}</strong>
        </div>
      `;

      const msgWa = `Hola Marcelo, consulté la patente ${data.patente} y tiene ${data.resumen.cantidad_multas} multa(s) por ${data.resumen.total_general_formato}. Quiero asesoramiento.`;
      const fabWa = document.getElementById("fab-wa");
      if (fabWa) fabWa.href = construirUrlWhatsApp(msgWa);
    } else {
      floatEl.style.display = "none";
    }
  }

  if (jurEl) {
    jurEl.innerHTML = conMultas
      .map((j, idx) => {
        const filas = (j.multas || [])
          .map((m) => {
            const tags = (m.etiquetas || [])
              .map((t) => `<span class="pill-tag">${escaparHtml(t)}</span>`)
              .join("");
            return `
              <tr>
                <td><strong>${escaparHtml(m.acta)}</strong></td>
                <td>${tags}<div>${escaparHtml(m.descripcion)}</div></td>
                <td><strong>${escaparHtml(m.monto_formato)}</strong></td>
              </tr>
            `;
          })
          .join("");

        return `
          <div id="jur-${idx}" class="card">
            <div class="card-header">
              <h3>MULTAS ${escaparHtml(j.jurisdiccion.toUpperCase())}</h3>
              <span>${j.multas.length} · ${escaparHtml(j.subtotal_formato)}</span>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>N° Acta</th>
                    <th>Descripción</th>
                    <th>Monto</th>
                  </tr>
                </thead>
                <tbody>${filas}</tbody>
              </table>
            </div>
          </div>
        `;
      })
      .join("");
  }

  if (portalesEl) {
    const filasPortales = (data.jurisdicciones || [])
      .map(
        (j) => `
        <tr>
          <td><strong>${escaparHtml(j.jurisdiccion)}</strong></td>
          <td><span class="status-badge st-${escaparHtml(j.estado)}">${escaparHtml(j.estado)}</span></td>
          <td>${escaparHtml(j.detalle || "—")}</td>
          <td><a href="${escaparHtml(j.url)}" target="_blank" rel="noopener" style="color:#1d4ed8;font-weight:700;">Abrir ↗</a></td>
        </tr>
      `
      )
      .join("");

    portalesEl.innerHTML = `
      <div class="card-header">
        <h3>ESTADO DE CADA PORTAL</h3>
        <span>${(data.jurisdicciones || []).length} jurisdicciones</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Jurisdicción</th>
              <th>Estado</th>
              <th>Detalle</th>
              <th>Portal</th>
            </tr>
          </thead>
          <tbody>${filasPortales}</tbody>
        </table>
      </div>
    `;
  }

  ultimoJsonTexto = JSON.stringify(data, null, 2);
  const jsonOut = document.getElementById("json-output");
  if (jsonOut) jsonOut.textContent = ultimoJsonTexto;
}

const formConsulta = document.getElementById("form-consulta");
if (formConsulta) {
  formConsulta.addEventListener("submit", async (e) => {
    e.preventDefault();
    ocultarError();

    const patenteInput = document.getElementById("patente-input");
    const patente = patenteInput ? patenteInput.value.trim().toUpperCase() : "";
    if (!patente) {
      mostrarError("Ingresá una patente válida.");
      return;
    }

    const chkSim = document.getElementById("chk-simulacro");
    const chkCache = document.getElementById("chk-cache");
    const simulacro = chkSim ? chkSim.checked : false;
    const ignorarCache = chkCache ? chkCache.checked : false;

    abrirModalCarga(patente);
    try {
      const resp = await fetch("/api/consultar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patente,
          simulacro,
          ignorar_cache: ignorarCache,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || `Error HTTP ${resp.status}`);
      }
      renderizarResultados(data);
    } catch (err) {
      mostrarError(`No se pudo realizar la consulta: ${err.message}`);
    } finally {
      cerrarModalCarga();
    }
  });
}

const btnCopiarJson = document.getElementById("btn-copiar-json");
if (btnCopiarJson) {
  btnCopiarJson.addEventListener("click", async () => {
    if (!ultimoJsonTexto) return;
    await navigator.clipboard.writeText(ultimoJsonTexto);
    alert("JSON copiado al portapapeles.");
  });
}

const btnDescargarJson = document.getElementById("btn-descargar-json");
if (btnDescargarJson) {
  btnDescargarJson.addEventListener("click", () => {
    if (!ultimoJsonTexto) return;
    const blob = new Blob([ultimoJsonTexto], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `infracciones_${ultimaPatente || "consulta"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });
}

inicializarEnlacesContacto();
cargarServidores();