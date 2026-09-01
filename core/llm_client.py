"""
LLM Client with automatic fallback.
Tries models in order until one responds without rate limit.
Compatible with OpenRouter (same protocol as OpenAI/Groq).
"""
import time
import os
from openai import OpenAI
from core.config import OPENROUTER_API_KEY

FALLBACK_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/devstral-small:free",
    "nvidia/llama-3.1-nemotron-nano-8b-v1:free",
    "openrouter/free",
]

WATCHDOG_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1:free"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "http://jarvis.local",
        "X-Title": "Jarvis Server Assistant"
    }
)


def chat_with_fallback(messages: list, tools: list = None, max_tokens: int = 1500, model_override: str = None) -> tuple:
    """
    Tries each model in order until one works.
    Returns (message_response, model_used, tokens_used)
    """
    models = [model_override] if model_override else FALLBACK_MODELS

    last_error = None
    for model in models:
        try:
            kwargs = {
                "model":      model,
                "messages":   messages,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"]       = tools
                kwargs["tool_choice"] = "auto"

            response = client.chat.completions.create(**kwargs)
            tokens   = response.usage.total_tokens if response.usage else 0
            return response.choices[0].message, model, tokens

        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["rate limit", "429", "quota", "too many", "404", "no endpoints"]):
                print(f"[LLM] {model} unavailable ({e}), trying next...")
                last_error = e
                time.sleep(1)
                continue
            else:
                print(f"[LLM] Error in {model}: {e}")
                raise

    raise Exception(f"All models are rate limited. Last error: {last_error}")
