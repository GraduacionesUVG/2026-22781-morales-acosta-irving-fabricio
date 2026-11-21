# Resolver sin leer — Plataforma experimental

Tesis de grado, Ing. en Ciencias de la Computación y TI, Universidad del Valle de Guatemala.
Investigador: Irving Fabricio Morales Acosta. Asesor: Dennis Aldana Moscoso.

Backend en FastAPI (Python) que sirve también el frontend (HTML/CSS/JS estático).
Un solo proceso, un solo puerto. Corre 100% local, sin base de datos externa.

> **Nota sobre este documento:** refleja el estado del proyecto a partir de las
> decisiones tomadas en el desarrollo conjunto con el asistente. Antes de una
> sesión real, revisá especialmente la sección 4 (API key y modelo) y la
> sección 8 (calibración de fuente), porque son las dos cosas con más
> probabilidad de haber cambiado desde la última vez que se tocó el código.

---

## 1. Qué es

Estudio de *eye tracking* que compara cómo procesan los estudiantes dos tipos
de tarea (programar vs. aplicar un método teórico) cuando tienen una IA
disponible. Diseño intra-sujeto con contrabalanceo, ~25 participantes de
tercer año, análisis con modelos de efectos mixtos en R.

Cada participante resuelve dos tareas, en el orden que le corresponda según
el contrabalanceo:

- **Procedimental:** completar la función `sugerir_horario()` en un sistema
  de reservas de salas (`reservas.py`), pasando 3 pruebas automáticas.
- **Declarativa:** aplicar el método AMEF a un caso de lavandería, en un
  campo de texto libre, sin verificación automática (a propósito: las
  tareas declarativas académicas no tienen oráculo, y forzar uno la volvería
  menos representativa de su modalidad — esto queda documentado como
  limitación del estudio).

---

## 2. Requisitos

- Python 3.10 o superior.
- Una API key de OpenAI (solo necesaria para que el chat funcione; todo lo
  demás —layout, ejecución de código, registro de datos— funciona sin ella).

```
python3 --version
```

---

## 3. Instalación de dependencias

Desde una terminal, parado en la carpeta `backend/`:

```
pip install fastapi uvicorn python-dotenv httpx
```

Si el sistema bloquea la instalación global (Linux con
"externally-managed-environment"):

```
pip install fastapi uvicorn python-dotenv httpx --break-system-packages
```

---

## 4. API key y modelo de IA

### 4.1 La key

Se lee desde una variable de entorno o un archivo `.env` en `backend/`
(nunca hardcodeada en el código). Requiere `python-dotenv` y que
`config.py` llame a `load_dotenv()` al inicio.

Crear `backend/.env`:

```
OPENAI_API_KEY=sk-...
```

La API de OpenAI **no** comparte suscripción con ChatGPT Plus: se paga por
consumo, aparte, y hay que cargar crédito en
`platform.openai.com → Settings → Billing` para que la key funcione (un
error 429 "insufficient_quota" significa exactamente esto).

### 4.2 El modelo — leer antes de cada sesión real

Este punto es inestable: en el curso de este proyecto ya se dieron **tres
deprecaciones de modelo en pocas semanas** (`gpt-5-chat-latest`,
`gpt-5.5` sin soporte de `temperature`, `gpt-5-chat-latest` deprecado de
nuevo). El panorama en `backend/app/config.py` a la fecha:

- **Toda la familia GPT-5 actual (incluidas las variantes "chat") tiene
  `temperature` fijo en 1, no configurable.** No es un bug de un modelo
  puntual, es una decisión de producto de OpenAI en toda la línea.
- El único modelo que sigue aceptando `temperature` personalizado es la
  familia **GPT-4o / GPT-4.1**, ya retirada de la interfaz de ChatGPT pero
  todavía activa por API para integraciones existentes — **sin compromiso
  de disponibilidad a largo plazo** de parte de OpenAI.
