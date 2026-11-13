# 📂 Bitácora de Desarrollo - Herramientas de Gestoría Integral

Registro cronológico de avances técnicos, resolución de incidencias, diseño arquitectónico e integración de conectores para la automatización de trámites y fiscalización vehicular.

🔗 **Entorno de Producción Activo:** [https://gestorianunez-multas.streamlit.app](https://gestorianunez-multas.streamlit.app)

---

## 📅 Jueves 12 de Noviembre de 2026
### 🌐 Pase a Producción en la Nube, Motor HTTP Puro e Integración Anti-CAPTCHA

#### 1. Decisión Arquitectónica: Eliminación de Navegadores Headless (Zero-Browser Architecture)
* **Análisis de Diseño:** Se evaluó inicialmente la automatización mediante navegadores externos (*Playwright / Chromium*), pero se descartó para evitar la apertura de ventanas emergentes en entornos locales y eliminar la sobrecarga de memoria RAM en servidores Linux de nube.
* **Implementación Definitiva:** Migración al 100% hacia peticiones HTTP asíncronas puras utilizando `httpx.AsyncClient` y parseo DOM en memoria con `BeautifulSoup4`. Todo el flujo de consulta se ejecuta dentro de `Streamlit`.

#### 2. Integración de Servicio Pago de Resolución de CAPTCHAs (`CaptchaSolver`)
* **Desarrollo del Cliente Universal:** Construcción de la clase asíncrona `CaptchaSolver` dentro de `GestoriaF.py` con soporte dual para **CapSolver** (`ReCaptchaV2TaskProxyLess`) y **2Captcha**.
* **Extracción e Inyección sin Navegador:**
  * Implementación de extractor por expresiones regulares (`extraer_sitekey_html`) que inspecciona el código fuente HTML/JS de los portales gubernamentales para capturar el parámetro `data-sitekey`.
  * Captura automática de inputs ocultos de sesión (`__VIEWSTATE`, `__EVENTVALIDATION`, tokens CSRF) y envío directo del token `g-recaptcha-response` mediante peticiones `POST`.
* **Conectores Operativos Integrados (9 Jurisdicciones):** Posadas, Rosario, Lomas de Zamora, PBA (InfraccionesBA), CABA, Ezeiza (Infratrack), Entre Ríos, Misiones y Lanús.

#### 3. Troubleshooting de Despliegue y CI/CD en Streamlit Community Cloud
* **Incidencia en Deploy Inicial:** Fallo de arranque en el contenedor de la nube (`ModuleNotFoundError: import httpx` en línea 18 de `GestoriaF.py`).
* **Diagnóstico y Resolución:** Confección y versionado del archivo `requirements.txt` especificando las dependencias exactas (`streamlit`, `httpx`, `beautifulsoup4`).
* **Seguridad (DevSecOps):** Configuración de la clave privada `CAPTCHA_API_KEY` en el almacén encriptado **Streamlit Secrets (TOML)**.
* **Publicación Exitosa:** Despliegue continuo vinculado a la rama `main` bajo el dominio `https://gestorianunez-multas.streamlit.app`.

---

## 📅 Sábado 17 de Octubre de 2026
### 🚀 Inicialización y Estructura Base del Proyecto

* **Creación del Repositorio:** Configuración inicial del repositorio `herramientas-gestoria-integral` en GitHub (`MarceloNH-IT`).
* **Desarrollo del Core (`GestoriaF.py`):**
  * Estructuración de la aplicación web utilizando Python y Streamlit con un enfoque de diseño LegalTech.
  * Implementación de tipado estático y `dataclasses` (`Infraccion`, `ResultadoJurisdiccion` y `JurisdiccionConfig`).
  * Programación asincrónica (`asyncio`) para el motor de consultas concurrentes sobre múltiples endpoints.

### 🛡️ Relevamiento y Mapeo de 13 Jurisdicciones
1. **Sin CAPTCHA (4 portales):** Posadas (Misiones), Rosario (Santa Fe), Lomas de Zamora y Córdoba Caminera.
2. **Con CAPTCHA / WAF (9 portales):** PBA, CABA, Ezeiza, Entre Ríos, Misiones Provincial, Lanús, Santa Fe Provincial, Vicente López y Avellaneda.

### 🛠️ Corrección de Incidencias Técnicas (Troubleshooting de Entorno)
* **Incidencia:** Error de compilación de sintaxis (`SyntaxError: invalid syntax`) en terminal de PowerShell.
* **Diagnóstico y Resolución:** Estandarización de codificación de caracteres a `UTF-8`.
* **Control de Versiones (Git):** Resolución de conflictos de sincronización remota (`non-fast-forward` / `fetch first`) y unificación de historial con `main`.
