// comun.js — funciones compartidas entre procedimental.html y declarativa.html
//
// El backend corre en el mismo origen (mismo proceso FastAPI que sirve
// este archivo), así que las rutas son relativas, sin necesidad de
// configurar host/puerto aquí.

function obtenerCodigoParticipante() {
  const params = new URLSearchParams(window.location.search);
  const codigo = params.get("codigo");
  if (!codigo) {
    console.error(
      "Falta el parámetro ?codigo= en la URL. Esta página debe abrirse " +
      "desde iniciar_sesion.py, no directamente."
    );
  }
  return codigo;
}

const CODIGO_PARTICIPANTE = obtenerCodigoParticipante();

// Límite de duración de cada tarea: al cumplirse desde el timestamp real
// de inicio (registrado por el backend, no por esta página), se dispara
// el cierre automático.
const DURACION_TAREA_MS = 12 * 60 * 1000;

// Handle del temporizador de cierre automático de la tarea en curso, para
// poder cancelarlo si el cierre ya ocurrió por otra vía (atajo manual).
let temporizadorCierreAutomatico = null;

// Otros disparadores de cierre automático (además del timeout de 12
// minutos, que ya se cancela abajo por su cuenta) pueden registrar acá
// una función de limpieza. `cerrarTareaActual` las llama a todas apenas
// arranca, así que sea cual sea el disparador que gane la carrera
// (atajo manual, timeout de 12 minutos, o cualquier otro), los demás
// quedan cancelados y ninguno intenta cerrar de nuevo una tarea que ya
// se está cerrando.
const ganchosCancelarCierrePendiente = [];

function registrarGanchoCancelarCierrePendiente(fn) {
  ganchosCancelarCierrePendiente.push(fn);
}

// Avisa al backend que esta tarea empieza ahora (marca el timestamp de
// inicio, si no estaba marcado ya). Debe llamarse una vez al cargar cada
// página de tarea, antes de cualquier otra interacción. Si la tarea
// servida por el backend no coincide con el HTML que se cargó, lo deja
// en consola: indicaría un desfase entre el archivo abierto a mano y el
// estado real de sesión.
//
// `obtenerCodigoCierre`, si se pasa, es la misma función que se usa para
// el cierre manual (ver `inicializarCierreManual`): se reutiliza acá
// para que el cierre automático por los 12 minutos capture el código del
// editor de la misma forma que el atajo de teclado.
//
// `obtenerCamposCierre`, si se pasa, es una función síncrona que
// devuelve un objeto con campos adicionales a mandar en el cuerpo del
// cierre (ver `cerrarTareaActual`) — lo usa la tarea declarativa para
// mandar `texto` y `metodo_guardado` sin tocar el contrato de
// `obtenerCodigoCierre` que ya usa la procedimental.
async function marcarInicioDeTarea(nombreTareaEsperado, obtenerCodigoCierre, obtenerCamposCierre) {
  try {
    const resp = await fetch(`/api/sesion/${CODIGO_PARTICIPANTE}/tarea-activa`);
    const datos = await resp.json();
    if (!resp.ok) {
      console.error("No se pudo marcar el inicio de la tarea:", datos.detail);
      return;
    }
    if (datos.tarea && datos.tarea !== nombreTareaEsperado) {
      console.warn(
        `Aviso: el backend dice que la tarea activa es '${datos.tarea}', ` +
        `pero esta página es '${nombreTareaEsperado}'. Verificar que se ` +
        `abrió la URL correcta para este participante.`
      );
    }
    if (datos.inicio) {
      programarCierreAutomatico(datos.inicio, obtenerCodigoCierre, obtenerCamposCierre);
    }
  } catch (e) {
    console.error("Error al marcar inicio de tarea:", e);
  }
}

