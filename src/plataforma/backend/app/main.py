"""Backend de la plataforma "Resolver sin leer".

Endpoints:
  GET  /api/sesion/{codigo}/tarea-activa   -> qué tarea mostrar ahora
  POST /api/sesion/{codigo}/chat            -> proxy a OpenAI + registro
  POST /api/sesion/{codigo}/ejecutar        -> corre el código del participante (solo procedimental)
  POST /api/sesion/{codigo}/guardar         -> guarda la respuesta final (código o tabla)
  POST /api/sesion/{codigo}/cerrar-tarea    -> cierre (manual por atajo, o automático por timeout), avanza a la siguiente tarea o termina

Arranque: ver README.md para cómo crear una sesión e iniciar el servidor.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import cliente_openai, ejecutor, registro, sesion

app = FastAPI(title="Resolver sin leer — Backend")

# CORS abierto: la plataforma corre 100% local, en la misma máquina,
# operada por una sola persona a la vez. No hay exposición a red externa.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Modelos de request ----------

class MensajeChat(BaseModel):
    historial: list[dict]  # [{"role": "user"|"assistant", "content": str}, ...]


class CodigoAEjecutar(BaseModel):
    codigo: str


class RespuestaFinal(BaseModel):
    respuesta_final: str | dict
    grado_cierre: int


class CierreTarea(BaseModel):
    # `codigo` se envía (y solo se usa) cuando la tarea activa es la
    # procedimental: es el código que está en el editor en el instante
    # del cierre, para guardarlo como respuesta final antes de cerrar.
    codigo: str | None = None
    # `texto` se envía (y solo se usa) cuando la tarea activa es la
    # declarativa: es el contenido de `editor-declarativa` en el
    # instante del cierre. A diferencia de la procedimental, la
    # declarativa TAMBIÉN sigue teniendo su botón "Entregar" explícito;
    # este campo es la red de seguridad para cuando el cierre (manual o
    # automático) ocurre sin que ese click haya pasado, o después de que
    # el participante siguió escribiendo tras entregar.
    texto: str | None = None
    # Puramente informativo: si el participante ya había hecho click en
    # "Entregar" al menos una vez antes de este cierre. No afecta qué se
    # guarda como respuesta final (siempre gana el contenido del editor
    # en el instante del cierre), solo queda registrado para análisis.
    metodo_guardado: str | None = None


# ---------- Manejo centralizado de errores de sesión ----------
# SesionCorrupta puede saltar desde cualquier endpoint (todos pasan por
# sesion.cargar_sesion en algún punto), así que se atrapa acá una sola
# vez en vez de repetir el try/except en cada ruta. Se devuelve 409
# (conflicto de estado del servidor) con el mensaje accionable que ya
# arma sesion.py, para que el investigador sepa qué hacer sin tener que
# leer un traceback.

@app.exception_handler(sesion.SesionCorrupta)
async def manejar_sesion_corrupta(request, exc: sesion.SesionCorrupta):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# ---------- Endpoints ----------

@app.get("/api/sesion/{codigo}/tarea-activa")
def obtener_tarea_activa(codigo: str):
    try:
        nombre_tarea = sesion.tarea_activa(codigo)
    except sesion.SesionNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))

    if nombre_tarea is None:
        return {"tarea": None, "mensaje": "El participante ya completó ambas tareas."}

    sesion_actual = sesion.iniciar_tarea_actual(codigo)
    inicio = sesion_actual["tareas"][nombre_tarea]["inicio"]
    return {"tarea": nombre_tarea, "inicio": inicio}


@app.post("/api/sesion/{codigo}/chat")
async def chat(codigo: str, body: MensajeChat):
    try:
        nombre_tarea = sesion.tarea_activa(codigo)
    except sesion.SesionNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    if nombre_tarea is None:
        raise HTTPException(status_code=409, detail="No hay tarea activa.")

    try:
        respuesta = await cliente_openai.consultar_modelo(body.historial)
    except cliente_openai.ErrorAPIOpenAI as e:
        raise HTTPException(status_code=502, detail=str(e))

    ultimo_prompt = body.historial[-1]["content"] if body.historial else ""
    registro.registrar_interaccion_ia(codigo, nombre_tarea, ultimo_prompt, respuesta)

    return {"respuesta": respuesta}


@app.post("/api/sesion/{codigo}/ejecutar")
def ejecutar(codigo: str, body: CodigoAEjecutar):
    try:
        nombre_tarea = sesion.tarea_activa(codigo)
    except sesion.SesionNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    if nombre_tarea != "procedimental":
        raise HTTPException(
            status_code=409,
            detail="La ejecución de código solo aplica a la tarea procedimental.",
        )

    resultado = ejecutor.ejecutar_codigo_participante(body.codigo)
    registro.registrar_intento_codigo(codigo, nombre_tarea, body.codigo, resultado["pruebas_pasadas"])
    return resultado


@app.post("/api/sesion/{codigo}/guardar")
def guardar(codigo: str, body: RespuestaFinal):
    try:
        nombre_tarea = sesion.tarea_activa(codigo)
    except sesion.SesionNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    if nombre_tarea is None:
        raise HTTPException(status_code=409, detail="No hay tarea activa.")

    registro.guardar_respuesta_final(codigo, nombre_tarea, body.respuesta_final, body.grado_cierre)
    return {"ok": True}


@app.post("/api/sesion/{codigo}/cerrar-tarea")
def cerrar_tarea(codigo: str, body: CierreTarea | None = None):
    """Cierre de la tarea activa: manual (atajo de teclado del
    investigador) o automático (límite de 12 minutos). Avanza el índice
    de tarea; no hay ruta que vuelva atrás.

    Si la tarea activa es la procedimental y el frontend mandó el
    código que está en el editor en este instante, ese código se
    corre en silencio contra el arnés de pruebas y se guarda como
    respuesta final ANTES de cerrar la tarea, en el mismo paso atómico
    de este endpoint (una sola llamada, no dos idas y vueltas
    separadas). Esto es a propósito: un cierre (sea manual o por
    timeout) sin captura del código en ese momento fue exactamente el
    incidente de pérdida de datos que motivó este cambio.

    Si la tarea activa es la declarativa y el frontend mandó el texto
    del editor, ese texto se guarda como respuesta final de la misma
    forma, ANTES de cerrar, pisando lo que hubiera (incluso si ya se
    había entregado antes con el botón "Entregar": el contenido del
    editor en el instante del cierre siempre es el que vale, porque el
    participante puede seguir escribiendo después de entregar). La
    tarea declarativa sigue teniendo su botón "Entregar" explícito sin
    cambios; esto es solo la red de seguridad para cuando el cierre
    ocurre sin ese click, o con ediciones posteriores a él."""
    try:
        nombre_tarea = sesion.tarea_activa(codigo)
    except sesion.SesionNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))

    if nombre_tarea == "procedimental" and body is not None and body.codigo is not None:
        resultado = ejecutor.ejecutar_codigo_participante(body.codigo)
        registro.guardar_respuesta_final(
            codigo, nombre_tarea, body.codigo, resultado["pruebas_pasadas"]
        )
    elif nombre_tarea == "declarativa" and body is not None and body.texto is not None:
        registro.guardar_respuesta_final(
            codigo, nombre_tarea, body.texto, 0, metodo_guardado=body.metodo_guardado
        )

    try:
        sesion.cerrar_tarea_actual(codigo)
    except sesion.SesionNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    except sesion.TareaYaCerrada as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    siguiente = sesion.tarea_activa(codigo)
    return {"siguiente_tarea": siguiente}


# ---------- Archivos estáticos del frontend ----------
# Montado al final, después de las rutas /api/..., para que estas tengan
# prioridad. Sirve procedimental.html y declarativa.html directamente
# desde backend/static/, en el mismo proceso y puerto que la API.
DIR_STATIC = Path(__file__).parent.parent / "static"
app.mount("/", StaticFiles(directory=DIR_STATIC, html=True), name="static")