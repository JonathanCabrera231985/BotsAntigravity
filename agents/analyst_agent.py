import re
import os
import logging
from typing import Dict, Any, List
from .base_agent import Agente

logger = logging.getLogger("SipecomAgents.AnalystAgent")

class AgenteAnalistaDesarrollador(Agente):
    """
    Agente responsable de escanear código en busca de deuda técnica y vulnerabilidades,
    generar propuestas de Historias de Usuario (HU), derivar casos de prueba QA en Gherkin,
    y aplicar parches de código automatizados.
    """

    def __init__(self, ruta_proyecto: str):
        super().__init__(ruta_proyecto)
        # Reglas de escaneo: (Nombre de regla, Patrón regex, Criticidad, Impacto, Descripción)
        self.reglas_vulnerabilidad = [
            {
                "id": "EXCEPT_PASS",
                "nombre": "Captura de excepción vacía",
                "patron": r"(except\s*(?:Exception)?\s*:\s*pass)",
                "criticidad": "Alta",
                "impacto": "Dificulta la depuración ocultando fallos críticos del sistema en producción.",
                "descripcion": "Se detectó un bloque try-except que captura excepciones y las silencia con 'pass'.",
                "propuesta_reemplazo": "except Exception as e:\n            logger.error(f\"Error inesperado en ejecución: {str(e)}\")"
            },
            {
                "id": "HARDCODED_SECRET",
                "nombre": "Credencial expuesta en código",
                "patron": r"(\b(?:password|passwd|api_key|secret_key|token|contrasena|db_pass)\s*=\s*['\"]([^'\"]{8,})['\"])",
                "criticidad": "Crítica",
                "impacto": "Fuga de credenciales sensibles en el repositorio de código fuente.",
                "descripcion": "Se detectó una asignación directa de contraseña o llave secreta de texto plano.",
                "propuesta_reemplazo": lambda m: f"{m.group().split('=')[0].strip()} = os.environ.get('{m.group().split('=')[0].strip().upper()}', 'VALOR_POR_DEFECTO')"
            },
            {
                "id": "UNSAFE_EVAL",
                "nombre": "Uso de eval() inseguro",
                "patron": r"(\beval\(([^)]+)\))",
                "criticidad": "Crítica",
                "impacto": "Riesgo extremo de Inyección de Código Arbitrario si las entradas no están saneadas.",
                "descripcion": "El uso de eval() permite evaluar strings dinámicos como código Python.",
                "propuesta_reemplazo": lambda m: f"ast.literal_eval({m.group(2)})"
            },
            {
                "id": "UNSAFE_EXEC",
                "nombre": "Uso de exec() inseguro",
                "patron": r"(\bexec\(([^)]+)\))",
                "criticidad": "Crítica",
                "impacto": "Riesgo extremo de Inyección de Código Arbitrario.",
                "descripcion": "El uso de exec() permite ejecutar strings dinámicos como código Python.",
                "propuesta_reemplazo": "None # exec bloqueado por seguridad"
            },
            {
                "id": "TODO_FIXME",
                "nombre": "Comentario pendiente (TODO/FIXME)",
                "patron": r"(#\s*(?:TODO|FIXME)\s*:\s*(.*))",
                "criticidad": "Baja",
                "impacto": "Deuda técnica acumulada que podría no resolverse.",
                "descripcion": "Comentarios en el código indicando tareas pendientes o arreglos futuros.",
                "propuesta_reemplazo": "" # Se resolverá de forma específica según el caso
            }
        ]

    def analizar_pep8_y_diseno(self, ruta_archivo: str, contenido: str) -> tuple[str, str]:
        """
        Analiza el código Python en busca de violaciones de PEP 8, Code Smells y complejidad ciclomática.
        Retorna una tupla (reporte_markdown, codigo_refactorizado).
        """
        import ast
        import re

        lineas = contenido.splitlines()
        errores_pep8 = []
        code_smells = []
        complejidad_mantenibilidad = []
        
        # --- 1. Análisis de líneas (PEP 8 simple) ---
        for idx, line in enumerate(lineas, 1):
            # Línea demasiado larga
            if len(line) > 79:
                errores_pep8.append(f"Línea {idx} excede los 79 caracteres (longitud: {len(line)}).")
            # Indentación no múltiple de 4 (expandiendo pestañas a 4 espacios para evitar falsos positivos)
            line_expanded = line.expandtabs(4)
            stripped = line_expanded.lstrip()
            if stripped and not line_expanded.startswith('#'):
                indent = len(line_expanded) - len(stripped)
                if indent % 4 != 0:
                    errores_pep8.append(f"Línea {idx} tiene una indentación que no es múltiplo de 4 ({indent} espacios tras expandir tabs).")
            # Espacios al final de línea
            if len(line) != len(line.rstrip()):
                errores_pep8.append(f"Línea {idx} tiene espacios en blanco al final.")

        # --- 2. Análisis del AST (PEP 8, Code Smells, Complejidad) ---
        try:
            tree = ast.parse(contenido)
        except Exception as e:
            errores_pep8.append(f"Error de sintaxis al compilar el archivo: {str(e)}")
            tree = None

        unused_args_map = {}
        redundant_elses = []
        complex_functions = []
        non_snake_case_names = []
        missing_docstrings = []
        
        if tree:
            for node in ast.walk(tree):
                # Faltan docstrings
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    doc = ast.get_docstring(node)
                    if not doc:
                        tipo_nodo = "función" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "clase"
                        missing_docstrings.append(f"Falta docstring en la {tipo_nodo} '{node.name}' (Línea {node.lineno}).")

                # Nombres snake_case
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not re.match(r'^[a-z_][a-z0-9_]*$', node.name):
                        non_snake_case_names.append(f"La función '{node.name}' (Línea {node.lineno}) no sigue el estándar snake_case.")
                
                # Argumentos no utilizados y elses redundantes
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Buscar argumentos
                    arg_names = [a.arg for a in node.args.args if a.arg != 'self' and a.arg != 'cls']
                    # Encontrar nombres cargados en el cuerpo
                    referenced_names = set()
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.Name) and isinstance(subnode.ctx, ast.Load):
                            referenced_names.add(subnode.id)
                    unused = [name for name in arg_names if name not in referenced_names]
                    if unused:
                        unused_args_map[node.name] = (node.lineno, unused)

                    # Else después de return
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.If) and subnode.orelse:
                            if subnode.body:
                                last_stmt = subnode.body[-1]
                                if isinstance(last_stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                                    redundant_elses.append((subnode.lineno, subnode.orelse[0].lineno))

                    # Complejidad Ciclomática
                    decision_points = 0
                    for subnode in ast.walk(node):
                        if isinstance(subnode, (ast.If, ast.For, ast.While, ast.AsyncFor, ast.comprehension, ast.ExceptHandler)):
                            decision_points += 1
                        elif isinstance(subnode, ast.BoolOp):
                            decision_points += len(subnode.values) - 1
                    
                    complexity = 1 + decision_points
                    if complexity > 5:
                        complex_functions.append((node.name, node.lineno, complexity))

        # Integrar hallazgos del AST en los reportes
        for msg in missing_docstrings:
            errores_pep8.append(msg)
        for msg in non_snake_case_names:
            code_smells.append(msg)
        for fn_name, (lineno, unused) in unused_args_map.items():
            for u in unused:
                code_smells.append(f"Argumento '{u}' no utilizado en la función '{fn_name}' (Línea {lineno}).")
        for if_line, else_line in redundant_elses:
            code_smells.append(f"Bloque 'else' innecesario después de un 'return' o 'raise' en la línea {if_line} (el 'else' comienza en la línea {else_line}).")

        # Evaluar complejidad y mantenibilidad
        if not tree:
            complejidad_mantenibilidad.append("El código no se pudo parsear sintácticamente, por lo que la mantenibilidad es muy baja.")
        elif not complex_functions:
            complejidad_mantenibilidad.append("El código tiene una complejidad ciclomática baja y es fácil de mantener.")
        else:
            for fn_name, lineno, complexity in complex_functions:
                complejidad_mantenibilidad.append(f"La función '{fn_name}' (Línea {lineno}) tiene una complejidad ciclomática alta de {complexity} (ifs, loops o condiciones anidadas). Se recomienda dividirla.")

        # --- 3. Generación de Código Refactorizado ---
        refactorizado = contenido
        
        # A) Eliminar else redundante después de return
        if redundant_elses:
            lineas_temp = list(lineas)
            for if_line, else_line in sorted(redundant_elses, key=lambda x: x[1], reverse=True):
                idx_else = else_line - 1
                while idx_else >= 0:
                    if re.match(r'^\s*else\s*:\s*(#.*)?$', lineas_temp[idx_else]):
                        break
                    idx_else -= 1
                if idx_else >= 0:
                    indent_else = len(lineas_temp[idx_else]) - len(lineas_temp[idx_else].lstrip())
                    lineas_temp.pop(idx_else)
                    idx_body = idx_else
                    while idx_body < len(lineas_temp):
                        line_content = lineas_temp[idx_body]
                        if not line_content.strip():
                            idx_body += 1
                            continue
                        indent_line = len(line_content) - len(line_content.lstrip())
                        if indent_line > indent_else:
                            lineas_temp[idx_body] = line_content[4:]
                            idx_body += 1
                        else:
                            break
            refactorizado = "\n".join(lineas_temp)
            lineas = refactorizado.splitlines()

        # B) Reemplazar == True, == False, == None
        refactorizado = re.sub(r'\b==\s*True\b', 'is True', refactorizado)
        refactorizado = re.sub(r'\b==\s*False\b', 'is False', refactorizado)
        refactorizado = re.sub(r'\b==\s*None\b', 'is None', refactorizado)
        refactorizado = re.sub(r'\b!=\s*None\b', 'is not None', refactorizado)
        
        # C) Añadir docstrings automáticos a funciones si no tienen
        if missing_docstrings:
            lineas_temp = refactorizado.splitlines()
            try:
                temp_tree = ast.parse("\n".join(lineas_temp))
                funcs_sin_doc = []
                for node in ast.walk(temp_tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not ast.get_docstring(node):
                            funcs_sin_doc.append((node.name, node.lineno))
                
                for name, lineno in sorted(funcs_sin_doc, key=lambda x: x[1], reverse=True):
                    idx_def = lineno - 1
                    idx_body = idx_def + 1
                    while idx_body < len(lineas_temp) and not lineas_temp[idx_body].strip():
                        idx_body += 1
                    if idx_body < len(lineas_temp):
                        indent = len(lineas_temp[idx_body]) - len(lineas_temp[idx_body].lstrip())
                        if indent == 0:
                            indent = 4
                        docstring_line = " " * indent + f'"""Docstring de la función {name}."""'
                        lineas_temp.insert(idx_body, docstring_line)
                refactorizado = "\n".join(lineas_temp)
                lineas = refactorizado.splitlines()
            except Exception:
                pass

        # D) Mitigar excepciones vacías
        contiene_except_pass = re.search(r'except\s*(?:Exception)?\s*:\s*pass', refactorizado)
        if contiene_except_pass:
            if "import logging" not in refactorizado:
                refactorizado = "import logging\n" + refactorizado
            lineas_temp = refactorizado.splitlines()
            for idx, line in enumerate(lineas_temp):
                if re.match(r'^\s*except\s*(?:Exception)?\s*:\s*pass\s*$', line):
                    indent = len(line) - len(line.lstrip())
                    lineas_temp[idx] = " " * indent + "except Exception as e:\n" + " " * (indent + 4) + "logging.exception(\"Error capturado en ejecución\")"
            refactorizado = "\n".join(lineas_temp)

        # Construir reporte Markdown final
        reporte_list = []
        
        reporte_list.append("### 🚨 Errores Críticos y Violaciones de Estilo (PEP 8)")
        if errores_pep8:
            for err in errores_pep8:
                reporte_list.append(f"* {err}")
        else:
            reporte_list.append("* Ninguno")
            
        reporte_list.append("\n### 🦨 Code Smells y Oportunidades de Refactorización")
        if code_smells:
            for smell in code_smells:
                reporte_list.append(f"* {smell}")
        else:
            reporte_list.append("* Ninguno")
            
        reporte_list.append("\n### 📈 Complejidad y Mantenibilidad")
        if complejidad_mantenibilidad:
            for comp in complejidad_mantenibilidad:
                reporte_list.append(f"* {comp}")
        else:
            reporte_list.append("* El código es fácil de leer y mantener.")

        reporte_list.append("\n### 🛠️ Código Refactorizado Propuesto")
        reporte_list.append("```python")
        reporte_list.append(refactorizado)
        reporte_list.append("```")
        
        reporte_markdown = "\n".join(reporte_list)
        return reporte_markdown, refactorizado

    def analizar_y_proponer(self, ruta_archivo: str) -> Dict[str, Any]:
        """
        Escanea el archivo de código en busca de deuda técnica o vulnerabilidades
        y genera una nueva Historia de Usuario (HU) en formato de diccionario.
        
        :param ruta_archivo: Ruta al archivo a analizar.
        :return: Diccionario que representa la Historia de Usuario propuesta.
        """
        logger.info(f"Iniciando análisis del archivo: {ruta_archivo}")
        contenido = self.leer_archivo(ruta_archivo)
        
        # Generar reporte PEP 8 y de diseño completo
        reporte_markdown, codigo_refactorizado = self.analizar_pep8_y_diseno(ruta_archivo, contenido)

        # Escaneo de reglas
        detalles_deuda = []
        propuestas_parche = []
        
        for regla in self.reglas_vulnerabilidad:
            matches = list(re.finditer(regla["patron"], contenido))
            if matches:
                for match in matches:
                    fragmento = match.group(1)
                    linea_num = contenido[:match.start()].count('\n') + 1
                    detalles_deuda.append(
                        f"- [{regla['criticidad']}] {regla['nombre']} en línea {linea_num}: '{fragmento}'"
                    )
                    
                    # Guardar información para el parcheo posterior
                    reemplazo = regla["propuesta_reemplazo"]
                    if callable(reemplazo):
                        reemplazo = reemplazo(match)
                        
                    propuestas_parche.append({
                        "id_regla": regla["id"],
                        "target": fragmento,
                        "replacement": reemplazo,
                        "linea": linea_num
                    })

        # Decidir nivel de criticidad máximo
        criticidad_maxima = "Baja"
        if detalles_deuda:
            criticidades = [r["criticidad"] for r in self.reglas_vulnerabilidad if any(p["id_regla"] == r["id"] for p in propuestas_parche)]
            if "Crítica" in criticidades:
                criticidad_maxima = "Crítica"
            elif "Alta" in criticidades:
                criticidad_maxima = "Alta"
            elif "Media" in criticidades:
                criticidad_maxima = "Media"

        # Construcción de la HU
        hu = {
            "Título": f"Mitigación de vulnerabilidades y deuda técnica en {os.path.basename(ruta_archivo)}",
            "Contexto": f"Durante el análisis estático del archivo {os.path.basename(ruta_archivo)}, se identificaron problemas de seguridad/mantenibilidad.",
            "Descripción": reporte_markdown,
            "Criterios de Aceptación": (
                "Escenario: Corrección de Deuda Técnica mediante Parches\n"
                "  Dado el archivo de código fuente con hallazgos detectados\n"
                "  Cuando el agente desarrollador aplica los parches de mitigación\n"
                "  Entonces las vulnerabilidades y malas prácticas identificadas son reemplazadas por código seguro y documentado."
            ),
            "Restricciones Técnicas": "Asegurar que los reemplazos de código mantengan la indentación sintáctica correcta.",
            "Nivel de Criticidad": criticidad_maxima,
            "Impacto Estimado": "Eliminación de riesgos de seguridad y mejora en la robustez operativa de SIPECOM.",
            "Parches": propuestas_parche,
            "CodigoRefactorizado": codigo_refactorizado,
            "Archivo": ruta_archivo
        }

        # Derivar casos de prueba a partir del Gherkin
        hu["Casos de Prueba"] = self.derivar_casos_prueba(hu["Criterios de Aceptación"])
        return hu

    def derivar_casos_prueba(self, criterios_aceptacion: str) -> List[Dict[str, str]]:
        """
        Deriva Casos de Prueba automáticamente de los Criterios de Aceptación en formato Gherkin.
        
        :param criterios_aceptacion: Criterios de aceptación estructurados en Gherkin.
        :return: Lista de casos de prueba con campos [Escenario, Dado, Cuando, Entonces]
        """
        casos = []
        lineas = criterios_aceptacion.split('\n')
        
        escenario_actual = "General"
        dado = ""
        cuando = ""
        entonces = ""
        
        for linea in lineas:
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue
                
            if linea_limpia.lower().startswith("escenario:"):
                if dado or cuando or entonces:
                    casos.append({
                        "Escenario": escenario_actual,
                        "Dado": dado,
                        "Cuando": cuando,
                        "Entonces": entonces
                    })
                escenario_actual = linea_limpia[len("escenario:"):].strip()
                dado, cuando, entonces = "", "", ""
            elif linea_limpia.lower().startswith("dado"):
                dado = linea_limpia[len("dado"):].strip()
            elif linea_limpia.lower().startswith("cuando"):
                cuando = linea_limpia[len("cuando"):].strip()
            elif linea_limpia.lower().startswith("entonces"):
                entonces = linea_limpia[len("entonces"):].strip()
                
        if dado or cuando or entonces:
            casos.append({
                "Escenario": escenario_actual,
                "Dado": dado,
                "Cuando": cuando,
                "Entonces": entonces
            })
            
        logger.info(f"Casos de prueba derivados: {len(casos)} casos generados a partir de Gherkin.")
        return casos

    def revisar_y_parchear(self, ruta_archivo: str, historia_usuario: Dict[str, Any]) -> str:
        """
        Aplica cambios al código del archivo basándose en la HU y los parches definidos.
        Hace uso de reemplazo preciso de tokens / palabras clave o refactorización completa.
        
        :param ruta_archivo: Ruta al archivo a modificar.
        :param historia_usuario: Historia de usuario con los metadatos de los parches.
        :return: Detalle de los cambios realizados.
        """
        logger.info(f"Iniciando fase de revisión y parcheo en: {ruta_archivo}")
        contenido_original = self.leer_archivo(ruta_archivo)
        
        # Si existe código refactorizado completo en la HU, usarlo directamente
        codigo_refactorizado = historia_usuario.get("CodigoRefactorizado")
        if codigo_refactorizado and codigo_refactorizado != contenido_original:
            exito = self.escribir_archivo(ruta_archivo, codigo_refactorizado)
            if exito:
                logger.info(f"Refactorización completa aplicada exitosamente en {ruta_archivo}")
                return "Refactorización completa de diseño aplicada (corrección PEP 8, Code Smells y Complejidad)."
            else:
                raise IOError(f"Fallo al escribir el código refactorizado en {ruta_archivo}")
                
        # Fallback al parcheo incremental original
        contenido_nuevo = contenido_original
        parches = historia_usuario.get("Parches", [])
        cambios_realizados = []
        
        if not parches:
            logger.info("No se especificaron parches automáticos para este ciclo.")
            return "Ningún cambio automático requerido (código limpio o propuesta de mejora general)."

        for parche in parches:
            target = parche["target"]
            replacement = parche["replacement"]
            
            if replacement:
                if target in contenido_nuevo:
                    if parche["id_regla"] == "EXCEPT_PASS":
                        if "import logging" not in contenido_nuevo:
                            contenido_nuevo = "import logging\n" + contenido_nuevo
                            cambios_realizados.append("Añadido 'import logging' al inicio del archivo.")
                            
                    if parche["id_regla"] == "UNSAFE_EVAL":
                        if "import ast" not in contenido_nuevo:
                            contenido_nuevo = "import ast\n" + contenido_nuevo
                            cambios_realizados.append("Añadido 'import ast' al inicio del archivo.")
                            
                    contenido_nuevo = contenido_nuevo.replace(target, replacement, 1)
                    cambios_realizados.append(f"Reemplazado '{target}' por '{replacement}' (Línea {parche['linea']}).")
                else:
                    logger.warning(f"No se encontró el bloque target para parchear: '{target}'")
            else:
                cambios_realizados.append(f"Parche manual requerido para la línea {parche['linea']}: {parche['target']}.")

        if contenido_nuevo != contenido_original:
            exito = self.escribir_archivo(ruta_archivo, contenido_nuevo)
            if exito:
                detalle_cambio = "\n".join(cambios_realizados)
                logger.info(f"Parches aplicados exitosamente en {ruta_archivo}")
                return detalle_cambio
            else:
                raise IOError(f"Fallo al escribir los cambios parcheados en {ruta_archivo}")
        else:
            logger.info(f"No se aplicaron cambios al archivo {ruta_archivo} (el contenido final es idéntico al original).")
            return "No se requirieron cambios en el archivo."

