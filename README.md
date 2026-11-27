# ⚖️ Herramientas Gestoría Integral — Buscador de Infracciones

Aplicación web modular en Python + Streamlit para consultar infracciones de tránsito por patente en múltiples jurisdicciones de Argentina, con arquitectura desacoplada, consultas asíncronas en paralelo y exportación estructurada a JSON.

---

## 🏗️ Arquitectura del Proyecto

```text
herramientas-gestoria-integral/
├── core/
│   ├── modelos.py          # Dataclasses de dominio, estados y excepciones tipadas
│   ├── captcha.py          # Cliente asíncrono anti-captcha (reCAPTCHA v2 / Turnstile) + modo simulacro
│   └── parser.py           # Normalización y parseo de respuestas HTML/JSON
├── conectores/
│   ├── base.py             # Cliente HTTP asíncrono (httpx), paginación y utilidades compartidas
│   ├── caba.py             # Conector CABA (reCAPTCHA v2)
│   ├── pba.py              # Conector Provincia de Buenos Aires (reCAPTCHA v2)
│   ├── entre_rios.py       # Conector Entre Ríos (Cloudflare Turnstile)
│   ├── avellaneda.py       # Conector Avellaneda (API JSON)
│   ├── lomas.py            # Conector Lomas de Zamora (flujo ASP.NET en 3 pasos + lectura de PDF)
│   └── vicente_lopez.py    # Conector Vicente López (Laravel/Vue + Cloudflare Turnstile)
├── GestoriaF.py            # Interfaz web en Streamlit, caché en memoria y monitoreo de portales
├── requirements.txt        # Dependencias del proyecto
└── .flake8                 # Configuración de linting