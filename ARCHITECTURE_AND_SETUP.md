# Arquitectura y Guía de Configuración - SIPECOM Agents

## 1. Visión General
El Sistema de Agentes Orquestados de SIPECOM es una herramienta de CLI basada en Python diseñada para automatizar la revisión de código, refactorización y aseguramiento de calidad (QA). Utiliza múltiples agentes especializados que colaboran para mitigar deuda técnica, validar reglas de negocio, y mantener un registro de auditoría completo y trazable.

## 2. Arquitectura del Sistema
El sistema sigue un patrón de Orquestador con agentes especializados:

*   **Orquestador Central (`orchestrator.py`)**: Dirige el flujo de trabajo (workflow). Se encarga de llamar a los agentes en el orden correcto y de interactuar con el usuario (Human-in-the-Loop) para aprobar o rechazar los cambios.
*   **Agente Base (`agents/base_agent.py`)**: Proporciona las herramientas fundamentales para todos los agentes, como leer y escribir archivos, y hacer backups de seguridad.
*   **Agente Lector de Historia de Usuario (`agents/story_reader_agent.py`)**: Lee las reglas de negocio y criterios de aceptación directamente desde un documento Markdown local o una URL de Google Docs para garantizar que los requerimientos de negocio estén alineados con la lógica del código.
*   **Agente Analista Desarrollador (`agents/analyst_agent.py`)**: Escanea el código en busca de errores PEP 8, *Code Smells*, vulnerabilidades (como contraseñas hardcodeadas o `eval` inseguro) y alta complejidad ciclomática. Además, fusiona esta información con las reglas de negocio para generar una propuesta técnica estructurada.
*   **Agente de Registro (`agents/registry_agent.py`)**: Registra todos los cambios y parches aplicados en un Google Sheets. Si hay problemas de conectividad o de credenciales, usa un archivo local `control_de_cambios.csv` como *fallback*.
*   **Agente QA / Documentación (`agents/qa_agent.py`)**: Simula la validación de pruebas basadas en Gherkin y mantiene un historial continuo en `DOCUMENTATION.md`.

## 3. Requisitos Técnicos
*   **Sistema Operativo**: Compatible con Windows, macOS y Linux.
*   **Lenguaje**: Python 3.8 o superior.
*   **Dependencias de entorno**: Puedes instalarlas usando `pip install -r requirements.txt`. Entre las principales están:
    *   `gspread`, `oauth2client` (para la API de Google Sheets).
    *   `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` (para la API de Google Docs).

## 4. Guía de Configuración e Integración con Google (Docs y Sheets)

Para que el sistema pueda leer documentos remotos en Google Docs y registrar tabulaciones en Google Sheets, necesitas colocar tu archivo `credentials.json` directamente en la raíz de la estructura del framework (ej. `C:\Users\tu-usuario\BotsAntigravity\credentials.json`). Este archivo maestro servirá para auditar **cualquier** proyecto o ruta que le envíes al agente.

### 4.1. Creación de las Credenciales JSON
1. Ve a la [Consola de Google Cloud](https://console.cloud.google.com/).
2. Crea un nuevo proyecto o selecciona uno existente.
3. Navega a **APIs & Services > Library** y asegúrate de habilitar las siguientes APIs:
    *   **Google Drive API**
    *   **Google Sheets API**
    *   **Google Docs API**
4. Navega a **APIs & Services > Credentials**.
5. Haz clic en **Create Credentials > Service Account**.
6. Completa los detalles y haz clic en crear. Esto generará un correo asociado a la cuenta de servicio (ej. `bot-agentes@tu-proyecto.iam.gserviceaccount.com`).
7. Haz clic en la cuenta recién creada, ve a la pestaña **Keys**, selecciona **Add Key > Create new key** y elige el formato **JSON**.
8. Descarga el archivo, renómbralo a `credentials.json` y guárdalo en la raíz del proyecto `BotsAntigravity`.

### 4.2. Permisos y Compartición de Archivos
*   **Para el Control de Cambios (Google Sheets)**: La hoja de cálculo donde el sistema va a escribir los registros ("Control de Cambios SIPECOM") debe estar **compartida** con el correo electrónico de tu cuenta de servicio otorgándole permisos de **Editor**.
*   **Para lectura de Historias de Usuario (Google Docs)**: Los documentos que incluyan las Historias de Usuario deben estar compartidos con el correo de la cuenta de servicio con permisos de **Lector** (mínimo) para que el Agente Lector pueda extraer el texto a través de la API.

### 4.3. Instrucciones de Uso
Edita el archivo `main.py`:
1. Ajusta la variable `ruta_proyecto` apuntando al directorio raíz del código que vas a auditar.
2. Ajusta `archivo_prueba` para indicar el archivo Python exacto a parchear.
3. Si lo deseas, proporciona una url válida en la variable `ruta_hu` apuntando a tu Google Docs.
4. Finalmente, ejecuta `python main.py` y sigue las opciones de la terminal para aprobar o denegar los cambios estructurados.