// Programa (o reprograma) el cierre automático de la tarea activa para
// que ocurra exactamente DURACION_TAREA_MS después del timestamp real de
// inicio que devuelve el backend — no 12 minutos desde que esta página
// cargó. Así, una recarga a mitad de tarea no reinicia la cuenta: si el
// participante recarga en el minuto 10, esto programa el disparo para
// dentro de 2 minutos, no de 12.
function programarCierreAutomatico(inicioISO, obtenerCodigoCierre, obtenerCamposCierre) {
  if (temporizadorCierreAutomatico) {
    clearTimeout(temporizadorCierreAutomatico);
    temporizadorCierreAutomatico = null;
  }
  const transcurridoMs = Date.now() - new Date(inicioISO).getTime();
  const restanteMs = DURACION_TAREA_MS - transcurridoMs;
  if (restanteMs <= 0) {
    cerrarTareaActual(obtenerCodigoCierre, obtenerCamposCierre);
    return;
  }
  temporizadorCierreAutomatico = setTimeout(() => {
    cerrarTareaActual(obtenerCodigoCierre, obtenerCamposCierre);
  }, restanteMs);
}

// Historial de la conversación con la IA, en memoria. Se reinicia si se
// recarga la página (cada tarea es una conversación nueva, no continúa
// entre tareas ni entre sesiones).
const historialChat = [];

async function enviarMensajeChat(textoUsuario) {
  historialChat.push({ role: "user", content: textoUsuario });
  const resp = await fetch(`/api/sesion/${CODIGO_PARTICIPANTE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ historial: historialChat }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || "Error al consultar la IA.");
  }
  const datos = await resp.json();
  historialChat.push({ role: "assistant", content: datos.respuesta });
  return datos.respuesta;
}

function agregarMensajeAlChat(rol, texto) {
  const contenedor = document.getElementById("chat-mensajes");
  const burbuja = document.createElement("div");
  burbuja.className = `chat-mensaje chat-mensaje-${rol}`;
  burbuja.textContent = texto;
  contenedor.appendChild(burbuja);
  contenedor.scrollTop = contenedor.scrollHeight;
}

// Burbuja de "escribiendo..." (tres puntos animados) mientras se espera
// la respuesta del modelo. Se identifica por id para poder quitarla
// apenas llegue la respuesta real o un error.
function mostrarIndicadorPensando() {
  const contenedor = document.getElementById("chat-mensajes");
  const burbuja = document.createElement("div");
  burbuja.className = "chat-mensaje chat-mensaje-ia chat-mensaje-pensando";
  burbuja.id = "chat-indicador-pensando";
  burbuja.innerHTML = "<span></span><span></span><span></span>";
  contenedor.appendChild(burbuja);
  contenedor.scrollTop = contenedor.scrollHeight;
}

function quitarIndicadorPensando() {
  const burbuja = document.getElementById("chat-indicador-pensando");
  if (burbuja) burbuja.remove();
}

// Límite de expansión del textarea de entrada, en píxeles. Crece con lo
// que el participante escribe para que pueda ver más de su mensaje, pero
// no debe invadir el historial de arriba, por eso el tope.
const CHAT_INPUT_ALTURA_NORMAL = 40;
const CHAT_INPUT_ALTURA_MAXIMA = 120;

function inicializarFormularioChat() {
  const input = document.getElementById("chat-input");
  const boton = document.getElementById("chat-enviar");

  function ajustarAlturaInput() {
    input.style.height = "auto";
    const nuevaAltura = Math.min(input.scrollHeight, CHAT_INPUT_ALTURA_MAXIMA);
    input.style.height = `${nuevaAltura}px`;
  }

  function restaurarAlturaInput() {
    input.style.height = `${CHAT_INPUT_ALTURA_NORMAL}px`;
  }

  input.addEventListener("input", ajustarAlturaInput);

  async function enviar() {
    const texto = input.value.trim();
    if (!texto) return;
    input.value = "";
    restaurarAlturaInput();
    boton.disabled = true;
    agregarMensajeAlChat("usuario", texto);
    mostrarIndicadorPensando();
    try {
      const respuesta = await enviarMensajeChat(texto);
      quitarIndicadorPensando();
      agregarMensajeAlChat("ia", respuesta);
    } catch (e) {
      quitarIndicadorPensando();
      agregarMensajeAlChat("ia", `(Error al contactar la IA: ${e.message})`);
    } finally {
      boton.disabled = false;
      input.focus();
    }
  }

  boton.addEventListener("click", enviar);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  });
}

// Hace que Tab inserte una indentación en el textarea en vez de mover el
// foco al siguiente elemento (comportamiento por default del navegador).
// Se usa en los editores de producción (declarativa y procedimental), no
// en el chat, donde Tab puede seguir moviendo el foco con normalidad.
function habilitarTabParaIndentar(textarea) {
  textarea.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    e.preventDefault();
    const inicio = textarea.selectionStart;
    const fin = textarea.selectionEnd;
    textarea.value = `${textarea.value.slice(0, inicio)}    ${textarea.value.slice(fin)}`;
    textarea.selectionStart = textarea.selectionEnd = inicio + 4;
  });
}

async function guardarRespuestaFinal(respuestaFinal, gradoCierre) {
  const resp = await fetch(`/api/sesion/${CODIGO_PARTICIPANTE}/guardar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ respuesta_final: respuestaFinal, grado_cierre: gradoCierre }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || "Error al guardar la respuesta final.");
  }
  return resp.json();
}

