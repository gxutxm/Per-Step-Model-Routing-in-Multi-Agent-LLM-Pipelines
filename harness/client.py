"""Model client.

This file defines ``call``, the single function used to send a prompt to
Gemini 3.5 Flash, Gemini 3.5 Flash-Lite, or Qwen3-8B. It selects the
provider, sends the request through LiteLLM, and returns the response
text with token counts. Repeated requests are read from the disk cache.
"""

import os
from dataclasses import dataclass

import litellm
from dotenv import load_dotenv

from harness.cache import get as cache_get
from harness.cache import put as cache_put

# Load API settings from a local .env file when present.
load_dotenv()

# Logical model names mapped to LiteLLM provider identifiers.
MODELS = {
    "flash": "gemini/gemini-3.5-flash",
    "flash-lite": "gemini/gemini-3.5-flash-lite",
    "qwen": "openai",
}


@dataclass
class ModelResponse:
    """Text and token usage for a single model call."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool = False


def call(model: str, messages: list[dict]) -> ModelResponse:
    """Call a registered model and return the response text and token counts.

    Args:
        model: One of ``flash``, ``flash-lite``, or ``qwen``.
        messages: Chat messages in OpenAI format.
    """
    if model not in MODELS:
        allowed = ", ".join(MODELS)
        raise ValueError(f"Unknown model {model!r}. Use one of: {allowed}")

    stored = cache_get(model, messages)
    if stored is not None:
        return ModelResponse(
            text=stored["text"],
            model=stored["model"],
            prompt_tokens=stored["prompt_tokens"],
            completion_tokens=stored["completion_tokens"],
            cached=True,
        )

    kwargs = {
        "messages": messages,
        # Fixed so repeated prompts stay deterministic.
        "temperature": 0,
    }

    if model == "qwen":
        api_base = os.environ.get("QWEN_API_BASE", "").strip()
        if not api_base:
            raise RuntimeError(
                "QWEN_API_BASE is not set. Set it to the address of the computer "
                "where Qwen is running."
            )
        model_name = os.environ.get("QWEN_MODEL", "Qwen/Qwen3-8B-AWQ")
        kwargs["model"] = "openai/" + model_name
        kwargs["api_base"] = api_base
        kwargs["api_key"] = os.environ.get("QWEN_API_KEY", "not-needed")
        # Qwen3 thinking mode is disabled for comparable runs.
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    else:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Set it in the environment or in a .env file."
            )
        kwargs["model"] = MODELS[model]
        kwargs["api_key"] = api_key

    response = litellm.completion(**kwargs)
    usage = response.usage

    result = ModelResponse(
        text=response.choices[0].message.content or "",
        model=model,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        cached=False,
    )
    cache_put(
        model,
        messages,
        {
            "text": result.text,
            "model": result.model,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
        },
    )
    return result