- Recomendación usada: `gpt-4.1-mini` (o el snapshot con fecha, más
  estable: `gpt-4.1-mini-2025-04-14`).

**Antes de cada sesión con un participante, probá el chat ese mismo día.**
Dado el ritmo de deprecaciones que ya se vivió en este proyecto, no sería
raro que vuelva a pasar.

```python
# backend/app/config.py
OPENAI_MODELO = "gpt-4.1-mini"
OPENAI_TEMPERATURA = 0.3
```

Si el modelo elegido no soporta `temperature`, el error de OpenAI lo dice
explícitamente (`"temperature does not support X with this model"`) — en
ese caso, es el modelo el que hay que cambiar, no hay forma de forzarlo.

---

## 5. Levantar el servidor

Desde `backend/`:

```
python -m uvicorn app.main:app --port 8000
```

Dejar la terminal abierta durante toda la sesión.

---

## 6. Iniciar la sesión de un participante

En otra terminal, desde `backend/`:

```
python iniciar_sesion.py P07 procedimental,declarativa
```

- Primer argumento: código del participante (nunca el nombre real).
- Segundo argumento: orden contrabalanceado, sin espacios. Para el otro
  orden: `python iniciar_sesion.py P08 declarativa,procedimental`.

Abre el navegador directo en la tarea que corresponde. El participante no
ve ningún selector ni pantalla de login. Si hay que reabrir el navegador a
mitad de sesión, correr el mismo comando con el mismo código: no vuelve a
crear la sesión, retoma donde estaba.

---

## 7. Cerrar una tarea manualmente

El límite de 12 minutos es una referencia visual para el investigador, **no
algo que el sistema haga cumplir automáticamente** — decisión explícita:
no se quiso que el sistema expulsara al participante por tiempo.

Para cerrar la tarea activa (el participante entregó, o decidiste cortar),
en la misma pantalla del participante:

```
Ctrl + Shift + Alt + C
```

Cierra la tarea activa y, si queda una segunda pendiente, redirige
automáticamente. Si era la segunda, muestra "Sesión completa" — sin forma
de volver atrás desde ninguna ruta de la API.

---

## 8. Layout: 3 columnas, orden configurable, calibración de fuente

### 8.1 Estructura

La pantalla tiene tres Áreas de Interés (AOI) en **columnas iguales**, en
una sola fila, altura completa:

- **Fuente:** contenido de solo lectura (código base o instructivo AMEF).
  **Incluye la consigna de la tarea fusionada arriba**, dentro de la misma
  AOI (decisión explícita: se aceptó perder la distinción entre "leyó la
  consigna" y "consultó la fuente" como métricas separadas, a cambio de
  una columna con esa información integrada).
- **Producción:** donde el participante escribe su respuesta.
- **Chat de IA.**

No hay scroll de página en ningún caso — es un invariante metodológico:
el scroll rompe el mapeo entre fijación ocular y AOI, que es el dato
central del estudio. El scroll interno *dentro* de una AOI (por ejemplo,
en el chat o en el editor) sí está permitido.

### 8.2 Orden de columnas

Fijo para todo el estudio (no varía por participante), controlado por tres
variables CSS al inicio del `<style>` de cada archivo:

```css
--orden-fuente: 1;
--orden-produccion: 2;
--orden-chat: 3;
```

El número indica la posición de izquierda a derecha (1 = primera columna).
Cambiar los tres números en **los dos archivos por igual**
(`procedimental.html` y `declarativa.html`) si se quiere otro orden — no
se comparten entre sí.

### 8.3 Tamaño de letra de la columna "Fuente" — PENDIENTE DE CALIBRAR

Valores actuales (calibrados en una pantalla de prueba, no en el monitor
real de la universidad):

```css
/* procedimental.html */
--fuente-codigo: 0.88vh;

/* declarativa.html */
--fuente-instructivo: 1.02vh;
```

