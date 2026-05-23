import os
import logging
import sys
from typing import Dict, Any
from agents.analyst_agent import AgenteAnalistaDesarrollador
from agents.registry_agent import AgenteRegistroGoogleSheets
from agents.qa_agent import AgenteQADocumentacion
from agents.story_reader_agent import AgenteLectorHistoriaUsuario

# Configuración centralizada de logging para el orquestador y los agentes
def configurar_logging(ruta_log: str = "sipecom_agents.log"):
    """
    Configura el sistema de logging para registrar en archivo y consola.
    """
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] (%(name)s) %(message)s')
    
    # Manejador para archivo
    file_handler = logging.FileHandler(ruta_log, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    # Manejador para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Logger raíz de la aplicación
    root_logger = logging.getLogger("SipecomAgents")
    root_logger.setLevel(logging.INFO)
    
    # Limpiar manejadores previos si los hubiera
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

class Orquestador:
    """
    El Cerebro del sistema: Coordina el flujo de análisis, aprobación interactiva,
    parcheo, registro de cambios y verificación de calidad.
    """

    def __init__(self, ruta_proyecto: str):
        """
        Inicializa el orquestador y todos los agentes especialistas.
        
        :param ruta_proyecto: Ruta raíz del proyecto.
        """
        configurar_logging(os.path.join(ruta_proyecto, "sipecom_agents.log"))
        self.logger = logging.getLogger("SipecomAgents.Orchestrator")
        self.ruta_proyecto = os.path.abspath(ruta_proyecto)
        
        self.logger.info("Inicializando agentes del sistema...")
        self.analista = AgenteAnalistaDesarrollador(self.ruta_proyecto)
        self.registrador = AgenteRegistroGoogleSheets(self.ruta_proyecto)
        self.qa = AgenteQADocumentacion(self.ruta_proyecto)
        self.lector_hu = AgenteLectorHistoriaUsuario(self.ruta_proyecto)
        self.logger.info("Todos los agentes han sido cargados con éxito.")

    def ejecutar_ciclo_completo(self, ruta_archivo: str, ruta_hu: str = None) -> bool:
        """
        Ejecuta el ciclo de vida completo para un archivo dado.
        
        :param ruta_archivo: Ruta al archivo de código fuente a procesar.
        :param ruta_hu: Ruta local o URL de Google Docs con la Historia de Usuario.
        :return: True si el ciclo se completó con éxito (aprobado o no requerido), 
                 False si fue abortado por el usuario o falló.
        """
        self.logger.info(f"=== INICIANDO CICLO DE CALIDAD EN: {os.path.basename(ruta_archivo)} ===")
        
        if not os.path.exists(ruta_archivo):
            self.logger.error(f"Archivo objetivo no encontrado en la ruta: {ruta_archivo}")
            return False
            
        try:
            # ---------------------------------------------------------
            # PASO 0: Lectura de Historia de Usuario (Opcional)
            # ---------------------------------------------------------
            resumen_hu = None
            if ruta_hu:
                self.logger.info(f"[PASO 0] Intentando leer la Historia de Usuario desde: {ruta_hu}")
                resumen_hu = self.lector_hu.leer_historia_usuario(ruta_hu)
                if resumen_hu:
                    self.logger.info("Resumen de Historia de Usuario extraído correctamente.")
                else:
                    self.logger.warning("No se pudo extraer la Historia de Usuario o el documento está vacío.")

            # ---------------------------------------------------------
            # PASO 1: Analista genera propuesta (HU) analizando el archivo
            # ---------------------------------------------------------
            self.logger.info("[PASO 1] Escaneando archivo y generando Historia de Usuario...")
            hu = self.analista.analizar_y_proponer(ruta_archivo)
            
            # Integrar requerimientos de negocio si se encontraron en el PASO 0
            if resumen_hu:
                hu['Título'] = f"{resumen_hu['Funcionalidad a Modificar']} + Refactor"
                hu['Contexto'] = f"Se leyeron reglas de negocio desde el documento externo.\n" + hu['Contexto']
                hu['Descripción'] = "### 📋 Requerimientos de Negocio\n" + resumen_hu['ReporteMarkdown'] + "\n\n### 🔧 Análisis Estático del Código\n" + hu['Descripción']
                # Prepend the acceptance criteria from the business
                criterios = "Escenario: Cumplimiento de Reglas de Negocio\n"
                for regla in resumen_hu['Reglas de Negocio Nuevas/Modificadas']:
                    criterios += f"  {regla}\n"
                hu['Criterios de Aceptación'] = criterios + "\n" + hu['Criterios de Aceptación']
                # Actualizar los casos de prueba para incluir los de negocio
                hu['Casos de Prueba'] = self.analista.derivar_casos_prueba(hu['Criterios de Aceptación'])

            
            # ---------------------------------------------------------
            # PASO 2: Human-in-the-loop (Aprobación del usuario)
            # ---------------------------------------------------------
            self.logger.info("[PASO 2] Solicitando aprobación del usuario para la propuesta...")
            aprobado = self._solicitar_aprobacion_humana(hu)
            
            if not aprobado:
                self.logger.warning("Flujo abortado por el usuario. No se realizaron modificaciones.")
                # Registrar el intento abortado en el registro
                self.registrador.tabular_cambios(
                    historia_usuario=hu,
                    detalle_cambio="Parche rechazado por aprobación humana.",
                    casos_prueba=hu.get("Casos de Prueba", []),
                    resultado_estado="Rechazado"
                )
                return False
                
            # ---------------------------------------------------------
            # PASO 3: Ejecución si es aprobado
            # ---------------------------------------------------------
            self.logger.info("[PASO 3] Aprobación concedida. Procediendo con el flujo automatizado...")
            
            # Subpaso 3.1: Crear copia de seguridad
            self.logger.info("Creando copia de seguridad del archivo original...")
            self.analista.crear_backup(ruta_archivo)
            
            # Subpaso 3.2: Aplicar parches de código
            self.logger.info("Aplicando parches de código...")
            detalle_cambio = self.analista.revisar_y_parchear(ruta_archivo, hu)
            
            # Subpaso 3.3: Registro (Google Sheets / CSV Fallback)
            self.logger.info("Tabulando cambios en la hoja de control...")
            registro_ok = self.registrador.tabular_cambios(
                historia_usuario=hu,
                detalle_cambio=detalle_cambio,
                casos_prueba=hu.get("Casos de Prueba", []),
                resultado_estado="Aplicado con Éxito"
            )
            if not registro_ok:
                self.logger.warning("El registro de cambios se completó con advertencias.")

            # Subpaso 3.4: QA y Documentación
            self.logger.info("Ejecutando verificación de QA y actualizando documentación técnica...")
            qa_ok = self.qa.verificar_y_documentar(ruta_archivo, hu.get("Casos de Prueba", []))
            if not qa_ok:
                self.logger.error("Error durante la verificación de QA o la actualización de documentación.")
                
            self.logger.info(f"=== CICLO COMPLETADO CON ÉXITO PARA: {os.path.basename(ruta_archivo)} ===")
            return True
            
        except Exception as e:
            self.logger.error(f"Error crítico no controlado durante el ciclo operativo: {str(e)}", exc_info=True)
            return False

    def _solicitar_aprobacion_humana(self, hu: Dict[str, Any]) -> bool:
        """
        Formatea y presenta la propuesta de HU en la consola, y detiene la
        ejecución solicitando una entrada booleana al usuario.
        
        :param hu: Diccionario de la Historia de Usuario.
        :return: True si el usuario aprueba, False si rechaza.
        """
        # Formateo visual premium para la consola
        ancho_consola = 80
        borde = "=" * ancho_consola
        separador = "-" * ancho_consola
        
        print("\n" + borde)
        print(f"|{'PROPUESTA DE HISTORIA DE USUARIO (HU) GENERADA POR AGENTE'.center(ancho_consola-2)}|")
        print(borde)
        
        print(f"\n* TÍTULO: {hu.get('Título')}")
        print(f"* CONTEXTO: {hu.get('Contexto')}")
        print(separador)
        
        print("* ANÁLISIS DE RIESGO:")
        print(f"  - Nivel de Criticidad : \033[91m{hu.get('Nivel de Criticidad')}\033[0m" if hu.get('Nivel de Criticidad') in ['Alta', 'Crítica'] 
              else f"  - Nivel de Criticidad : \033[92m{hu.get('Nivel de Criticidad')}\033[0m")
        print(f"  - Impacto Estimado   : {hu.get('Impacto Estimado')}")
        print(separador)
        
        desc = hu.get('Descripción', '')
        try:
            # Intentar codificar en la codificación de la consola actual
            desc.encode(sys.stdout.encoding or 'utf-8')
        except (UnicodeEncodeError, LookupError):
            # Fallback en caso de que no admita emojis
            desc = desc.replace("🚨", "[PEP 8]").replace("🦨", "[CODE SMELLS]").replace("📈", "[COMPLEJIDAD]").replace("🛠️", "[REFACTOR]")
            
        print(f"* DESCRIPCIÓN:\n{desc}")
        print(separador)
        
        print(f"* CRITERIOS DE ACEPTACIÓN (Gherkin):\n{hu.get('Criterios de Aceptación')}")
        print(separador)
        
        print(f"* RESTRICCIONES TÉCNICAS: {hu.get('Restricciones Técnicas')}")
        print(separador)
        
        print("* CASOS DE PRUEBA DERIVADOS:")
        casos = hu.get("Casos de Prueba", [])
        for i, cp in enumerate(casos, 1):
            print(f"  CP {i}: {cp.get('Escenario')}")
            print(f"    Dado: {cp.get('Dado')}")
            print(f"    Cuando: {cp.get('Cuando')}")
            print(f"    Entonces: {cp.get('Entonces')}")
            
        print(borde)
        
        # Bucle de interacción con el usuario (Human-in-the-loop)
        while True:
            seleccion = input("\n>>> ¿Desea aprobar y aplicar esta propuesta de cambio? (s/n): ").strip().lower()
            if seleccion in ['s', 'si', 'yes', 'y', '1', 'true']:
                return True
            elif seleccion in ['n', 'no', '0', 'false']:
                return False
            else:
                print("Entrada no reconocida. Ingrese 's' para Sí o 'n' para No.")
