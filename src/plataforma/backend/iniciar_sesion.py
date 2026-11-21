#!/usr/bin/env python3
"""Inicia la sesión de un participante: crea su archivo de configuración
(si no existe) y abre el navegador directo en la tarea que le toca,
sin pantalla intermedia de login.

Uso:
    python iniciar_sesion.py P07 procedimental,declarativa
    python iniciar_sesion.py P08 declarativa,procedimental

El segundo argumento es el orden contrabalanceado para ese participante
(el investigador lo decide, no se sortea aquí). Si el participante ya
tiene una sesión creada, no la vuelve a crear: simplemente abre la
tarea que le toca según el estado guardado (útil si hay que reabrir el
navegador a mitad de sesión por algún motivo).
"""

import sys
import webbrowser
import subprocess


sys.path.insert(0, str(__file__).rsplit("/", 1)[0])

from app import sesion  # noqa: E402

PUERTO = 8000  # un solo proceso, un solo puerto: FastAPI sirve la API y el frontend

NOMBRE_ARCHIVO_HTML = {
    "procedimental": "procedimental.html",
    "declarativa": "declarativa.html",
}


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    codigo_participante = sys.argv[1]
    orden = sys.argv[2].split(",")

    try:
        sesion.crear_sesion(codigo_participante, orden)
        print(f"Sesión creada para '{codigo_participante}', orden: {orden}")
    except FileExistsError:
        print(f"Ya existe sesión para '{codigo_participante}', usando la existente.")

    nombre_tarea = sesion.tarea_activa(codigo_participante)
    if nombre_tarea is None:
        print(f"'{codigo_participante}' ya completó ambas tareas. Nada que abrir.")
        sys.exit(0)

    archivo_html = NOMBRE_ARCHIVO_HTML[nombre_tarea]
    url = f"http://localhost:{PUERTO}/{archivo_html}?codigo={codigo_participante}"
    print(f"Abriendo tarea '{nombre_tarea}' para '{codigo_participante}': {url}")
    subprocess.run(["cmd", "/c", "start", "chrome", url])


if __name__ == "__main__":
    main()
