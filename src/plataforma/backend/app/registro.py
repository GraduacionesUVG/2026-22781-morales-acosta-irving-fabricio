"""Registro de datos de sesión (sección 4 del documento de tareas/datos).

Un archivo JSON por participante y tarea, con:
  - interacciones con la IA (prompts y outputs, en orden)
  - respuesta final (código o tabla)
  - tiempos (inicio/fin, ya cubiertos por sesion.py)

No se registra el nombre del participante en ningún lado, solo el
código, conforme al consentimiento informado.
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

DIR_REGISTROS = Path(__file__).parent.parent / "registros"


def _ruta_registro(codigo_participante: str, tarea: str) -> Path:
    return DIR_REGISTROS / f"{codigo_participante}_{tarea}.json"


def _cargar_o_crear(codigo_participante: str, tarea: str) -> dict:
    ruta = _ruta_registro(codigo_participante, tarea)
    if ruta.exists():
        contenido = ruta.read_text(encoding="utf-8")
        try:
            return json.loads(contenido)
        except json.JSONDecodeError:
            # El archivo existe pero no es JSON válido (típicamente: una
            # escritura anterior se interrumpió a mitad de camino, o algo
            # externo -como sincronización de OneDrive en la carpeta del
            # proyecto- lo dejó vacío o truncado). No se descarta en
            # silencio: se respalda con timestamp para poder inspeccionarlo
            # después, y se continúa con un registro nuevo para no perder
            # la sesión en curso.
            marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            respaldo = ruta.with_suffix(f".corrupto-{marca}.json")
            shutil.copy2(ruta, respaldo)
            print(
                f"[registro] AVISO: {ruta.name} no era JSON válido "
                f"(¿escritura interrumpida?). Se respaldó como "
                f"{respaldo.name} y se empieza un registro nuevo para "
                f"'{codigo_participante}' / '{tarea}'."
            )
    return {
        "codigo_participante": codigo_participante,
        "tarea": tarea,
        "interacciones_ia": [],
        "intentos_codigo": [],
        "respuesta_final": None,
        "grado_cierre": None,
        "metodo_guardado": None,
    }


def _guardar(registro: dict) -> None:
    """Escritura atómica: se escribe primero a un archivo temporal en el
    mismo directorio y luego se reemplaza el archivo final con
    os.replace(), que en Windows y Linux es una operación atómica a nivel
    de sistema de archivos. Así, si el proceso se interrumpe a mitad de
    la escritura (cierre abrupto, corte de luz, Ctrl+C), el archivo
    final nunca queda a medio escribir: o tiene el contenido viejo
    completo, o el nuevo completo, nunca algo intermedio o vacío."""
    DIR_REGISTROS.mkdir(parents=True, exist_ok=True)
    ruta = _ruta_registro(registro["codigo_participante"], registro["tarea"])
    ruta_temp = ruta.with_suffix(".tmp")
    ruta_temp.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(ruta_temp, ruta)


def registrar_interaccion_ia(codigo_participante: str, tarea: str, prompt: str, output: str) -> None:
    registro = _cargar_o_crear(codigo_participante, tarea)
    registro["interacciones_ia"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "output": output,
    })
    _guardar(registro)


def registrar_intento_codigo(codigo_participante: str, tarea: str, codigo: str, pruebas_pasadas: int) -> None:
    """Registra un intento de 'Probar código', se haya o no logrado pasar
    las 3 pruebas. A diferencia de `guardar_respuesta_final` (que pisa un
    único valor), acá se acumula un intento por llamada: cada click en
    'Probar código' agrega una entrada nueva, en orden, sin perder los
    intentos anteriores de la misma sesión."""
    registro = _cargar_o_crear(codigo_participante, tarea)
    registro.setdefault("intentos_codigo", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "codigo": codigo,
        "pruebas_pasadas": pruebas_pasadas,
    })
    _guardar(registro)


def guardar_respuesta_final(
    codigo_participante: str,
    tarea: str,
    respuesta_final,
    grado_cierre: int,
    metodo_guardado: str | None = None,
) -> None:
    """`respuesta_final` es un str en ambas tareas: el código del editor
    en la procedimental, y el texto libre del campo de producción en la
    declarativa. En la declarativa `grado_cierre` llega siempre como 0
    (no hay verificación automática); el grado real lo asigna el
    investigador a mano sobre el texto guardado, con la rúbrica de tres
    criterios binarios.

    `metodo_guardado` es puramente informativo (no afecta qué se guarda
    como `respuesta_final`, que siempre es el contenido pasado acá): en
    la tarea declarativa distingue si el participante llegó a hacer
    click en "Entregar" al menos una vez antes del cierre
    ("entrega_manual") o si el cierre lo capturó sin que eso pasara
    ("captura_automatica_cierre"). Se deja `None` (sin pisar el valor
    existente) cuando no aplica, como en la tarea procedimental."""
    registro = _cargar_o_crear(codigo_participante, tarea)
    registro["respuesta_final"] = respuesta_final
    registro["grado_cierre"] = grado_cierre
    if metodo_guardado is not None:
        registro["metodo_guardado"] = metodo_guardado
    _guardar(registro)


def cargar_registro(codigo_participante: str, tarea: str) -> dict:
    return _cargar_o_crear(codigo_participante, tarea)