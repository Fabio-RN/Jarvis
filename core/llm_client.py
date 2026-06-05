"""
LLM Client con fallback automático.
Intenta modelos en orden hasta que uno responda sin rate limit.
Compatible con OpenRouter (mismo protocolo que OpenAI/Groq).
"""
import time
import os
from openai import OpenAI
from core.config import OPENROUTER_API_KEY

# openrouter/free elige automáticamente un modelo gratuito que soporte
# la funcionalidad que necesitás (incluyendo tool use) — es el fallback perfecto.
# Los demás son modelos específicos verificados con tool use en 2026.
MODELOS_FALLBACK = [
    "meta-llama/llama-3.3-70b-instruct:free",  # el mejor, mismo que tenías en Groq
    "mistralai/devstral-small:free",  
    "nvidia/llama-3.1-nemotron-nano-8b-v1:free",# NVIDIA, rápido, soporta tools ✅
    "openrouter/free",                          # comodín — elige el mejor disponible ✅
]

MODELO_VIGILANTE = "nvidia/llama-3.1-nemotron-nano-8b-v1:free"  # ligero para el vigilante

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "http://jarvis.local",
        "X-Title": "Jarvis Server Assistant"
    }
)


def chat_con_fallback(messages: list, tools: list = None, max_tokens: int = 1500, modelo_override: str = None) -> tuple:
    """
    Intenta cada modelo en orden hasta que uno funcione.
    Devuelve (mensaje_response, modelo_usado, tokens_usados)
    """
    modelos = [modelo_override] if modelo_override else MODELOS_FALLBACK

    ultimo_error = None
    for modelo in modelos:
        try:
            kwargs = {
                "model":      modelo,
                "messages":   messages,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"]       = tools
                kwargs["tool_choice"] = "auto"

            respuesta = client.chat.completions.create(**kwargs)
            tokens    = respuesta.usage.total_tokens if respuesta.usage else 0
            return respuesta.choices[0].message, modelo, tokens

        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["rate limit", "429", "quota", "too many", "404", "no endpoints"]):
                print(f"[LLM] {modelo} no disponible ({e}), probando siguiente...")
                ultimo_error = e
                time.sleep(1)
                continue
            else:
                # Error distinto a rate limit — no intentar más modelos
                print(f"[LLM] Error en {modelo}: {e}")
                raise

    # Todos fallaron por rate limit
    raise Exception(f"Todos los modelos están en rate limit. Último error: {ultimo_error}")