Están en `vh` (proporcional al alto de pantalla), no en píxeles fijos, a
propósito: así, cuando se mida el monitor real, alcanza con ajustar **una
sola variable** por archivo y todo se reacomoda solo, sin tocar el resto
del CSS.

**Estos valores no igualan el tamaño de letra de "Producción" o "Chat"**
(que están en `14px` fijos): se intentó igualar y el contenido dejaba de
caber sin scroll en las resoluciones de prueba. Son el máximo medido que
sostiene cero scroll con margen de seguridad.

**Cómo recalibrar contra el monitor real:**
1. Abrir el archivo en el navegador de la máquina de sesión.
2. F12 → buscar la variable en `:root` dentro del panel de estilos.
3. Subir el valor hasta que aparezca una barra de scroll en la columna de
   fuente; bajar un poco desde ahí (dejar margen: la fuente monoespaciada
   configurada, `JetBrains Mono`, puede no estar instalada en esa máquina
   y usar una alternativa con métricas ligeramente distintas).
4. Reportar el valor final para dejarlo guardado en el archivo.

---

## 9. Contenido de las tareas

### 9.1 Procedimental

- **Fuente:** `reservas.py` completo (53 líneas), de solo lectura.
- **Producción:** editor con `sugerir_horario()` a implementar, más 3
  `assert` visibles que el participante debe hacer pasar.
- **Verificación:** botón "Probar código" ejecuta el código real en un
  subproceso aislado con timeout (robustez operativa, no aislamiento de
  seguridad — la escala del estudio es un participante a la vez, en
  máquina local, con el investigador presente).
- El estado inicial de `reservas` (las reservas de prueba de A1 y C3) se
  inyecta automáticamente antes de correr el código del participante; él
  nunca ve ni escribe esa parte.
- Botón "Entregar" guarda el código final; `grado_cierre` se calcula
  automático (3 si pasaron las 3 pruebas, 0 si no).

### 9.2 Declarativa

- **Fuente:** instructivo AMEF (modo/efecto/causa, severidad cualitativa
  en 3 categorías, regla de prioridad), sin NPR ni escalas numéricas —
  se sacaron a propósito: el cálculo de NPR es una operación aritmética
  que volvía la tarea parcialmente procedimental.
- **Producción:** un único campo de texto libre, precargado con un
  andamiaje (misma lógica que el `# TU CÓDIGO AQUÍ` de la procedimental).
  Sin selects, checkboxes ni campos separados — cualquier control
  estructurado agrega re-codificación que contamina la medición de
  fijaciones/sacadas.
- **Sin verificador.** Botón "Entregar" guarda el texto tal cual;
  `grado_cierre` se envía siempre en `0` — la calificación real la hace
  el investigador a mano, con la rúbrica de tres criterios binarios
  (anclaje a la etapa correcta, severidad, priorización).

### 9.3 Preguntas de inferencia (post-Paas, no forman parte de la plataforma)

**Procedimental:**
> "En este sistema, una reserva de la sala A1 termina a las 10:00 y otra
> persona quiere reservar la misma sala iniciando exactamente a las
> 10:00. ¿El sistema acepta la segunda reserva? Explica por qué."
> Respuesta esperada: sí, por los intervalos semiabiertos `[inicio, fin)`
> en `_choca`.

**Declarativa:**
> "En un AMEF, el modo de falla X es Moderado y ocurre en la etapa 2 (la
> más temprana); el modo de falla Y es Crítico y ocurre en la etapa 4 (la
> más tardía). ¿Cuál se atiende primero? Explica por qué."
> Respuesta esperada: Y, porque un modo Crítico se atiende primero sin
> importar la etapa; "etapa más temprana" es solo el desempate.

No están integradas a la plataforma — se administran aparte (junto con el
Paas).

---

## 10. Escala de Paas

Se aplica dos veces por participante (una por tarea), fuera de la
plataforma (no hay pantalla para esto en el sistema). Un solo ítem, 1 a 9,
con las nueve anclas verbales estándar (de "muy, muy bajo esfuerzo mental"
a "muy, muy alto esfuerzo mental").

