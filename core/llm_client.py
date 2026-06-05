"""
LLM client with automatic fallback.
Try models in order until one responds without rate limiting.
Compatible with OpenRouter (same protocol as OpenAI/Groq).
"""
import time
import os
from openai import OpenAI
from core.config import OPENROUTER_API_KEY

# openrouter/free automatically selects a free model that supports
# the needed functionality, including tool use, so it is the ideal fallback.
# The others are specific models verified with tool use in 2026.
FALLBACK_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",  # best default, same one previously used in Groq
    "mistralai/devstral-small:free",  
    "nvidia/llama-3.1-nemotron-nano-8b-v1:free",# NVIDIA, fast, supports tools
    "openrouter/free",                          # wildcard - picks the best available
]

MONITOR_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1:free"  # lightweight model for monitoring

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
    Try each model in order until one works.
    Return (response_message, model_used, tokens_used)
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
            tokens = response.usage.total_tokens if response.usage else 0
            return response.choices[0].message, model, tokens

        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["rate limit", "429", "quota", "too many", "404", "no endpoints"]):
                print(f"[LLM] {model} unavailable ({e}), trying next...")
                last_error = e
                time.sleep(1)
                continue
            else:
                # Error other than rate limit - do not try more models
                print(f"[LLM] Error in {model}: {e}")
                raise

    # All models failed due to rate limiting
    raise Exception(f"All models are rate-limited. Last error: {last_error}")
