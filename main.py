# main.py
# Punto de entrada interactivo para demostrar el sistema de agentes orquestados de SIPECOM

import os
import json
from orchestrator import Orquestador

def cargar_configuracion(ruta_config="config.json"):
    try:
        with open(ruta_config, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo de configuración '{ruta_config}'.")
        return None
    except json.JSONDecodeError:
        print(f"Error: El archivo '{ruta_config}' no tiene un formato JSON válido.")
        return None

def main():
    config = cargar_configuracion()
    if not config:
        print("Finalizando ejecución por falta de configuración.")
        return

    ruta_proyecto = config.get("ruta_proyecto", "")
    archivo_prueba = config.get("archivo_prueba", "")
    ruta_hu = config.get("ruta_hu", "")
    print("================================================================================")
    print("      SISTEMA DE AGENTES ORQUESTADOS PARA LA GESTIÓN DE CALIDAD Y OPERACIONES   ")
    print("                                   SIPECOM S.A.                                 ")
    print("================================================================================")
    print(f"Ruta del proyecto: {ruta_proyecto}")
    print(f"Archivo a analizar: {archivo_prueba if archivo_prueba else '[Analizar todo el proyecto recursivamente]'}")
    print(f"Ruta Historia Usuario: {ruta_hu}\n")

    # Inicializar el cerebro / Orquestador
    orquestador = Orquestador(ruta_proyecto=ruta_proyecto)
    
    if not archivo_prueba:
        print("El archivo_prueba está vacío en la configuración. Escaneando la ruta_proyecto...")
        archivos = orquestador.analista.listar_archivos()
        if not archivos:
            print("No se encontraron archivos de Python (.py) para procesar en la ruta del proyecto.")
            exito = False
        else:
            # Filtrar archivos que tengan historias de usuario asociadas si hay ruta_hu
            resumen_hu = None
            if ruta_hu:
                print("Cargando el backlog para filtrar archivos aplicables...")
                resumen_hu = orquestador.lector_hu.leer_historia_usuario(ruta_hu)
                
            if resumen_hu and "HistoriasBacklog" in resumen_hu:
                import re
                archivos_validos = []
                for a in archivos:
                    filename = os.path.basename(a).lower()
                    filename_no_ext = os.path.splitext(filename)[0]
                    
                    tiene_historias = False
                    for story in resumen_hu["HistoriasBacklog"]:
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
                            tiene_historias = True
                            break
                    if tiene_historias:
                        archivos_validos.append(a)
                        
                print(f"Backlog analizado. Filtrados {len(archivos_validos)} archivos aplicables (de un total de {len(archivos)} en la ruta del proyecto).")
                archivos = archivos_validos
                
                # Limpiar pestañas excedentes en Google Sheets
                nombres_validos = [f"Reporte Técnico-{os.path.splitext(os.path.basename(a))[0]}" for a in archivos]
                print("Limpiando pestañas excedentes en Google Sheets...")
                orquestador.registrador.eliminar_pestanas_excedentes(nombres_validos)
                
            if not archivos:
                print("No quedan archivos de Python (.py) aplicables para procesar en la ejecución.")
                exito = True
            else:
                print(f"Se procesarán {len(archivos)} archivos Python (.py) que corresponden al backlog:")
                for a in archivos:
                    print(f"  - {os.path.basename(a)}")
                
                exito = True
                for idx, archivo in enumerate(archivos, 1):
                    print(f"\n[Procesando {idx}/{len(archivos)}] >>> {os.path.basename(archivo)}")
                    ciclo_ok = orquestador.ejecutar_ciclo_completo(archivo, ruta_hu)
                    if not ciclo_ok:
                        print(f"El ciclo de calidad para {os.path.basename(archivo)} no se completó con éxito.")
                        exito = False
    else:
        # Ejecutar el ciclo completo sobre el archivo de prueba y la HU
        exito = orquestador.ejecutar_ciclo_completo(archivo_prueba, ruta_hu)
    
    print("\n" + "="*80)
    if exito:
        print(">>> PROCESO FINALIZADO: El ciclo operativo concluyó de manera EXITOSA. <<<")
    else:
        print(">>> PROCESO FINALIZADO: El ciclo operativo fue ABORTADO o finalizó con errores. <<<")
    print("="*80)

if __name__ == "__main__":
    main()
