import os
import csv
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from .base_agent import Agente

# Intentar importar dependencias de Google Sheets de forma segura
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False

logger = logging.getLogger("SipecomAgents.RegistryAgent")

class AgenteRegistroGoogleSheets(Agente):
    """
    Agente responsable de registrar los cambios aplicados en una hoja de control.
    Implementa conectividad con Google Sheets con fallback automático a CSV local
    en caso de falta de dependencias o credenciales no configuradas.
    """

    def __init__(self, ruta_proyecto: str, nombre_hoja: str = "Control de Cambios SIPECOM"):
        super().__init__(ruta_proyecto)
        self.nombre_hoja = nombre_hoja
        self.nombre_archivo_csv = os.path.join(self.ruta_proyecto, "control_de_cambios.csv")
        
        # Buscar credentials.json siempre en la raíz del framework BotsAntigravity
        directorio_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ruta_credenciales = os.path.join(directorio_base, "credentials.json")

    def tabular_cambios(
        self, 
        historia_usuario: Dict[str, Any], 
        detalle_cambio: str, 
        casos_prueba: List[Dict[str, str]],
        resultado_estado: str = "Aplicado"
    ) -> bool:
        """
        Registra la información del cambio en la hoja de control.
        Las columnas obligatorias son: Fecha/Hora, Agente, Historia de Usuario, 
        Archivo Modificado, Acción, Justificación, Resultado/Estado y Casos de Prueba.
        
        :param historia_usuario: La propuesta (HU) analizada.
        :param detalle_cambio: Detalle del parche aplicado.
        :param casos_prueba: Casos de prueba derivados.
        :param resultado_estado: Estado del cambio (ej. "Aplicado", "Rechazado", "Error").
        :return: True si se registró con éxito, False en caso contrario.
        """
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        agente_nombre = "AgenteAnalistaDesarrollador"
        titulo_hu = historia_usuario.get("Título", "HU sin título")
        archivo_modificado = os.path.basename(historia_usuario.get("Archivo", "Desconocido"))
        accion = detalle_cambio
        justificacion = f"Criticidad: {historia_usuario.get('Nivel de Criticidad', 'Baja')}. Impacto: {historia_usuario.get('Impacto Estimado', 'N/A')}"
        
        # Formatear casos de prueba para el registro
        casos_formateados = []
        for i, cp in enumerate(casos_prueba, 1):
            casos_formateados.append(
                f"CP{i} [{cp.get('Escenario', 'N/A')}]: Dado {cp.get('Dado', 'N/A')} / Cuando {cp.get('Cuando', 'N/A')} / Entonces {cp.get('Entonces', 'N/A')}"
            )
        casos_str = " | ".join(casos_formateados)

        datos_fila = [
            fecha_hora,
            agente_nombre,
            titulo_hu,
            archivo_modificado,
            accion,
            justificacion,
            resultado_estado,
            casos_str
        ]

        columnas = [
            "Fecha/Hora",
            "Agente",
            "Historia de Usuario",
            "Archivo Modificado",
            "Acción",
            "Justificación",
            "Resultado/Estado",
            "Casos de Prueba"
        ]

        logger.info("Iniciando proceso de tabulación de cambios...")
        
        # Intentar registro en Google Sheets si está disponible y hay credenciales
        if GOOGLE_SHEETS_AVAILABLE and os.path.exists(self.ruta_credenciales):
            try:
                logger.info(f"Intentando conectar a Google Sheets usando {self.ruta_credenciales}")
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                creds = ServiceAccountCredentials.from_json_keyfile_name(self.ruta_credenciales, scope)
                client = gspread.authorize(creds)
                
                # Intentar abrir la hoja
                try:
                    sheet = client.open(self.nombre_hoja).sheet1
                    # Verificamos si está vacía para colocar cabeceras
                    if not sheet.get_all_values():
                        sheet.append_row(columnas)
                except gspread.exceptions.SpreadsheetNotFound:
                    # Crear una nueva hoja si no existe
                    logger.info(f"Hoja '{self.nombre_hoja}' no encontrada. Creándola...")
                    sh = client.create(self.nombre_hoja)
                    # Compartir con el usuario si es necesario (el propietario de las credenciales es el dueño)
                    sheet = sh.sheet1
                    # Escribir cabeceras
                    sheet.append_row(columnas)
                
                # Escribir la nueva fila
                sheet.append_row(datos_fila)
                
                # Aplicar formato gerencial
                try:
                    sheet.freeze(rows=1)
                    sheet.format("A1:H1", {
                        "backgroundColor": {"red": 0.1, "green": 0.2, "blue": 0.4},
                        "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
                        "horizontalAlignment": "CENTER"
                    })
                    sheet.format("A2:H1000", {
                        "wrapStrategy": "WRAP",
                        "verticalAlignment": "TOP"
                    })
                    logger.info("Formato de informe gerencial aplicado exitosamente.")
                except Exception as e_fmt:
                    logger.warning(f"No se pudo aplicar el formato de celdas: {e_fmt}")

                logger.info(f"Registro exitoso en Google Sheets: '{self.nombre_hoja}'")
                return True
            except Exception as e:
                logger.warning(f"Error al conectar/escribir en Google Sheets: {str(e)}. Realizando fallback a CSV local.")
        else:
            if not GOOGLE_SHEETS_AVAILABLE:
                logger.info("Las dependencias gspread o oauth2client no están instaladas.")
            if not os.path.exists(self.ruta_credenciales):
                logger.info(f"Archivo de credenciales '{self.ruta_credenciales}' no encontrado.")
            logger.info("Procediendo con el registro en el archivo CSV local.")

        # Fallback a CSV local
        return self._tabular_csv(columnas, datos_fila)

    def _tabular_csv(self, columnas: List[str], datos_fila: List[str]) -> bool:
        """
        Método interno para registrar los datos en un archivo CSV local de forma segura.
        
        :param columnas: Cabeceras del CSV.
        :param datos_fila: Datos a registrar.
        :return: True si la escritura fue exitosa, False en caso contrario.
        """
        existe_csv = os.path.exists(self.nombre_archivo_csv)
        try:
            # Abrir en modo append (agregar al final) con codificación UTF-8
            with open(self.nombre_archivo_csv, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                
                # Si el archivo es nuevo, escribir las cabeceras primero
                if not existe_csv:
                    writer.writerow(columnas)
                    logger.info(f"Creado nuevo archivo CSV local: {self.nombre_archivo_csv}")
                
                writer.writerow(datos_fila)
            logger.info(f"Registro exitoso en CSV local: {self.nombre_archivo_csv}")
            return True
        except Exception as e:
            logger.error(f"Error crítico al escribir en el archivo CSV local: {str(e)}")
            return False

    def escribir_reporte_gerencial(self, contenido_markdown: str, nombre_pestana: str = "Reporte Técnico") -> bool:
        """
        Guarda el reporte Markdown compilado de forma estructurada y con diseño premium 
        en una nueva pestaña dentro del Google Sheet.
        """
        if not GOOGLE_SHEETS_AVAILABLE or not os.path.exists(self.ruta_credenciales):
            logger.warning("No hay credenciales o dependencias para Google Sheets. Guardando reporte en archivo local Markdown.")
            ruta_reporte = os.path.join(self.ruta_proyecto, f"{nombre_pestana.replace(' ', '_')}.md")
            with open(ruta_reporte, 'w', encoding='utf-8') as f:
                f.write(contenido_markdown)
            return True
            
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.ruta_credenciales, scope)
            client = gspread.authorize(creds)
            sh = client.open(self.nombre_hoja)
            
            # Intentar obtener la pestaña o crearla
            try:
                sheet = sh.worksheet(nombre_pestana)
                sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                sheet = sh.add_worksheet(title=nombre_pestana, rows="200", cols="10")
                
            # --- PARSER DE MARKDOWN ---
            import re
            lines = contenido_markdown.strip().split('\n')
            grid = []
            
            # Guardar estilos especiales por fila (1-indexed para gspread)
            titulos = []
            subtitulos = []
            subsubtitulos = []
            cabeceras_tabla = []
            filas_codigo = []
            filas_negrita = []
            
            current_row = 1
            in_table = False
            in_code_block = False
            
            for line in lines:
                line_strip = line.strip()
                if not line_strip:
                    grid.append([""])
                    current_row += 1
                    continue
                
                # Bloques de código (```)
                if line_strip.startswith('```'):
                    in_code_block = not in_code_block
                    continue
                
                if in_code_block:
                    grid.append(["    " + line])
                    filas_codigo.append(current_row)
                    current_row += 1
                    continue
                
                # Títulos (# ...)
                if line_strip.startswith('# '):
                    grid.append([line_strip[2:].strip()])
                    titulos.append(current_row)
                    current_row += 1
                elif line_strip.startswith('## '):
                    grid.append([line_strip[3:].strip()])
                    subtitulos.append(current_row)
                    current_row += 1
                elif line_strip.startswith('### '):
                    grid.append([line_strip[4:].strip()])
                    subsubtitulos.append(current_row)
                    current_row += 1
                elif line_strip.startswith('#### '):
                    grid.append([line_strip[5:].strip()])
                    subsubtitulos.append(current_row)
                    current_row += 1
                # Tablas (| ... |)
                elif line_strip.startswith('|'):
                    if '---' in line_strip:
                        continue
                    cells = [c.strip() for c in line_strip.split('|')[1:-1]]
                    grid.append(cells)
                    if not in_table:
                        in_table = True
                        cabeceras_tabla.append(current_row)
                    current_row += 1
                else:
                    in_table = False
                    # Verificar si es clave-valor bold (e.g. **Clave**: Valor)
                    bold_match = re.match(r'^\*\*(.*?)\*\*:\s*(.*)$', line_strip)
                    if bold_match:
                        key, val = bold_match.groups()
                        val_clean = val.replace('`', '')
                        grid.append([key + ":", val_clean])
                        filas_negrita.append(current_row)
                    else:
                        # Si tiene formato markdown negrita dentro del texto, lo limpiamos de backticks y asteriscos
                        cleaned = line_strip.replace('**', '').replace('`', '')
                        grid.append([cleaned])
                    current_row += 1
            
            # Escribir toda la data de una sola vez
            if grid:
                # Completar filas para que tengan al menos el ancho de la más larga
                max_cols = max(len(row) for row in grid) if grid else 1
                grid_normalized = [row + [""] * (max_cols - len(row)) for row in grid]
                
                # Encontrar el rango de letras (ej. A1:E200)
                letra_col_fin = chr(ord('A') + max_cols - 1)
                rango_total = f"A1:{letra_col_fin}{len(grid_normalized)}"
                sheet.update(rango_total, grid_normalized)
                
                # --- APLICAR ESTILOS PREMIUM ---
                # 1. Configuración por defecto: Ajustar texto y alineación superior
                sheet.format(f"A1:{letra_col_fin}{len(grid_normalized)}", {
                    "wrapStrategy": "WRAP",
                    "verticalAlignment": "TOP",
                    "textFormat": {"fontFamily": "Arial", "fontSize": 10}
                })
                
                # 2. Títulos principales
                for row_idx in titulos:
                    sheet.format(f"A{row_idx}:{letra_col_fin}{row_idx}", {
                        "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": {"red": 0.1, "green": 0.2, "blue": 0.4}}
                    })
                
                # 3. Subtítulos
                for row_idx in subtitulos:
                    sheet.format(f"A{row_idx}:{letra_col_fin}{row_idx}", {
                        "backgroundColor": {"red": 0.9, "green": 0.93, "blue": 0.98},
                        "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 0.15, "green": 0.25, "blue": 0.45}}
                    })
                
                # 4. Sub-subtítulos
                for row_idx in subsubtitulos:
                    sheet.format(f"A{row_idx}:{letra_col_fin}{row_idx}", {
                        "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": {"red": 0.2, "green": 0.3, "blue": 0.5}}
                    })
                
                # 5. Cabeceras de Tabla
                for row_idx in cabeceras_tabla:
                    sheet.format(f"A{row_idx}:{letra_col_fin}{row_idx}", {
                        "backgroundColor": {"red": 0.1, "green": 0.2, "blue": 0.4},
                        "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
                        "horizontalAlignment": "CENTER"
                    })
                
                # 6. Filas de Código
                for row_idx in filas_codigo:
                    sheet.format(f"A{row_idx}:{letra_col_fin}{row_idx}", {
                        "textFormat": {"fontFamily": "Courier New", "fontSize": 9, "foregroundColor": {"red": 0.3, "green": 0.3, "blue": 0.3}}
                    })
                    
                # 7. Filas de Negrita (Key-Value)
                for row_idx in filas_negrita:
                    sheet.format(f"A{row_idx}", {
                        "textFormat": {"bold": True}
                    })
            
            logger.info(f"Reporte técnico guardado y formateado exitosamente en la pestaña '{nombre_pestana}'.")
            return True
        except Exception as e:
            logger.error(f"Error al escribir y formatear el reporte gerencial en Google Sheets: {str(e)}")
            return False

    def eliminar_pestanas_excedentes(self, nombres_validos: List[str]) -> None:
        """
        Elimina las pestañas de 'Reporte Técnico-xxx' que no estén en la lista de nombres_validos.
        """
        if not GOOGLE_SHEETS_AVAILABLE or not os.path.exists(self.ruta_credenciales):
            return
            
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.ruta_credenciales, scope)
            client = gspread.authorize(creds)
            sh = client.open(self.nombre_hoja)
            
            for ws in sh.worksheets():
                name = ws.title
                if name.startswith("Reporte Técnico-"):
                    if name not in nombres_validos:
                        logger.info(f"Eliminando pestaña excedente: {name}")
                        try:
                            sh.del_worksheet(ws)
                        except Exception as e_del:
                            logger.warning(f"No se pudo eliminar la pestaña {name}: {e_del}")
        except Exception as e:
            logger.error(f"Error al conectar para eliminar pestañas excedentes: {e}")

