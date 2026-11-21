// procedimental.js — lógica específica de la tarea procedimental.
// Depende de comun.js (debe cargarse antes en el HTML).
//
// No hay botón "Entregar" en esta tarea: la respuesta final se captura
// server-side, en silencio, en el momento en que se cierra la tarea
// (atajo manual o timeout automático de 12 minutos), reusando el código
// que esté en el editor en ese instante. Ver `inicializarCierreManual`
// y `marcarInicioDeTarea` en comun.js, y el endpoint /cerrar-tarea en
// main.py.

// Texto fijo de las 3 pruebas. Vive fuera del <textarea> editable para
// que un Ctrl+A + borrar del participante no pueda eliminarlo junto con
// su código. Se concatena con el contenido editable antes de enviar el
// código completo al backend, reproduciendo exactamente el mismo texto
// que antes recibía la API cuando el participante no modifica nada.
const CODIGO_PRUEBAS_FIJO = "\n\n\n# ---- Pruebas: tu función debe pasar las tres ----\nassert sugerir_horario(\"A1\", 90) == 1000   # hueco entre reservas\nassert sugerir_horario(\"B2\", 90) == 700    # sala libre: sugiere la apertura\nassert sugerir_horario(\"C3\", 120) is None  # sin hueco suficiente";

function obtenerCodigoCompleto() {
  const editor = document.getElementById("editor-codigo");
  return editor.value + CODIGO_PRUEBAS_FIJO;
}

// Tercer disparador de cierre automático, además del atajo manual y el
// timeout de 12 minutos (ambos en comun.js): pasar las 3 pruebas con
// "Probar código" también cierra la tarea sola, reusando exactamente
// `cerrarTareaActual` de comun.js (mismo mecanismo atómico de
// prueba-silenciosa + guardado + cierre que ya usan los otros dos, no
// una copia). Se demora 8 segundos antes de cerrar de verdad, para que
// el participante alcance a leer el resultado. No se deshabilita
// "Probar código" ni el editor durante esa espera: si el participante
// vuelve a probar y el resultado empeora, se cancela (ver `ejecutarCodigo`).
const RETRASO_CIERRE_POR_PRUEBAS_MS = 8 * 1000;

let temporizadorCierrePorPruebasCompletas = null;

function cancelarCierrePorPruebasCompletas() {
  if (temporizadorCierrePorPruebasCompletas) {
    clearTimeout(temporizadorCierrePorPruebasCompletas);
    temporizadorCierrePorPruebasCompletas = null;
  }
}

function programarCierrePorPruebasCompletas() {
  cancelarCierrePorPruebasCompletas();
  temporizadorCierrePorPruebasCompletas = setTimeout(() => {
    temporizadorCierrePorPruebasCompletas = null;
    cerrarTareaActual(obtenerCodigoCompleto);
  }, RETRASO_CIERRE_POR_PRUEBAS_MS);
}

