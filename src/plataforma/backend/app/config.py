"""Configuración fija del backend.

Estos valores deben ser idénticos para todos los participantes
(parametrización del modelo de IA, Fase 3 del protocolo). No deben
variar entre sesiones ni ajustarse a mitad del estudio: si se cambia
algo aquí, en principio invalida la comparabilidad con sesiones ya
corridas, salvo que sea antes de empezar la recolección real.
"""

import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
# --- Modelo de IA ---
OPENAI_MODELO = "gpt-5.5"
OPENAI_TEMPERATURA = 1


SYSTEM_PROMPT = (
    "Eres un asistente de inteligencia artificial de uso general. "
    "Respondes de forma clara, directa y concisa a las preguntas que te hacen, "
    "sin rodeos ni advertencias innecesarias. "
    "Puedes ayudar tanto con preguntas de programación en Python como con "
    "preguntas sobre métodos de análisis y gestión de calidad. "
    "Responde como lo harías normalmente ante cualquier pregunta: si te piden "
    "una solución completa, dala; si te piden una pista, da una pista. "
    "No asumas qué tan completa debe ser tu respuesta más allá de lo que la "
    "pregunta indique."
)

# --- Timeout de ejecución de código del participante ---
TIMEOUT_EJECUCION_SEGUNDOS = 10
