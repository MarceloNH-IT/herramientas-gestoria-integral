# ⚖️ Herramientas de Gestoría Integral | Buscador Federal de Infracciones

[![Estado del Proyecto](https://img.shields.io/badge/Estado-En_Producción-success?style=for-the-badge)](https://gestorianunez-multas.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Cloud-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://gestorianunez-multas.streamlit.app)
[![Arquitectura](https://img.shields.io/badge/Motor-Async_HTTPX-7c3aed?style=for-the-badge)](#arquitectura-técnica)

Plataforma LegalTech desarrollada en Python para la **consulta automatizada, concurrente y unificada de infracciones de tránsito por dominio (patente)** en múltiples jurisdicciones provinciales y municipales de la República Argentina.

---

## 🌐 Acceso Directo a la Aplicación en Vivo

Hacé clic en el siguiente botón para abrir el buscador operativo directamente en el navegador (sin necesidad de instalar nada):

### 👉 [**ABRIR BUSCADOR DE INFRACCIONES ONLINE**](https://gestorianunez-multas.streamlit.app) 👈
*(URL directa: `https://gestorianunez-multas.streamlit.app`)*

---

## 🚀 Características Principales

* **Validación Normativa de Dominios:** Expresiones regulares (`Regex`) adaptadas al parque automotor y motovehicular argentino (`LLLNNN`, `LLNNNLL` Mercosur, `LNNNLLL` y `NNNLLL`).
* **Motor Asíncrono Concurrente (`asyncio` + `httpx`):** Ejecución simultánea de consultas HTTP directas sin depender de navegadores pesados (*headless browsers*), optimizando el consumo de memoria en la nube y entregando resultados en segundos.
* **Resolución Automatizada de Barreras Anti-Bot:** Integración nativa mediante API REST con **CapSolver / 2Captcha** para extracción de `data-sitekey` e inyección dinámica de tokens `g-recaptcha-response` (v2 Estándar e Invisible).
* **Consolidación Financiera y Operativa:** Cálculo automático de subtotales por jurisdicción, totalizador general flotante e identificación de actas con controlador.
* **Fallback Operativo Resiliente:** Aislamiento de fallos por portal (un juzgado caído no detiene el resto de la consulta) con acceso rápido de contingencia al portal oficial.

---

## 🗺️ Matriz de Jurisdicciones Relevadas (13 Portales)

| Jurisdicción | Nivel | Esquema de Seguridad | Método de Consulta | Estado |
| :--- | :--- | :--- | :--- | :--- |
| **Posadas (Misiones)** | Municipal | Sin CAPTCHA | `HTTP POST` Directo | 🟢 Activo |
| **Rosario (Santa Fe)** | Municipal | Sin CAPTCHA | `HTTP Form` / Parseo DOM | 🟢 Activo |
| **Lomas de Zamora** | Municipal | Sin CAPTCHA | `ASP.NET ViewState` HTTP | 🟢 Activo |
| **PBA (InfraccionesBA)** | Provincial | Google reCAPTCHA (Inv.) | `HTTP + CapSolver API` | 🟢 Activo |
| **CABA (GCBA)** | CABA | Google reCAPTCHA v2 | `HTTP + CapSolver API` | 🟢 Activo |
| **Ezeiza (Infratrack)** | Municipal | Google reCAPTCHA v2 | `HTTP + CapSolver API` | 🟢 Activo |
| **Entre Ríos** | Provincial | Google reCAPTCHA v2 | `Monitoreo Vial + CapSolver` | 🟢 Activo |
| **Misiones** | Provincial | Google reCAPTCHA v2 | `Monitoreo Vial + CapSolver` | 🟢 Activo |
| **Lanús** | Municipal | Google reCAPTCHA v2 | `HTTP + CapSolver API` | 🟢 Activo |
| **Córdoba Caminera** | Provincial | Sin CAPTCHA | Enlace Directo / Validación | 🟡 Enlace Oficial |
| **Santa Fe Provincial** | Provincial | CAPTCHA de Texto | Enlace Directo / Validación | 🟡 Enlace Oficial |
| **Vicente López** | Municipal | Cloudflare Turnstile | Enlace Directo / Validación | 🟡 Enlace Oficial |
| **Avellaneda** | Municipal | Cloudflare WAF | Enlace Directo / Validación | 🟡 Enlace Oficial |

---

## 🏗️ Arquitectura Técnica y Stack

* **Frontend & UI:** `Streamlit` con inyección de hojas de estilo CSS3 personalizadas (tipografía *Rubik*, tarjetas responsivas, barra de progreso en tiempo real con *backdrop-filter* y panel flotante de navegación rápida).
* **Networking & Scraping:** `httpx` (cliente HTTP/1.1 y HTTP/2 asíncrono) + `BeautifulSoup4` para extracción de formularios ocultos (`CSRF`, `__VIEWSTATE`, `__EVENTVALIDATION`) y normalización de tablas HTML.
* **Estructuras de Datos:** Uso estricto de `dataclasses` y `type hints` (`Infraccion`, `ResultadoJurisdiccion`, `JurisdiccionConfig`).
* **Seguridad de Credenciales:** Administración de claves de API mediante variables de entorno y bóveda encriptada (`Streamlit Secrets` en formato TOML).

---

## 📂 Estructura del Repositorio

```text
herramientas-gestoria-integral/
├── GestoriaF.py          # Core de la aplicación (UI, motor asíncrono, conectores HTTP y cliente Anti-Captcha)
├── requirements.txt      # Dependencias de producción para despliegue en Streamlit Cloud
├── BITACORA.md           # Registro técnico cronológico de avances, arquitectura y troubleshooting
└── README.md             # Documentación general y acceso directo a la aplicación
```

👨‍💻 Autor y Contacto Profesional
Horacio Marcelo Nuñez

Mandatario del Automotor | Gestoría Integral & Defensoría de Multas de Tránsito | Especialista IT & Automatización

🌐 Aplicación Web: gestorianunez-multas.streamlit.app

🐙 GitHub: @MarceloNH-IT

📸 Instagram: @marcelonunezgestiones

📖 Documentación de Ingeniería: Ver BITACORA.md


