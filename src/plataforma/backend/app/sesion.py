"""Control de sesión por participante.

El archivo de configuración (backend/sesiones/{codigo}.json) es la única
fuente de verdad sobre qué tarea está activa, en qué orden, y si una
tarea ya se cerró. El participante nunca decide nada de esto: el frontend
solo pregunta "qué tarea me toca mostrar ahora" y el backend responde
según este archivo. Una vez una tarea queda cerrada, no hay forma de
volver a abrirla desde ninguna ruta de la API.
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

DIR_SESIONES = Path(__file__).parent.parent / "sesiones"

TAREAS_VALIDAS = {"procedimental", "declarativa"}


class SesionNoEncontrada(Exception):
    pass


class SesionCorrupta(Exception):
    pass


class TareaYaCerrada(Exception):
    pass


def _ruta_sesion(codigo_participante: str) -> Path:
    return DIR_SESIONES / f"{codigo_participante}.json"


def crear_sesion(codigo_participante: str, orden: list[str]) -> dict:
    """Crea el archivo de configuración para un participante nuevo.
    `orden` debe ser una lista con las dos tareas en el orden
    contrabalanceado que le corresponde a ese participante, p. ej.
    ["declarativa", "procedimental"].
    """
    if set(orden) != TAREAS_VALIDAS:
        raise ValueError(f"orden debe contener exactamente {TAREAS_VALIDAS}, recibido: {orden}")

    sesion = {
        "codigo_participante": codigo_participante,
        "orden": orden,
        "tarea_actual_index": 0,
        "tareas": {
            t: {"inicio": None, "fin": None, "cerrada": False}
            for t in orden
        },
    }
    DIR_SESIONES.mkdir(parents=True, exist_ok=True)
    ruta = _ruta_sesion(codigo_participante)
    if ruta.exists():
        raise FileExistsError(
            f"Ya existe una sesión para '{codigo_participante}'. "
            "Si querés reiniciarla, borrá el archivo a mano primero: "
            f"{ruta}"
        )
    _guardar_sesion(sesion)
    return sesion


def cargar_sesion(codigo_participante: str) -> dict:
    ruta = _ruta_sesion(codigo_participante)
    if not ruta.exists():
        raise SesionNoEncontrada(
            f"No existe sesión para '{codigo_participante}'. "
            "Creala primero con crear_sesion() o el script de inicio."
        )
    contenido = ruta.read_text(encoding="utf-8")
    try:
        return json.loads(contenido)
    except json.JSONDecodeError:
        # A diferencia de registro.py, acá NO se reinicia solo: el
        # archivo de sesión controla qué tarea ya se cerró. Si se
        # reseteara en silencio, un participante podría volver a una
        # tarea ya completada, contaminando tiempos y datos oculares.
        # Se respalda para poder inspeccionarlo y se detiene con un
        # error explícito: la decisión de cómo continuar (reconstruir
        # el estado a mano, o reiniciar la sesión de ese participante)
        # queda del lado del investigador, no del código.
        marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        respaldo = ruta.with_suffix(f".corrupto-{marca}.json")
        shutil.copy2(ruta, respaldo)
        raise SesionCorrupta(
            f"El archivo de sesión de '{codigo_participante}' no es JSON "
            f"válido (posible escritura interrumpida). Se respaldó como "
            f"{respaldo.name}. Revisalo a mano: si se puede recuperar el "
            f"contenido, restauralo; si no, borrá {ruta.name} para "
            f"empezar de nuevo con ese participante (perdiendo el "
            f"progreso registrado hasta ahora)."
        )


def _guardar_sesion(sesion: dict) -> None:
    """Escritura atómica: se escribe primero a un archivo temporal en el
    mismo directorio y luego se reemplaza el archivo final con
    os.replace(), atómico tanto en Windows como en Linux. Así, si el
    proceso se interrumpe a mitad de la escritura (cierre abrupto,
    corte de luz, Ctrl+C), el archivo final nunca queda a medio
    escribir: o tiene el contenido viejo completo, o el nuevo completo,
    nunca algo intermedio o vacío."""
    DIR_SESIONES.mkdir(parents=True, exist_ok=True)
    ruta = _ruta_sesion(sesion["codigo_participante"])
    ruta_temp = ruta.with_suffix(".tmp")
    ruta_temp.write_text(json.dumps(sesion, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(ruta_temp, ruta)


def tarea_activa(codigo_participante: str) -> str | None:
    """Devuelve el nombre de la tarea que le toca ver al participante
    ahora mismo, o None si ya completó ambas."""
    sesion = cargar_sesion(codigo_participante)
    idx = sesion["tarea_actual_index"]
    if idx >= len(sesion["orden"]):
        return None
    return sesion["orden"][idx]


def iniciar_tarea_actual(codigo_participante: str) -> dict:
    """Marca el timestamp de inicio de la tarea activa. Si ya tiene
    timestamp de inicio (recarga de página), no lo pisa, para no
    contaminar el tiempo medido."""
    sesion = cargar_sesion(codigo_participante)
    nombre = tarea_activa(codigo_participante)
    if nombre is None:
        raise TareaYaCerrada("El participante ya completó ambas tareas.")
    if sesion["tareas"][nombre]["cerrada"]:
        raise TareaYaCerrada(f"La tarea '{nombre}' ya está cerrada.")
    if sesion["tareas"][nombre]["inicio"] is None:
        sesion["tareas"][nombre]["inicio"] = datetime.now(timezone.utc).isoformat()
        _guardar_sesion(sesion)
    return sesion


def cerrar_tarea_actual(codigo_participante: str) -> dict:
    """Cierra la tarea activa y avanza el índice. Una vez cerrada, no
    hay ruta en la API que vuelva a abrirla. No se puede cerrar una
    tarea que nunca se inició (evita avanzar el índice por error)."""
    sesion = cargar_sesion(codigo_participante)
    nombre = tarea_activa(codigo_participante)
    if nombre is None:
        raise TareaYaCerrada("El participante ya completó ambas tareas.")
    if sesion["tareas"][nombre]["cerrada"]:
        raise TareaYaCerrada(f"La tarea '{nombre}' ya está cerrada.")
    if sesion["tareas"][nombre]["inicio"] is None:
        raise ValueError(
            f"La tarea '{nombre}' no se ha iniciado todavía "
            "(no se llamó a tarea-activa/iniciar_tarea_actual). "
            "No se puede cerrar una tarea que no empezó."
        )

    sesion["tareas"][nombre]["fin"] = datetime.now(timezone.utc).isoformat()
    sesion["tareas"][nombre]["cerrada"] = True
    sesion["tarea_actual_index"] += 1
    _guardar_sesion(sesion)
    return sesion