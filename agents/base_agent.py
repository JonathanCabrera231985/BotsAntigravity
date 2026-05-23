import os
import shutil
import logging
from typing import List

# Configuración básica de logging para los agentes
logger = logging.getLogger("SipecomAgents.BaseAgent")

class Agente:
    """
    Clase base para todos los agentes del sistema de SIPECOM.
    Proporciona funcionalidades transversales para la gestión de archivos y backups.
    """
    
    def __init__(self, ruta_proyecto: str):
        """
        Constructor del agente base.
        
        :param ruta_proyecto: Ruta raíz del directorio donde reside el proyecto Python.
        :raises ValueError: Si la ruta especificada no existe o no es un directorio.
        """
        if not os.path.exists(ruta_proyecto):
            raise ValueError(f"La ruta del proyecto especificada no existe: {ruta_proyecto}")
        if not os.path.isdir(ruta_proyecto):
            raise ValueError(f"La ruta del proyecto especificada no es un directorio: {ruta_proyecto}")
            
        self.ruta_proyecto = os.path.abspath(ruta_proyecto)
        logger.info(f"Agente {self.__class__.__name__} inicializado con ruta de proyecto: {self.ruta_proyecto}")

    def crear_backup(self, ruta_archivo: str) -> str:
        """
        Crea una copia de seguridad (.bak) del archivo especificado usando shutil.
        
        :param ruta_archivo: Ruta absoluta o relativa al archivo que se respaldará.
        :return: Ruta del archivo de backup creado.
        :raises FileNotFoundError: Si el archivo original no existe.
        :raises Exception: Ante fallos en la copia del archivo.
        """
        ruta_abs = os.path.abspath(ruta_archivo)
        if not os.path.exists(ruta_abs):
            logger.error(f"No se pudo crear backup. Archivo no encontrado: {ruta_abs}")
            raise FileNotFoundError(f"Archivo no encontrado para backup: {ruta_abs}")
            
        ruta_backup = f"{ruta_abs}.bak"
        try:
            shutil.copy2(ruta_abs, ruta_backup)
            logger.info(f"Backup creado exitosamente en: {ruta_backup}")
            return ruta_backup
        except Exception as e:
            logger.error(f"Error al crear backup de {ruta_abs}: {str(e)}")
            raise e

    def listar_archivos(self) -> List[str]:
        """
        Escanea recursivamente la 'ruta_proyecto' y localiza archivos (.py) que requieran análisis.
        Excluye archivos de backup (.bak) y carpetas virtuales/especiales comunes si es necesario.
        
        :return: Lista de rutas absolutas de archivos de Python (.py) encontrados.
        """
        archivos_py = []
        logger.info(f"Escaneando archivos en el directorio del proyecto: {self.ruta_proyecto}")
        
        # Extensiones o directorios a excluir
        exclusiones = {'.git', '__pycache__', 'venv', '.venv', 'env', '.gemini'}
        
        try:
            for root, dirs, files in os.walk(self.ruta_proyecto):
                # Modificar dirs in-place para no escanear carpetas excluidas
                dirs[:] = [d for d in dirs if d not in exclusiones]
                
                for file in files:
                    if file.endswith('.py') and not file.endswith('.py.bak'):
                        ruta_completa = os.path.abspath(os.path.join(root, file))
                        archivos_py.append(ruta_completa)
            
            logger.info(f"Escaneo completado. Se encontraron {len(archivos_py)} archivos .py.")
            return archivos_py
        except Exception as e:
            logger.error(f"Error al listar archivos en {self.ruta_proyecto}: {str(e)}")
            return []

    def leer_archivo(self, ruta_archivo: str) -> str:
        """
        Lectura segura en formato UTF-8 del archivo provisto.
        
        :param ruta_archivo: Ruta al archivo a leer.
        :return: Contenido del archivo como cadena de texto.
        :raises FileNotFoundError: Si el archivo no existe.
        :raises Exception: Ante fallos en la lectura.
        """
        ruta_abs = os.path.abspath(ruta_archivo)
        if not os.path.exists(ruta_abs):
            logger.error(f"No se pudo leer el archivo. No existe: {ruta_abs}")
            raise FileNotFoundError(f"Archivo no encontrado: {ruta_abs}")
            
        try:
            with open(ruta_abs, 'r', encoding='utf-8') as f:
                contenido = f.read()
            logger.info(f"Lectura exitosa del archivo: {ruta_abs}")
            return contenido
        except Exception as e:
            logger.error(f"Error al leer el archivo {ruta_abs}: {str(e)}")
            raise e

    def escribir_archivo(self, ruta_archivo: str, contenido: str) -> bool:
        """
        Escritura con manejo robusto de excepciones (try-except).
        Escribe el contenido proporcionado en el archivo en formato UTF-8.
        
        :param ruta_archivo: Ruta al archivo donde se escribirá.
        :param contenido: Contenido a escribir.
        :return: True si se escribió correctamente, False en caso contrario.
        """
        ruta_abs = os.path.abspath(ruta_archivo)
        try:
            # Asegurar que el directorio padre existe
            directorio_padre = os.path.dirname(ruta_abs)
            if directorio_padre and not os.path.exists(directorio_padre):
                os.makedirs(directorio_padre, exist_ok=True)
                
            with open(ruta_abs, 'w', encoding='utf-8') as f:
                f.write(contenido)
            logger.info(f"Escritura exitosa en el archivo: {ruta_abs}")
            return True
        except Exception as e:
            logger.error(f"Excepción controlada al escribir en el archivo {ruta_abs}: {str(e)}")
            return False
