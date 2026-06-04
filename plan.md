# Estrategia de Implementación

## Objetivo
Preparar y cargar el Agente de BotsAntigravity en esta máquina para su ejecución, incluyendo la capacidad de generar reportes en Google Sheets con formato gerencial estructurado, detectar modificaciones en las Historias de Usuario de Google Docs, y escanear recursivamente todo el proyecto si no se especifica un archivo de prueba.

## Pasos a seguir
1. Confirmar el Tech Stack definitivo (Python con gspread).
2. Configurar el entorno virtual e instalar dependencias.
3. Centralizar rutas en `config.json`.
4. Diseñar e implementar el nuevo Agente de Reportes (`agents/report_agent.py`) detallando las 3 HUs.
5. Mejorar el formateo en `agents/registry_agent.py` para parsear Markdown a celdas individuales en Google Sheets de forma tabular, estética y por archivo dinámico.
6. Implementar un mecanismo de caché en `orchestrator.py` para detectar si el documento de Google Docs ha sido modificado.
7. Modificar `main.py` para soportar el análisis recursivo de múltiples archivos Python en `ruta_proyecto` cuando `archivo_prueba` esté vacío.
8. Probar y auditar visualmente los resultados (/audit).
