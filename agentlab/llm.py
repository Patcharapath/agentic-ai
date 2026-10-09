"""One place to choose the LLM for every lab.

Settings come from the ``.env`` file next to ``pyproject.toml`` (copy ``.env.example``). Typical use::

    from agentlab import get_llm

    llm = get_llm()                      # provider and model from .env
    llm = get_llm("openrouter")          # another provider, its default model
    llm = get_llm("ollama", "qwen3.5:9b", temperature=0.7)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

LABS_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(LABS_ROOT / ".env")

# provider -> (env var holding the model name, default model, env var holding the API key)
PROVIDERS: dict[str, tuple[str, str, str | None]] = {
    "ollama": ("OLLAMA_MODEL", "qwen3.5:4b", None),
    "openrouter": ("OPENROUTER_MODEL", "google/gemma-4-31b-it:free", "OPENROUTER_API_KEY"),
    "groq": ("GROQ_MODEL", "openai/gpt-oss-120b", "GROQ_API_KEY"),
    "google": ("GOOGLE_MODEL", "gemini-3.8-flash", "GOOGLE_API_KEY"),
}


def provider_settings(provider: str | None = None) -> tuple[str, str, str | None]:
    """Return (provider, model, api_key_env_var) after applying .env settings."""
    provider = (provider or os.getenv("LLM_PROVIDER") or "ollama").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown LLM provider {provider!r}. Choose one of: {', '.join(PROVIDERS)}")
    model_var, default_model, key_var = PROVIDERS[provider]
    return provider, os.getenv(model_var) or default_model, key_var


def get_llm(provider: str | None = None, model: str | None = None, temperature: float = 0, **kwargs):
    """Build a LangChain chat model for the chosen provider.

    ``temperature`` defaults to 0 because the labs want repeatable answers.
    Extra keyword arguments are passed to the underlying LangChain class.
    """
    provider, default_model, key_var = provider_settings(provider)
    model = model or default_model
    if key_var and not os.getenv(key_var):
        raise RuntimeError(f"{key_var} is empty. Add your key to {LABS_ROOT / '.env'} (see .env.example).")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        kwargs.setdefault("num_ctx", int(os.getenv("OLLAMA_NUM_CTX") or 8192))
        # Cap the answer length so a model that fails to stop cannot hang a notebook.
        kwargs.setdefault("num_predict", int(os.getenv("OLLAMA_NUM_PREDICT") or 1024))
        # Thinking is off unless asked for: a small local model can spend minutes
        # reasoning before a one-line answer. Module 3 turns it on deliberately.
        think = (os.getenv("OLLAMA_THINK") or "false").strip().lower()
        if think in ("true", "false"):
            kwargs.setdefault("reasoning", think == "true")
        if os.getenv("OLLAMA_BASE_URL"):
            kwargs.setdefault("base_url", os.environ["OLLAMA_BASE_URL"])
        return ChatOllama(model=model, temperature=temperature, **kwargs)
    if provider == "openrouter":
        from langchain_openrouter import ChatOpenRouter

        return ChatOpenRouter(model=model, temperature=temperature, **kwargs)
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=model, temperature=temperature, **kwargs)
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model, temperature=temperature, **kwargs)


def release_model() -> list[str]:
    """Unload local models from RAM and return the names that were unloaded.

    Ollama keeps a model loaded between calls, and the RAM it holds grows as it
    is called with new prompts. Unloading gives all of that back; the next call
    reloads the model, which takes a few seconds. Does nothing when Ollama is
    not running or no model is loaded.
    """
    base = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=3) as response:
            loaded = [m["name"] for m in json.loads(response.read()).get("models", [])]
        for name in loaded:
            body = json.dumps({"model": name, "keep_alive": 0}).encode()
            request = urllib.request.Request(f"{base}/api/generate", data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(request, timeout=30).read()
        return loaded
    except (urllib.error.URLError, OSError, ValueError):
        return []
