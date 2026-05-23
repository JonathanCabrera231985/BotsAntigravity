import ast
# test_target.py
# Archivo de prueba para demostrar el funcionamiento del sistema de agentes de SIPECOM

import os

def procesar_informacion_cliente(datos_raw):
    # TODO: Validar la estructura de datos_raw antes de procesarla
    try:
        # Uso de eval para procesar expresiones dinámicas del cliente (Vulnerabilidad)
        resultado = ast.literal_eval(datos_raw)
        print(f"Resultado procesado: {resultado}")
    except:
        # Captura de excepción vacía que oculta fallos (Deuda técnica)
        pass

def autenticar_servicio_externo():
    # Credenciales en duro (Vulnerabilidad Crítica)
    api_key = os.environ.get('API_KEY', 'VALOR_POR_DEFECTO')
    print(f"Autenticando en servicio externo con key: {api_key}")
    # FIXME: Migrar esta autenticación a OAuth2 lo antes posible
    return True

if __name__ == "__main__":
    print("Iniciando ejecución de prueba...")
    procesar_informacion_cliente("1 + 2")
    autenticar_servicio_externo()
