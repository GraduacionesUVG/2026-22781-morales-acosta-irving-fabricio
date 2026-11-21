// declarativa.js — lógica específica de la tarea declarativa.
// Depende de comun.js (debe cargarse antes en el HTML).
//
// La tarea declarativa NO tiene verificador ni oráculo, a diferencia de
// la procedimental (que ejecuta 3 pruebas). Es deliberado: las tareas
// declarativas académicas no tienen comprobación automática, y forzar
// una la volvería menos representativa de su modalidad. La ausencia de
// oráculo queda documentada como limitación del estudio.
//
// A diferencia de la procedimental, esta tarea SÍ conserva su botón
// "Entregar" explícito: así funciona hoy y no cambia. Lo que sí se
// agrega es una red de seguridad al cierre (manual o por timeout de 12
// minutos): el contenido de `editor-declarativa` en el instante del
// cierre siempre se manda al backend y siempre gana como respuesta
// final, se haya entregado antes o no (el participante puede seguir
// escribiendo después de entregar). `entregoClickeado` es solo un dato
// informativo sobre si "Entregar" se usó alguna vez antes del cierre;
// no cambia qué se guarda.
let entregoClickeado = false;

async function entregarRespuesta() {
  const boton = document.getElementById("btn-entregar");
  const mensaje = document.getElementById("mensaje-entrega");
  const editor = document.getElementById("editor-declarativa");

  boton.disabled = true;
  try {
    // grado_cierre se envía siempre como 0: NO es una calificación.
    // Esta tarea no tiene verificación automática, así que aquí no se
    // evalúa nada. El investigador asigna el grado 0-3 después, a mano,
    // sobre el texto guardado, con la rúbrica de tres criterios
    // binarios (anclaje / severidad / priorización). Cualquier valor
    // distinto de 0 en este campo sería un artefacto, no un resultado.
    await guardarRespuestaFinal(editor.value, 0);
    entregoClickeado = true;
    mensaje.style.display = "block";
    mensaje.textContent = "Entregado. Espera instrucciones.";
  } catch (e) {
    mensaje.style.display = "block";
    mensaje.textContent = `No se pudo entregar: ${e.message}`;
    boton.disabled = false;
  }
}

// Campos adicionales que se mandan junto con el cierre de la tarea (ver
// `cerrarTareaActual` en comun.js): el texto actual del editor, y si
// "Entregar" ya se había usado antes de este cierre.
function obtenerCamposCierreDeclarativa() {
  const editor = document.getElementById("editor-declarativa");
  return {
    texto: editor.value,
    metodo_guardado: entregoClickeado ? "entrega_manual" : "captura_automatica_cierre",
  };
}

document.addEventListener("DOMContentLoaded", () => {
  marcarInicioDeTarea("declarativa", null, obtenerCamposCierreDeclarativa);
  inicializarFormularioChat();
  inicializarCierreManual(null, obtenerCamposCierreDeclarativa);
  habilitarTabParaIndentar(document.getElementById("editor-declarativa"));

  document.getElementById("btn-entregar").addEventListener("click", entregarRespuesta);
});