---

## 11. Dónde quedan los datos

- `backend/sesiones/{codigo}.json` — orden, tarea activa, timestamps de
  inicio/fin, si cada tarea está cerrada.
- `backend/registros/{codigo}_{tarea}.json` — interacciones con la IA
  (prompts y outputs en orden) y la respuesta final entregada, con un
  `grado_cierre` de referencia (no es la calificación definitiva en la
  tarea declarativa, ver 9.2).

Ningún archivo contiene el nombre real del participante, solo el código.

### 11.1 Si aparece un archivo corrupto

Las escrituras son atómicas (se escribe a un `.tmp` y se reemplaza el
archivo final), para que un corte a mitad de escritura no deje un archivo
vacío. Si de todas formas aparece uno corrupto (por ejemplo, de antes de
este arreglo):

- **Registro** (`registros/...`): el sistema lo detecta solo, hace una
  copia con marca de tiempo (`..._corrupto-{fecha}.json`) y sigue con un
  registro nuevo, sin intervención.
- **Sesión** (`sesiones/...`): el sistema **se detiene** con un error
  claro en vez de resetear solo — reiniciar automáticamente ahí podría
  dejar que un participante vuelva a una tarea ya cerrada. El mensaje de
  error indica el archivo de respaldo y qué hacer.

**Causa probable si esto ya pasó:** si la carpeta del proyecto vive dentro
de `Downloads` y esa carpeta está sincronizada con OneDrive, la
sincronización puede interferir con escrituras de archivos en curso. Si
es el caso, mover el proyecto fuera de cualquier carpeta sincronizada
(por ejemplo, a `C:\proyectos\resolver-sin-leer-plataforma`) elimina la
causa de raíz, no solo el síntoma.

---

## 12. Pendiente / caution list

- **Animación de "pensando" en el chat:** todavía no implementada. El
  participante no tiene ninguna señal visual de que su pregunta se está
  procesando entre que la envía y llega la respuesta (más allá del botón
  "Enviar" deshabilitado momentáneamente). Toca `comun.js` (lógica) y los
  `<style>` de ambos HTML (animación).
- **Calibración de fuente:** ver sección 8.3, pendiente contra el monitor
  real de la universidad.
- **Modelo de IA:** ver sección 4.2, probar el mismo día de cada sesión
  dado el historial de deprecaciones.
- **Ruta del proyecto:** confirmar que no está dentro de una carpeta
  sincronizada con OneDrive u otro servicio similar (ver 11.1).

---

## 13. Estructura del proyecto

```
backend/
  app/
    main.py            — endpoints de la API + monta el frontend estático
    sesion.py           — control de sesión por participante (orden, cierre,
                           escritura atómica, falla explícita si se corrompe)
    ejecutor.py           — ejecuta el código del participante en subproceso
                             con timeout
    cliente_openai.py      — proxy hacia la API de OpenAI
    registro.py              — guarda interacciones IA y respuesta final
                                (escritura atómica, recupera solo si se
                                corrompe)
    config.py                 — modelo, temperatura, system prompt (fijos
                                 para todo el estudio)
    reservas.py                — módulo real que importa el código del
                                  participante
  static/
    procedimental.html          — tarea procedimental (3 columnas)
    declarativa.html             — tarea declarativa (3 columnas)
    comun.js                      — funciones compartidas (chat, guardar,
                                     cierre manual, marcar inicio de tarea)
    procedimental.js               — lógica específica de la procedimental
    declarativa.js                  — lógica específica de la declarativa
  iniciar_sesion.py                 — script de arranque por participante
  sesiones/                          — se crea solo, un JSON por participante
  registros/                          — se crea solo, un JSON por
                                        participante y tarea
  .env                                 — API key (no se comparte ni se sube
                                          a ningún repositorio)
```
