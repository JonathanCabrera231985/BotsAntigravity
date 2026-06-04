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
                    
                    # --- CACHE DE MODIFICACIONES DE GOOGLE DOCS ---
                    import hashlib
                    import json
                    
                    cache_path = os.path.join(self.ruta_proyecto, ".hu_cache.json")
                    hu_actual_txt = resumen_hu.get('ReporteMarkdown', '')
                    hu_hash_actual = hashlib.md5(hu_actual_txt.encode('utf-8')).hexdigest()
                    
                    documento_modificado = True
                    if os.path.exists(cache_path):
                        try:
                            with open(cache_path, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            if cache_data.get(ruta_hu) == hu_hash_actual:
                                documento_modificado = False
                        except Exception as e_cache:
                            self.logger.warning(f"No se pudo leer el caché de HUs: {e_cache}")
                            
                    if not documento_modificado:
                        self.logger.info("El documento de Google Docs no ha recibido modificaciones desde la última ejecución.")
                        print("\n" + "="*80)
                        print(" AVISO: El documento de Google Docs no ha recibido ninguna modificación.")
                        print("="*80)
                        while True:
                            aplicar = input(">>> ¿Desea aplicar la solicitud de esas historias de usuario igualmente? (s/n): ").strip().lower()
                            if aplicar in ['s', 'si', 'yes', 'y']:
                                self.logger.info("El usuario decidió aplicar la Historia de Usuario sin modificar.")
                                break
                            elif aplicar in ['n', 'no']:
                                self.logger.info("El usuario rechazó aplicar la Historia de Usuario. Se usará el análisis puro de código.")
                                resumen_hu = None  # Descartar las reglas de negocio
                                break
                            else:
                                print("Entrada no reconocida. Ingrese 's' para Sí o 'n' para No.")
                    
                    # Actualizar caché si todavía se decide usar
                    if resumen_hu:
                        try:
                            cache_data = {}
                            if os.path.exists(cache_path):
                                with open(cache_path, 'r', encoding='utf-8') as f:
                                    cache_data = json.load(f)
                            cache_data[ruta_hu] = hu_hash_actual
                            with open(cache_path, 'w', encoding='utf-8') as f:
                                json.dump(cache_data, f, indent=2)
                        except Exception as e_cache:
                            self.logger.warning(f"No se pudo escribir en el caché de HUs: {e_cache}")
                else:
                    self.logger.warning("No se pudo extraer la Historia de Usuario o el documento está vacío.")

            # ---------------------------------------------------------
            # PASO 1: Analista genera propuesta (HU) analizando el archivo
            # ---------------------------------------------------------
            self.logger.info("[PASO 1] Escaneando archivo y generando Historia de Usuario...")
            hu = self.analista.analizar_y_proponer(ruta_archivo)
            
            # Integrar requerimientos de negocio si se encontraron en el PASO 0
            historias_aplicables = []
            if resumen_hu and 'HistoriasBacklog' in resumen_hu:
                filename = os.path.basename(ruta_archivo).lower()
                filename_no_ext = os.path.splitext(filename)[0]
                for story in resumen_hu['HistoriasBacklog']:
                    match = False
                    for ref_file in story.get("files_mentioned", []):
                        ref_file = ref_file.lower()
                        ref_file_no_ext = os.path.splitext(ref_file)[0]
                        if ref_file == filename:
                            match = True
                            break
                        if ref_file_no_ext in filename_no_ext or filename_no_ext in ref_file_no_ext:
                            match = True
                            break
                    if not match:
                        title_lower = story.get("title", "").lower()
                        desc_lower = story.get("description", "").lower()
                        if "clibapiclient" in filename_no_ext and "clibapiclient" in (title_lower + desc_lower):
                            match = True
                        elif "munchery_spider" in filename_no_ext and "munchery_spider" in (title_lower + desc_lower):
                            match = True
                    if match:
                        historias_aplicables.append(story)
            
            if historias_aplicables:
                hu['Título'] = f"{resumen_hu['Funcionalidad a Modificar']} + Refactor"
                hu['Contexto'] = f"Se leyeron reglas de negocio desde el documento externo.\n" + hu['Contexto']
                
                stories_markdown = []
                for s in historias_aplicables:
                    stories_markdown.append(f"#### [{s['id']}] {s['title']}")
                    stories_markdown.append(f"**Descripción**: {s['description']}")
                    stories_markdown.append("**Criterios de Aceptación**:")
                    for c in s['criteria']:
                        stories_markdown.append(f"  - {c}")
                    stories_markdown.append("")
                    
                hu['Descripción'] = "### [REQ] Requerimientos de Negocio\n" + "\n".join(stories_markdown) + "\n\n### [ANALISIS] Análisis Estático del Código\n" + hu['Descripción']
                
                criterios = "Escenario: Cumplimiento de Reglas de Negocio\n"
                for s in historias_aplicables:
                    for c in s['criteria']:
                        criterios += f"  - {c}\n"
                hu['Criterios de Aceptación'] = criterios + "\n" + hu['Criterios de Aceptación']
                hu['Casos de Prueba'] = self.analista.derivar_casos_prueba(hu['Criterios de Aceptación'])
                hu['HistoriasAplicables'] = historias_aplicables
            else:
                hu['HistoriasAplicables'] = []

            
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
                
            # Subpaso 3.5: Generación del Reporte Técnico (SonarQube)
            self.logger.info("Generando Reporte Técnico gerencial consolidado...")
            from agents.report_agent import AgenteReporteTecnico
            agente_reporte = AgenteReporteTecnico(self.ruta_proyecto)
            reporte_markdown = agente_reporte.generar_reporte(ruta_archivo, resumen_hu, hu)
            
            # Guardarlo en una nueva pestaña dinámica según el archivo analizado (solo si tiene historias aplicables)
            if hu.get('HistoriasAplicables'):
                nombre_archivo_sin_ext = os.path.splitext(os.path.basename(ruta_archivo))[0]
                nombre_pestana = f"Reporte Técnico-{nombre_archivo_sin_ext}"
                self.registrador.escribir_reporte_gerencial(reporte_markdown, nombre_pestana=nombre_pestana)
            else:
                self.logger.info(f"Omitiendo creación de pestaña Google Sheets para {os.path.basename(ruta_archivo)} por falta de Historias de Usuario aplicables.")

            self.logger.info(f"=== CICLO COMPLETADO CON ÉXITO PARA: {os.path.basename(ruta_archivo)} ===")
            return True
            
        except Exception as e:
            self.logger.error(f"Error crítico no controlado durante el ciclo operativo: {str(e)}", exc_info=True)
            return False

    def _limpiar_texto(self, texto: str) -> str:
        if not texto:
            return ""
        # Reemplazar BOM y caracteres problemáticos comunes
        texto_limpio = texto.replace('\ufeff', '').replace('\u200b', '')
        # Reemplazar emojis comunes para evitar fallos en consolas Windows legacy
        texto_limpio = (texto_limpio
                        .replace("🚨", "[PEP 8]")
                        .replace("🦨", "[CODE SMELLS]")
                        .replace("📈", "[COMPLEJIDAD]")
                        .replace("🛠️", "[REFACTOR]")
                        .replace("📋", "[REQ]")
                        .replace("🔧", "[ANALISIS]")
                        .replace("", ""))
        encoding = sys.stdout.encoding or 'utf-8'
        try:
            texto_bytes = texto_limpio.encode(encoding, errors='replace')
            return texto_bytes.decode(encoding)
        except Exception:
            try:
                return texto_limpio.encode('ascii', errors='replace').decode('ascii')
            except Exception:
                return "[Error de codificación de texto]"

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
        
        titulo = self._limpiar_texto(hu.get('Título', ''))
        contexto = self._limpiar_texto(hu.get('Contexto', ''))
        desc = self._limpiar_texto(hu.get('Descripción', ''))
        criterios = self._limpiar_texto(hu.get('Criterios de Aceptación', ''))
        restricciones = self._limpiar_texto(hu.get('Restricciones Técnicas', ''))
        impacto = self._limpiar_texto(hu.get('Impacto Estimado', ''))
        criticidad = self._limpiar_texto(hu.get('Nivel de Criticidad', ''))

        print(f"\n* TÍTULO: {titulo}")
        print(f"* CONTEXTO: {contexto}")
        print(separador)
        
        print("* ANÁLISIS DE RIESGO:")
        print(f"  - Nivel de Criticidad : \033[91m{criticidad}\033[0m" if criticidad in ['Alta', 'Crítica'] 
              else f"  - Nivel de Criticidad : \033[92m{criticidad}\033[0m")
        print(f"  - Impacto Estimado   : {impacto}")
        print(separador)
        
        print(f"* DESCRIPCIÓN:\n{desc}")
        print(separador)
        
        print(f"* CRITERIOS DE ACEPTACIÓN (Gherkin):\n{criterios}")
        print(separador)
        
        print(f"* RESTRICCIONES TÉCNICAS: {restricciones}")
        print(separador)
        
        print("* CASOS DE PRUEBA DERIVADOS:")
        casos = hu.get("Casos de Prueba", [])
        for i, cp in enumerate(casos, 1):
            escenario = self._limpiar_texto(cp.get('Escenario', ''))
            dado = self._limpiar_texto(cp.get('Dado', ''))
            cuando = self._limpiar_texto(cp.get('Cuando', ''))
            entonces = self._limpiar_texto(cp.get('Entonces', ''))
            print(f"  CP {i}: {escenario}")
            print(f"    Dado: {dado}")
            print(f"    Cuando: {cuando}")
            print(f"    Entonces: {entonces}")
            
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