// Cierre de la tarea activa: punto único que usan tanto el atajo de
// teclado manual como el cierre automático a los 12 minutos, para que
// exista una sola implementación del "avanzar a la siguiente tarea o
// mostrar sesión completa" (y de cómo se captura el código al cerrar).
//
// `obtenerCodigoCierre`, si se pasa, es una función síncrona que
// devuelve el código actual del editor; se manda como `codigo` en el
// mismo POST que cierra la tarea para que el backend lo pruebe en
// silencio y lo guarde como respuesta final, todo en un solo paso
// atómico (ver /cerrar-tarea en main.py). Lo usa la procedimental.
//
// `obtenerCamposCierre`, si se pasa, es una función síncrona que
// devuelve un objeto con campos adicionales para el mismo cuerpo (p. ej.
// `texto` y `metodo_guardado`, que usa la declarativa para su propia
// captura de seguridad al cierre, sin perder su botón "Entregar").
async function cerrarTareaActual(obtenerCodigoCierre, obtenerCamposCierre) {
  if (temporizadorCierreAutomatico) {
    clearTimeout(temporizadorCierreAutomatico);
    temporizadorCierreAutomatico = null;
  }
  // Cualquier otro disparador de cierre automático que haya quedado
  // pendiente (p. ej. el de "3/3 pruebas" de la procedimental) se
  // cancela acá también, antes de seguir: quien haya ganado la carrera
  // para llegar hasta acá es el único que cierra.
  for (const cancelar of ganchosCancelarCierrePendiente) {
    cancelar();
  }
  try {
    const cuerpo = {};
    if (obtenerCodigoCierre) {
      cuerpo.codigo = obtenerCodigoCierre();
    }
    if (obtenerCamposCierre) {
      Object.assign(cuerpo, obtenerCamposCierre());
    }
    const resp = await fetch(`/api/sesion/${CODIGO_PARTICIPANTE}/cerrar-tarea`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
    const datos = await resp.json();
    if (!resp.ok) {
      console.error("No se pudo cerrar la tarea:", datos.detail);
      return;
    }
    if (datos.siguiente_tarea) {
      window.location.href = `/${datos.siguiente_tarea === "procedimental" ? "procedimental" : "declarativa"}.html?codigo=${CODIGO_PARTICIPANTE}`;
    } else {
      document.body.innerHTML =
        '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:1.2vw;color:#444;">Sesión completa. Puede cerrar esta ventana.</div>';
    }
  } catch (err) {
    console.error("Error al cerrar tarea:", err);
  }
}

// Atajo de teclado discreto para que el investigador cierre la tarea
// manualmente, sin ningún elemento visible en la pantalla del
// participante. No hay confirmación visual fuerte a propósito: solo
// un cambio leve de color en el borde de la página por una fracción
// de segundo, perceptible para quien sabe qué buscar, no para el
// participante concentrado en la tarea. Tiene precedencia sobre el
// cierre automático: si se usa antes de los 12 minutos, cierra ya
// mismo (y cancela el temporizador automático, vía cerrarTareaActual).
function inicializarCierreManual(obtenerCodigoCierre, obtenerCamposCierre) {
  document.addEventListener("keydown", async (e) => {
    if (e.ctrlKey && e.shiftKey && e.altKey && e.key.toLowerCase() === "c") {
      e.preventDefault();
      await cerrarTareaActual(obtenerCodigoCierre, obtenerCamposCierre);
    }
  });
}
