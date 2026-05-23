# main.py
# Punto de entrada interactivo para demostrar el sistema de agentes orquestados de SIPECOM

import os
from orchestrator import Orquestador

def main():
    # Obtener el directorio actual donde se reside el proyecto
    #ruta_proyecto = os.path.dirname(os.path.abspath(__file__))
    #archivo_prueba = os.path.join(ruta_proyecto, "test_target.py")

     # Define la ruta raíz de tu proyecto
    ruta_proyecto = r"C:\Users\Jonathan Cabrera\Downloads\Bot\Python\lib_py\fuentes\ComprobantesRecibidos"
    
    # Define el archivo específico de ese proyecto que quieres analizar y parchear
    archivo_prueba = r"C:\Users\Jonathan Cabrera\Downloads\Bot\Python\lib_py\fuentes\ComprobantesRecibidos\munchery_spider.py"
    
    # Opcional: Define la ruta o URL de Google Docs de la Historia de Usuario
    #ruta_hu = "https://docs.google.com/document/d/1Ejemplo12345/edit" # O un archivo local como r"C:\ruta\HU.md"

    ruta_hu = "https://docs.google.com/document/d/1StSqfTFJscH9JPFnTvBMKgwOm1cf2TShoCa_uu0VG5s/edit?usp=sharing"

    
    print("================================================================================")
    print("      SISTEMA DE AGENTES ORQUESTADOS PARA LA GESTIÓN DE CALIDAD Y OPERACIONES   ")
    print("                                   SIPECOM S.A.                                 ")
    print("================================================================================")
    print(f"Ruta del proyecto: {ruta_proyecto}")
    print(f"Archivo a analizar: {archivo_prueba}")
    print(f"Ruta Historia Usuario: {ruta_hu}\n")

    # Inicializar el cerebro / Orquestador
    orquestador = Orquestador(ruta_proyecto=ruta_proyecto)
    
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
