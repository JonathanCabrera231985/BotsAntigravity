import os
import re
import logging
from typing import Dict, Any, Optional
from .base_agent import Agente

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    GOOGLE_DOCS_AVAILABLE = True
except ImportError:
    GOOGLE_DOCS_AVAILABLE = False

logger = logging.getLogger("SipecomAgents.StoryReaderAgent")

class AgenteLectorHistoriaUsuario(Agente):
    """
    Agente responsable de leer Historias de Usuario desde archivos Markdown
    locales o documentos de Google Docs, extrayendo los Criterios de Aceptación
    y generando un reporte técnico para el Agente Analista.
    """

    def __init__(self, ruta_proyecto: str):
        super().__init__(ruta_proyecto)
        # Buscar credentials.json siempre en la raíz del framework BotsAntigravity
        directorio_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ruta_credenciales = os.path.join(directorio_base, "credentials.json")

    def leer_historia_usuario(self, ruta_doc: str) -> Optional[Dict[str, Any]]:
        """
        Lee el documento y devuelve un diccionario con el formato requerido.
        """
        if not ruta_doc:
            return None
            
        contenido = ""
        
        # Detectar si es una URL de Google Docs
        if "docs.google.com/document/d/" in ruta_doc:
            logger.info("Detectado documento de Google Docs.")
            contenido = self._leer_google_docs(ruta_doc)
        elif os.path.exists(ruta_doc):
            logger.info(f"Leyendo documento local: {ruta_doc}")
            try:
                with open(ruta_doc, 'r', encoding='utf-8') as f:
                    contenido = f.read()
            except Exception as e:
                logger.error(f"Error al leer archivo local {ruta_doc}: {e}")
                return None
        else:
            logger.warning(f"La ruta o URL proporcionada no es válida o no existe: {ruta_doc}")
            return None
            
        if not contenido:
            logger.warning("El documento está vacío o no se pudo extraer el contenido.")
            return None
            
        return self.generar_resumen_tecnico(contenido)

    def _leer_google_docs(self, url: str) -> str:
        if not GOOGLE_DOCS_AVAILABLE:
            logger.error("Dependencias de Google Docs no disponibles. Asegúrese de haber instalado google-api-python-client.")
            return ""
            
        if not os.path.exists(self.ruta_credenciales):
            logger.error(f"Credenciales no encontradas en {self.ruta_credenciales}")
            return ""
            
        # Extraer ID del documento
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
        if not match:
            logger.error("URL de Google Docs inválida.")
            return ""
            
        doc_id = match.group(1)
        
        try:
            scopes = ['https://www.googleapis.com/auth/documents.readonly']
            creds = Credentials.from_service_account_file(self.ruta_credenciales, scopes=scopes)
            service = build('docs', 'v1', credentials=creds)
            document = service.documents().get(documentId=doc_id).execute()
            
            # Extraer el texto
            text = ""
            for item in document.get('body').get('content', []):
                if 'paragraph' in item:
                    elements = item.get('paragraph').get('elements', [])
                    for element in elements:
                        if 'textRun' in element:
                            text += element.get('textRun').get('content', '')
            return text
        except Exception as e:
            logger.error(f"Error al leer Google Docs (ID: {doc_id}): {e}")
            return ""

    def generar_resumen_tecnico(self, contenido: str) -> Dict[str, Any]:
        """
        Procesa el contenido para extraer y estructurar el reporte técnico.
        """
        logger.info("Generando resumen técnico de la historia de usuario...")
        
        # Extraer funcionalidad a modificar (heurística simple: primera línea o título)
        funcionalidad = "Desconocida"
        lineas = [l.strip() for l in contenido.split('\n') if l.strip()]
        if lineas:
            funcionalidad = lineas[0].replace("#", "").strip()
            
        # Extraer criterios de aceptación o reglas de negocio
        reglas_negocio = []
        en_criterios = False
        for linea in lineas:
            linea_lower = linea.lower()
            if "criterio" in linea_lower or "regla" in linea_lower or "aceptación" in linea_lower:
                en_criterios = True
                continue
            if en_criterios:
                if linea.startswith("#") or linea.lower().startswith("impacto"):
                    en_criterios = False
                elif linea.startswith("-") or linea.startswith("*"):
                    reglas_negocio.append(linea)
                elif len(linea) > 5:
                    reglas_negocio.append("- " + linea)
                    
        if not reglas_negocio:
            reglas_negocio = ["- No se especificaron criterios de aceptación explícitos."]
            
        # Extraer impacto esperado
        impacto = "Alineación de lógica con los nuevos requerimientos de la historia de usuario."
        for i, linea in enumerate(lineas):
            if "impacto" in linea.lower():
                # Tomar las siguientes líneas hasta el fin o nuevo título
                impacto_lines = []
                for j in range(i+1, len(lineas)):
                    if lineas[j].startswith("#"):
                        break
                    impacto_lines.append(lineas[j])
                if impacto_lines:
                    impacto = " ".join(impacto_lines)
                break

        resumen = {
            "Funcionalidad a Modificar": funcionalidad,
            "Reglas de Negocio Nuevas/Modificadas": reglas_negocio,
            "Impacto Esperado": impacto,
            "ReporteMarkdown": self._formatear_markdown(funcionalidad, reglas_negocio, impacto),
            "HistoriasBacklog": self.parse_backlog(contenido)
        }
        return resumen

    def parse_backlog(self, text: str) -> list:
        """
        Parsea el backlog completo del documento de SonarQube en Historias de Usuario estructuradas.
        """
        parts = text.split("Historia de Usuario:")
        stories = []
        
        for part in parts[1:]:
            lines = part.strip().split('\n')
            if not lines:
                continue
            title = lines[0].strip()
            
            # Extraer códigos de regla de SonarQube (ej. python:S4830)
            sonar_rules = re.findall(r'(python:S\d+)', title)
            
            description = ""
            criteria = []
            effort = "0.0h"
            cases = []
            
            current_section = None
            for line in lines[1:]:
                line_strip = line.strip()
                if not line_strip:
                    continue
                
                if line_strip.startswith("Descripción:") or line_strip.startswith("Descripcion:"):
                    current_section = "desc"
                    description = line_strip[12:].strip()
                    continue
                elif line_strip.startswith("Criterios de Aceptación:") or line_strip.startswith("Criterios de Aceptacion:"):
                    current_section = "criteria"
                    continue
                elif line_strip.startswith("Esfuerzo Estimado:"):
                    current_section = "effort"
                    effort = line_strip[18:].strip()
                    continue
                elif line_strip.startswith("Casos de Prueba:"):
                    current_section = "cases"
                    continue
                    
                if current_section == "desc":
                    description += " " + line_strip
                elif current_section == "criteria":
                    criteria.append(line_strip)
                elif current_section == "cases":
                    cases.append(line_strip)
                    
            # Determinar categoría y ID de HU
            category = "MANT"
            category_name = "Mantenibilidad"
            if any(r in ["python:S4830"] for r in sonar_rules):
                category = "SEC"
                category_name = "Seguridad"
            elif any(r in ["python:S3516"] for r in sonar_rules):
                category = "CONF"
                category_name = "Confiabilidad"
                
            count = sum(1 for s in stories if s["category"] == category) + 1
            hu_id = f"HU-{category}-{count:02d}"
            
            effort_hours = 0.0
            eff_match = re.search(r'([\d.]+)', effort)
            if eff_match:
                effort_hours = float(eff_match.group(1))
                
            # Buscar menciones a archivos .py
            files_mentioned = re.findall(r'([a-zA-Z0-9_-]+\.py)', part)
            files_mentioned = list(set(files_mentioned))
            
            stories.append({
                "id": hu_id,
                "title": title,
                "category": category,
                "category_name": category_name,
                "description": description.strip(),
                "criteria": criteria,
                "effort": effort,
                "effort_hours": effort_hours,
                "cases": cases,
                "sonar_rules": sonar_rules,
                "files_mentioned": files_mentioned,
                "raw_block": part
            })
        return stories

    def _formatear_markdown(self, funcionalidad: str, reglas: list, impacto: str) -> str:
        reporte = [
            f"- **Funcionalidad a Modificar:** {funcionalidad}",
            "- **Reglas de Negocio Nuevas/Modificadas:**"
        ]
        reporte.extend([f"  {r}" for r in reglas])
        reporte.append(f"- **Impacto Esperado:** {impacto}")
        return "\n".join(reporte)

