"""Ejecución del código del participante.

Corre en un subproceso separado, con timeout, para que un bucle infinito
o un error no tumben el servidor mientras hay un participante enfrente.
Esto es robustez operativa, no aislamiento de seguridad: la escala del
estudio es un participante a la vez, en máquina local, con el
investigador presente.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SEGUNDOS = 10
DIR_APP = Path(__file__).parent  # acá vive reservas.py

MARCADOR_RESULTADOS = "##__RESULTADOS_JSON__##:"


PREFIJO_ESTADO_INICIAL = (
    "from reservas import _poblar_estado_inicial as _ps_inicial\n"
    "_ps_inicial()\n"
    "del _ps_inicial\n"
)


# Plantilla del arnés de pruebas que corre dentro del subproceso.
#
# En vez de ejecutar el texto del participante tal cual (función + sus
# 3 asserts como sentencias sueltas, que es lo que causaba que un primer
# assert fallido abortara el script y ocultara el resultado de los otros
# dos), este arnés:
#
#   1. Parsea el código del participante con `ast` y descarta del árbol
#      los `Assert` de nivel superior antes de ejecutarlo. Eso separa la
#      "parte definitoria" (imports + función) de la "parte de pruebas"
#      de forma estructural, no por coincidencia de texto: cualquier
#      variación de formato en los asserts (espacios, comentarios,
#      orden) da igual, porque lo que se filtra es el tipo de nodo AST,
#      no una cadena.
#   2. Ejecuta cada uno de los 3 casos conocidos por su cuenta, cada uno
#      en su propio try/except, así que una excepción en un caso
#      (assert fallido, KeyError, TypeError, error de sintaxis en la
#      definición, lo que sea) no le impide correr a los otros dos.
#   3. Imprime un único renglón final con los resultados en JSON detrás
#      de un marcador, que el proceso padre parsea para armar `salida`
#      y contar `pruebas_pasadas`.
#
# Todo esto sigue corriendo en el mismo subproceso, con el mismo
# `subprocess.run(..., timeout=TIMEOUT_SEGUNDOS)` de siempre: el
# aislamiento por prueba es solo a nivel de try/except, no de proceso.
_PLANTILLA_ARNES = '''
import ast as _ast_mod
import json as _json_mod

_codigo_participante = {codigo_repr}

_ns = {{}}
_error_definicion = None
try:
    _arbol = _ast_mod.parse(_codigo_participante)
    _arbol.body = [_n for _n in _arbol.body if not isinstance(_n, _ast_mod.Assert)]
    _ast_mod.fix_missing_locations(_arbol)
    exec(compile(_arbol, "<codigo_participante>", "exec"), _ns)
except BaseException as _e_def:
    _error_definicion = _e_def

_PRUEBAS = [
    ("A1", 90, lambda _r: _r == 1000, "hueco entre reservas"),
    ("B2", 90, lambda _r: _r == 700, "sala libre: sugiere la apertura"),
    ("C3", 120, lambda _r: _r is None, "sin hueco suficiente"),
]

_resultados = []
for _sala, _dur, _check, _desc in _PRUEBAS:
    try:
        if "sugerir_horario" not in _ns:
            raise (_error_definicion if _error_definicion is not None
                   else NameError("sugerir_horario no está definida"))
        _obtenido = _ns["sugerir_horario"](_sala, _dur)
        if _check(_obtenido):
            _resultados.append([True, _desc, None])
        else:
            _resultados.append([False, _desc, f"obtuvo {{_obtenido!r}}"])
    except BaseException as _e:
        _resultados.append([False, _desc, f"{{type(_e).__name__}}: {{_e}}"])

print({marcador!r} + _json_mod.dumps(_resultados))
'''


def _construir_script(codigo: str) -> str:
    arnes = _PLANTILLA_ARNES.format(codigo_repr=repr(codigo), marcador=MARCADOR_RESULTADOS)
    return PREFIJO_ESTADO_INICIAL + "\n" + arnes


def _parsear_resultados(stdout: str):
    """Busca el renglón de resultados en el stdout del subproceso y lo
    decodifica. Devuelve None si no está (p. ej. el arnés mismo no llegó
    a correr por algún motivo excepcional)."""
    idx = stdout.rfind(MARCADOR_RESULTADOS)
    if idx == -1:
        return None
    resto = stdout[idx + len(MARCADOR_RESULTADOS):]
    fin = resto.find("\n")
    linea = resto if fin == -1 else resto[:fin]
    try:
        datos = json.loads(linea)
    except (ValueError, TypeError):
        return None
    if not isinstance(datos, list):
        return None
    return datos


def ejecutar_codigo_participante(codigo: str) -> dict:
    """Ejecuta el código del editor (import + función del participante)
    en un subproceso aislado, con el directorio de la app en el PYTHONPATH
    para que `from reservas import ...` funcione. Los 3 casos de prueba
    fijos se corren desde un arnés propio (ver `_PLANTILLA_ARNES`), no
    como los asserts literales del participante, para que un caso fallido
    no le impida correr a los otros.

    Antes del código del participante se inyecta una llamada invisible
    que puebla el estado inicial de `reservas` (A1 y C3 con sus reservas
    de partida). El participante nunca ve ni escribe esa línea: la tarea
    solo le pide implementar `sugerir_horario`, no preparar datos.

    Devuelve un dict con:
      - exito: bool, True si pruebas_pasadas == 3
      - salida: reporte de las 3 pruebas (una línea por prueba), para
        mostrar al participante
      - timeout: bool, True si se cortó por exceder TIMEOUT_SEGUNDOS
      - pruebas_pasadas: int, cuántas de las 3 pruebas conocidas pasaron
        (0 en caso de timeout, porque no se puede saber cuántas hubieran
        pasado)
    """
    codigo_completo = _construir_script(codigo)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=DIR_APP, encoding="utf-8"
    ) as f:
        f.write(codigo_completo)
        ruta_temp = Path(f.name)

    try:
        resultado = subprocess.run(
            [sys.executable, str(ruta_temp)],
            cwd=DIR_APP,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEGUNDOS,
        )
        stdout = resultado.stdout or ""
        stderr = resultado.stderr or ""
        resultados = _parsear_resultados(stdout)

        if resultados is not None:
            pruebas_pasadas = sum(1 for paso, _desc, _detalle in resultados if paso)
            lineas = []
            for i, (paso, desc, detalle) in enumerate(resultados, start=1):
                estado = "correcta" if paso else "falló"
                linea = f"Prueba {i} ({desc}): {estado}"
                if not paso and detalle:
                    linea += f" — {detalle}"
                lineas.append(linea)
            salida = "\n".join(lineas)
        else:
            # El arnés no llegó a imprimir sus resultados (caso
            # excepcional fuera de los try/except del arnés mismo).
            pruebas_pasadas = 0
            otros = (stdout + stderr).strip()
            salida = otros or "El código no produjo resultados de las pruebas."

        return {
            "exito": pruebas_pasadas == 3,
            "salida": salida,
            "timeout": False,
            "pruebas_pasadas": pruebas_pasadas,
        }
    except subprocess.TimeoutExpired:
        return {
            "exito": False,
            "salida": f"Tiempo de ejecución excedido ({TIMEOUT_SEGUNDOS}s). "
                      "Revisa si hay un bucle infinito.",
            "timeout": True,
            "pruebas_pasadas": 0,
        }
    finally:
        ruta_temp.unlink(missing_ok=True)