async function ejecutarCodigo() {
  const resultados = document.getElementById("resultados-pruebas");
  const boton = document.getElementById("btn-probar");

  boton.disabled = true;
  resultados.className = "resultados";
  resultados.textContent = "Ejecutando...";

  try {
    const resp = await fetch(`/api/sesion/${CODIGO_PARTICIPANTE}/ejecutar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo: obtenerCodigoCompleto() }),
    });
    const datos = await resp.json();
    if (!resp.ok) {
      resultados.className = "resultados error";
      resultados.textContent = datos.detail || "Error al ejecutar.";
      cancelarCierrePorPruebasCompletas();
      return;
    }
    resultados.className = `resultados ${datos.exito ? "exito" : "error"}`;
    resultados.textContent = datos.salida;

    // Solo el resultado MÁS RECIENTE importa: un 3/3 anterior no cuenta
    // si este intento ya no lo es, y viceversa.
    if (datos.exito) {
      programarCierrePorPruebasCompletas();
    } else {
      cancelarCierrePorPruebasCompletas();
    }
  } catch (e) {
    resultados.className = "resultados error";
    resultados.textContent = `Error de conexión: ${e.message}`;
    cancelarCierrePorPruebasCompletas();
  } finally {
    boton.disabled = false;
  }
}

// --- Numeración de línea de la zona de Producción (AOI 3) ---
//
// Puramente visual. No toca `editor.value` ni `obtenerCodigoCompleto()`:
// "Probar código", el cierre automático al pasar 3/3, el cierre silencioso
// por atajo/timeout y el registro de intentos siguen leyendo el mismo
// texto plano, sin marcas del gutter mezcladas.
//
// Una sola secuencia continua cubre las dos partes de la zona: el
// <textarea> editable se numera 1..N y el bloque de asserts (solo
// lectura) sigue en N+1..N+M, sin reiniciar. N se recalcula en cada
// edición: `input` cubre tecleo/pegado/cortar/deshacer, y `keyup` cubre
// además la indentación con Tab de comun.js, que fija `value` directo y
// no dispara `input`. El gutter del textarea sigue su scroll vertical
// desplazando su contenido interno, para no desalinearse de las líneas.
function inicializarNumerosDeLinea() {
  const editor = document.getElementById("editor-codigo");
  const pruebas = document.getElementById("editor-pruebas");
  const gutterCodigoInner = document.getElementById("gutter-codigo-inner");
  const gutterPruebas = document.getElementById("gutter-pruebas");
  if (!editor || !pruebas || !gutterCodigoInner || !gutterPruebas) return;

  const lineasDePruebas = pruebas.textContent.split("\n").length;

  function secuencia(desde, cantidad) {
    const nums = [];
    for (let i = 0; i < cantidad; i++) nums.push(desde + i);
    return nums.join("\n");
  }

  function sincronizarScrollVertical() {
    gutterCodigoInner.style.transform = `translateY(${-editor.scrollTop}px)`;
  }

  function repintar() {
    const lineasDeCodigo = editor.value.split("\n").length;
    gutterCodigoInner.textContent = secuencia(1, lineasDeCodigo);
    gutterPruebas.textContent = secuencia(lineasDeCodigo + 1, lineasDePruebas);
    sincronizarScrollVertical();
  }

  editor.addEventListener("input", repintar);
  editor.addEventListener("keyup", repintar);
  editor.addEventListener("scroll", sincronizarScrollVertical);
  window.addEventListener("resize", sincronizarScrollVertical);

  repintar();
}

// --- Auto-indentación al presionar Enter (solo en el textarea editable) ---
//
// Al pulsar Enter, la línea nueva arranca con la misma sangría (espacios
// o tabs iniciales) que la línea que se deja. Además, si el texto de esa
// línea antes del cursor termina en ":" —el signo de inicio de bloque en
// Python, p. ej. `def sugerir_horario(sala, duracion):` o un `if/for`—
// la línea nueva recibe un nivel más de sangría (4 espacios, el estilo
// que ya usa reservas.py).
//
// Alcance acotado: solo intercepta Enter dentro de #editor-codigo. No
// toca el bloque de asserts (no es editable), ni el tecleo normal, ni el
// pegado, ni la protección Ctrl+A (los asserts viven fuera del textarea).
// Usa execCommand("insertText") para conservar el historial de deshacer
// nativo y disparar el evento `input` (que repinta el gutter); si el
// navegador lo rechaza, cae a una inserción manual equivalente.
function habilitarAutoIndentacion(textarea) {
  const UN_NIVEL = "    ";
  textarea.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.isComposing || e.ctrlKey || e.metaKey || e.altKey) {
      return;
    }
    const val = textarea.value;
    const inicio = textarea.selectionStart;
    const fin = textarea.selectionEnd;
    const inicioLinea = val.lastIndexOf("\n", inicio - 1) + 1;
    const lineaAntesDelCursor = val.slice(inicioLinea, inicio);
    const sangriaActual = (lineaAntesDelCursor.match(/^[ \t]*/) || [""])[0];
    const abreBloque = lineaAntesDelCursor.replace(/\s+$/, "").endsWith(":");
    const insertar = "\n" + sangriaActual + (abreBloque ? UN_NIVEL : "");

    e.preventDefault();
    let ok = false;
    try {
      ok = document.execCommand("insertText", false, insertar);
    } catch (_) {
      ok = false;
    }
    if (!ok) {
      textarea.value = val.slice(0, inicio) + insertar + val.slice(fin);
      textarea.selectionStart = textarea.selectionEnd = inicio + insertar.length;
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  marcarInicioDeTarea("procedimental", obtenerCodigoCompleto);
  inicializarFormularioChat();
  inicializarCierreManual(obtenerCodigoCompleto);
  habilitarTabParaIndentar(document.getElementById("editor-codigo"));
  habilitarAutoIndentacion(document.getElementById("editor-codigo"));
  inicializarNumerosDeLinea();
  // Para que el atajo manual y el timeout de 12 minutos (comun.js)
  // cancelen este tercer disparador si alguno de ellos gana la carrera.
  registrarGanchoCancelarCierrePendiente(cancelarCierrePorPruebasCompletas);

  document.getElementById("btn-probar").addEventListener("click", ejecutarCodigo);
});
