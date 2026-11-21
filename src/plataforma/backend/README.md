# Resolver sin leer — Plataforma experimental

Backend (FastAPI) + frontend (HTML/JS estático servido por el mismo backend).
Un solo proceso, un solo puerto (8000).

## 1. Requisitos

- Python 3.10 o superior instalado en la máquina donde se va a correr la sesión.
- Una API key de OpenAI (necesaria solo para que el chat de IA funcione;
  todo lo demás —layout, ejecución de código, registro de datos— funciona
  sin ella).

Verificar Python instalado:

```
python3 --version
```

Si no está instalado, instalarlo desde https://www.python.org/downloads/
(en Windows, marcar la casilla "Add Python to PATH" durante la instalación).

## 2. Instalación de dependencias

Desde una terminal, parado en la carpeta `backend/`:

```
pip install fastapi uvicorn python-dotenv httpx
```

Si el sistema operativo bloquea la instalación global (Linux con
"externally-managed-environment"), usar:

```
pip install fastapi uvicorn python-dotenv httpx --break-system-packages
```

## 3. Configurar la API key de OpenAI

El backend lee la key desde una variable de entorno, nunca desde un
archivo dentro del proyecto (para no exponerla por accidente).

**En Windows (PowerShell), antes de iniciar el servidor cada vez:**
```
$env:OPENAI_API_KEY = "sk-..."
```

**En macOS/Linux:**
```
export OPENAI_API_KEY="sk-..."
```

Alternativa más cómoda: crear un archivo `.env` dentro de `backend/`
con la línea `OPENAI_API_KEY=sk-...` (este archivo no se sube a ningún
lado ni se comparte; si en algún momento se versiona el proyecto con
git, agregar `.env` al `.gitignore`).

Mientras no se configure la key, todo el resto de la plataforma
funciona igual; solo el chat de IA mostrará un mensaje de error claro
en lugar de una respuesta.

## 4. Elegir el modelo (opcional)

Por default está configurado `gpt-4o-mini` en `app/config.py`. Para
cambiarlo, editar la línea `OPENAI_MODELO` en ese archivo, una sola vez,
antes de iniciar la recolección de datos real (no cambiarlo a mitad del
estudio: rompe la comparabilidad entre sesiones).

También en `config.py` está `SYSTEM_PROMPT`: revisarlo y ajustarlo antes
de la sesión real si se considera necesario.

## 5. Levantar el servidor

Desde la carpeta `backend/`:

```
python3 -m uvicorn app.main:app --port 8000
```

Dejar esa terminal abierta mientras dure la sesión. Si aparece
`Application startup complete`, el servidor está listo.

## 6. Iniciar la sesión de un participante

**En otra terminal** (o pestaña), desde la carpeta `backend/`:

```
python3 iniciar_sesion.py P07 procedimental,declarativa
```

- El primer argumento es el código del participante (lo decide el
  investigador, nunca el nombre real).
- El segundo argumento es el orden contrabalanceado para ese
  participante: la tarea que debe hacer primero, luego la segunda,
  separadas por coma, sin espacios. Para el otro orden:
  ```
  python3 iniciar_sesion.py P08 declarativa,procedimental
  ```

Esto abre automáticamente el navegador en la tarea que le corresponde.
El participante no ve ninguna pantalla de login ni selector de tarea.

Si por algún motivo hay que volver a abrir el navegador a mitad de
sesión (se cerró por error, por ejemplo), correr el mismo comando otra
vez con el mismo código: no vuelve a crear la sesión, abre la tarea que
estaba activa según el estado guardado.

## 7. Cerrar una tarea manualmente

El límite de 12 minutos es una referencia visual, no algo que el sistema
haga cumplir automáticamente. Para cerrar la tarea activa cuando el
investigador lo decida (ya sea porque el participante entregó, o porque
pasó el tiempo), presionar en la misma pantalla del participante:

```
Ctrl + Shift + Alt + C
```

Esto cierra la tarea activa y, si queda una segunda tarea pendiente,
redirige automáticamente a ella. Si ya era la segunda, muestra un
mensaje de "Sesión completa" y no hay forma de volver atrás.

## 8. Dónde quedan los datos

- `backend/sesiones/{codigo}.json` — estado de la sesión: orden,
  tarea activa, timestamps de inicio/fin, si cada tarea está cerrada.
- `backend/registros/{codigo}_{tarea}.json` — interacciones con la IA
  (prompts y outputs en orden) y la respuesta final entregada (código o
  tabla AMEF + justificación), con un grado de cierre automático de
  referencia (la calificación definitiva según la rúbrica se hace
  revisando el contenido completo, no solo este número).

Ningún archivo contiene el nombre real del participante, solo el código.

## 9. Antes de la sesión real en la universidad

El tamaño de fuente de ambas tareas (`--fuente-codigo` en
`procedimental.html`, `--fuente-instructivo` en `declarativa.html`) está
calibrado de forma provisional contra una pantalla de 1920×1080. Cuando
se mida el monitor real de la sesión, ajustar esas variables (están
documentadas con comentarios en cada archivo) hasta que el contenido
completo quepa sin que aparezca scroll. Hay un script de verificación
rápida si se necesita (preguntar, no está incluido en este paquete por
default).

## 10. Estructura del proyecto

```
backend/
  app/
    main.py          — endpoints de la API + monta el frontend estático
    sesion.py         — control de sesión por participante (orden, cierre)
    ejecutor.py        — ejecuta el código del participante en subproceso con timeout
    cliente_openai.py  — proxy hacia la API de OpenAI
    registro.py         — guarda interacciones IA y respuesta final
    config.py            — modelo, temperatura, system prompt (fijos)
    reservas.py           — módulo real que importa el código del participante
  static/
    procedimental.html     — tarea procedimental (código Python)
    declarativa.html        — tarea declarativa (tabla AMEF)
    comun.js                 — funciones compartidas (chat, guardar, cierre manual)
    procedimental.js          — lógica específica de la tarea procedimental
    declarativa.js              — lógica específica de la tarea declarativa
  iniciar_sesion.py             — script de arranque por participante
  sesiones/                      — se crea automáticamente, un JSON por participante
  registros/                      — se crea automáticamente, un JSON por participante y tarea
```
