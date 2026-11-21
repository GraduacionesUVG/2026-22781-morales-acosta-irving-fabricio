"""Proxy hacia la API de OpenAI.

El frontend nunca llama a OpenAI directamente (eso expondría la API key
en el navegador). Todo pasa por este backend, que añade el system prompt
fijo y los parámetros fijos (modelo, temperatura) antes de reenviar.
"""

import httpx

from . import config

URL_CHAT_COMPLETIONS = "https://api.openai.com/v1/chat/completions"


class ErrorAPIOpenAI(Exception):
    pass


async def consultar_modelo(historial_mensajes: list[dict]) -> str:
    """Envía el historial de la conversación (sin el system prompt, que
    se agrega aquí) y devuelve el texto de la respuesta del modelo.

    historial_mensajes: lista de dicts {"role": "user"|"assistant", "content": str}
    """
    if not config.OPENAI_API_KEY:
        raise ErrorAPIOpenAI(
            "No hay OPENAI_API_KEY configurada. Definila como variable de "
            "entorno antes de iniciar el backend (ver README)."
        )

    mensajes = [{"role": "system", "content": config.SYSTEM_PROMPT}] + historial_mensajes

    payload = {
        "model": config.OPENAI_MODELO,
        "temperature": config.OPENAI_TEMPERATURA,
        "messages": mensajes,
    }
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        respuesta = await client.post(URL_CHAT_COMPLETIONS, json=payload, headers=headers)

    if respuesta.status_code != 200:
        raise ErrorAPIOpenAI(
            f"OpenAI respondió {respuesta.status_code}: {respuesta.text[:300]}"
        )

    datos = respuesta.json()
    return datos["choices"][0]["message"]["content"]
