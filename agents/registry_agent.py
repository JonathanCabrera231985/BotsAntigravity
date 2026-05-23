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
