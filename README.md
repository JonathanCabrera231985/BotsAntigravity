# Sistema de Agentes Orquestados para Gestión de Calidad y Operaciones - SIPECOM

Este proyecto implementa un sistema modular de agentes autónomos desarrollado en Python. Los agentes cooperan entre sí bajo la supervisión de un **Orquestador Central** para analizar el código fuente, proponer e implementar refactorizaciones y parches de seguridad, registrar los cambios aplicados en hojas de control (Google Sheets o CSV local) y verificar la calidad mediante pruebas estructuradas (Gherkin/QA).

## Arquitectura del Sistema

El flujo de trabajo involucra cinco componentes principales:

1. **Clase Base `Agente` (`agents/base_agent.py`)**: Abstrae las operaciones comunes de lectura/escritura de archivos con UTF-8, escaneo recursivo de directorios y copias de seguridad de seguridad (`.bak`).
2. **Agente Lector de Historia de Usuario (`agents/story_reader_agent.py`)**: Lee las reglas de negocio (criterios de aceptación) desde un archivo local Markdown o directamente interactuando con la API de Google Docs.
3. **Agente Analista/Desarrollador (`agents/analyst_agent.py`)**:
   - Escanea archivos Python en busca de deuda técnica y vulnerabilidades críticas (excepciones silenciadas, secretos expuestos, uso inseguro de `eval`/`exec`, comentarios `TODO` pendientes).
   - Genera propuestas formales de **Historias de Usuario (HU)** y deriva casos de prueba bajo sintaxis **Gherkin**, integrando opcionalmente los requisitos capturados en el paso anterior.
   - Aplica parches seguros mediante manipulación estructurada de tokens.
4. **Agente de Registro (`agents/registry_agent.py`)**:
   - Tabula los metadatos de los cambios: fecha/hora, agente responsable, HU, archivo modificado, acción de parcheo, justificación, estado y casos de prueba aplicados.
   - Conexión nativa con **Google Sheets** usando la biblioteca `gspread`.
   - **Manejo de Fallback**: Si no existen credenciales de Google o falla la red, el agente escribe automáticamente sobre un archivo CSV local (`control_de_cambios.csv`) para no interrumpir el flujo.
4. **Agente de QA/Documentación (`agents/qa_agent.py`)**:
   - Simula y verifica los casos de prueba QA derivados de la HU.
   - Crea y actualiza dinámicamente un historial de calidad en `DOCUMENTATION.md`.
5. **Orquestador Central (`orchestrator.py`)**:
   - Gestiona el ciclo operativo paso a paso.
   - Introduce una compuerta **Human-in-the-loop**: presenta la propuesta con análisis de riesgo al usuario en consola y aguarda su aprobación para aplicar o abortar el cambio.
   - Emplea un módulo `logging` unificado que guarda cada fase en `sipecom_agents.log` y consola.

## Documentación Detallada y Guía de Configuración

Para obtener instrucciones exhaustivas sobre los requisitos técnicos, cómo habilitar los accesos y crear el archivo `credentials.json` para conectarse con Google Docs y Google Sheets, consulta nuestra guía completa:

👉 **[Ver Arquitectura y Guía de Configuración (ARCHITECTURE_AND_SETUP.md)](ARCHITECTURE_AND_SETUP.md)**

---

## Requisitos de Instalación

Instala las dependencias necesarias ejecutando:

```bash
pip install -r requirements.txt
```

*(Nota: Asegúrate de tener configurado tu `credentials.json` tal y como se detalla en la guía de configuración para habilitar Google Sheets y Docs).*

---

## Cómo Ejecutar la Demostración

Hemos provisto un archivo de prueba con deuda técnica preconfigurada (`test_target.py`) y un ejecutable principal (`main.py`).

1. Para arrancar el flujo de demostración interactivo, ejecuta:
   ```bash
   python main.py
   ```

2. El orquestador analizará `test_target.py`, identificará las vulnerabilidades y te presentará una Historia de Usuario (HU).
3. Escribe `s` (Sí) para aprobar los cambios o `n` (No) para rechazarlos.
4. Si apruebas, verás que:
   - Se crea el backup `test_target.py.bak`.
   - Se aplican parches a `test_target.py` para corregir las excepciones vacías e inyectar de forma segura imports de logging.
   - Se registra el cambio en `control_de_cambios.csv`.
   - Se actualiza `DOCUMENTATION.md` con los resultados de las pruebas.
