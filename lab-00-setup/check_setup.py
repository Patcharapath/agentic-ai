"""Lab 0 - check that this machine is ready for the course.

Run from the repository folder (the one with ``pyproject.toml``):

    uv run python lab-00-setup/check_setup.py

It checks Python, the installed packages, your ``.env`` file, the local Ollama
model, and every API provider you have a key for. You pass when the Python
environment is fine and at least one LLM answers. API keys are never printed.
"""
from __future__ import annotations

import importlib.metadata as md
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LABS_ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ["langchain", "langgraph", "langchain-ollama", "langchain-openrouter", "langchain-groq", "langchain-google-genai"]
PROMPT = "Reply with exactly one word: ready"

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    mark = {"ok": "[ OK ]", "fail": "[FAIL]", "skip": "[SKIP]", "warn": "[WARN]"}[status]
    print(f"{mark} {name}" + (f" - {detail}" if detail else ""), flush=True)


def get_json(url: str, payload: dict | None = None, timeout: float = 10):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def short(err: Exception) -> str:
    return " ".join(str(err).split())[:220]


def check_python() -> bool:
    v = sys.version_info
    ok = (3, 11) <= (v.major, v.minor) < (3, 14)
    record("ok" if ok else "fail", "Python version", f"{v.major}.{v.minor}.{v.micro}" + ("" if ok else " (need 3.11-3.13; run with 'uv run')"))
    in_venv = sys.prefix != sys.base_prefix
    record("ok" if in_venv else "warn", "Virtual environment", sys.prefix if in_venv else "not in .venv; start this script with 'uv run python ...' (without uv: the .venv's own python)")
    return ok


def check_packages() -> bool:
    missing = []
    for p in PACKAGES:
        try:
            record("ok", f"Package {p}", md.version(p))
        except md.PackageNotFoundError:
            missing.append(p)
            record("fail", f"Package {p}", "not installed; run 'uv sync' in the repository folder (without uv: pip install -e .)")
    return not missing


def check_env_file() -> None:
    env = LABS_ROOT / ".env"
    if env.exists():
        record("ok", ".env file", str(env))
    else:
        record("warn", ".env file", "not found; copy .env.example to .env (defaults are used until you do)")


def try_llm(provider: str, model: str) -> bool:
    from agentlab import get_llm

    name = f"LLM call via {provider}"
    try:
        t0 = time.time()
        reply = get_llm(provider, model).invoke(PROMPT)
        text = reply.text if isinstance(getattr(reply, "text", None), str) else str(reply.content)
        usage = reply.usage_metadata or {}
        record("ok", name, f"{model} answered {text.strip()[:40]!r} in {time.time() - t0:.1f}s, {usage.get('total_tokens', '?')} tokens")
        return True
    except Exception as e:  # each provider raises its own error types
        record("fail", name, f"{model}: {short(e)}")
        return False


def check_ollama(model: str) -> bool:
    base = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    try:
        version = get_json(f"{base}/api/version").get("version", "?")
        record("ok", "Ollama server", f"version {version} at {base}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        record("fail", "Ollama server", f"not reachable at {base}; open the Ollama app ({short(e)})")
        return False
    names = [m.get("name", "") for m in get_json(f"{base}/api/tags").get("models", [])]
    if model not in names and f"{model}:latest" not in names:
        record("fail", "Ollama model", f"{model} is not downloaded; run 'ollama pull {model}' (you have: {', '.join(names) or 'none'})")
        return False
    record("ok", "Ollama model", f"{model} is downloaded")
    try:
        caps = get_json(f"{base}/api/show", {"model": model}).get("capabilities", [])
        if "tools" in caps:
            record("ok", "Ollama tool calling", f"{model} supports tools")
        else:
            record("warn", "Ollama tool calling", f"{model} does not support tools; it will not work as an agent from Lab 2 on")
    except (urllib.error.URLError, OSError, ValueError) as e:
        record("warn", "Ollama tool calling", f"could not read model capabilities ({short(e)})")
    return try_llm("ollama", model)


def check_openrouter_model(model: str) -> None:
    try:
        models = {m["id"]: m for m in get_json("https://openrouter.ai/api/v1/models", timeout=20).get("data", [])}
    except (urllib.error.URLError, OSError, ValueError) as e:
        record("warn", "OpenRouter model list", f"could not download it ({short(e)})")
        return
    if model not in models:
        record("fail", "OpenRouter model", f"{model} is not listed any more; pick a current free model and set OPENROUTER_MODEL in .env")
    elif "tools" not in models[model].get("supported_parameters", []):
        record("warn", "OpenRouter model", f"{model} does not support tools; it will not work as an agent from Lab 2 on")
    else:
        record("ok", "OpenRouter model", f"{model} is listed and supports tools")


def main() -> int:
    print("Agentic AI - Lab 0 setup check\n")
    sys.path.insert(0, str(LABS_ROOT))
    base_ok = check_python()
    base_ok = check_packages() and base_ok
    check_env_file()
    if not base_ok:
        print("\nFix the items marked [FAIL] above, then run this script again.")
        return 1

    from agentlab import PROVIDERS, provider_settings

    default_provider, _, _ = provider_settings()
    record("ok", "Default provider", f"LLM_PROVIDER={default_provider}")

    working = []
    for provider in PROVIDERS:
        _, model, key_var = provider_settings(provider)
        print()
        if provider == "ollama":
            if check_ollama(model):
                working.append(provider)
            continue
        if not os.getenv(key_var):
            record("skip", f"LLM call via {provider}", f"{key_var} is empty in .env")
            continue
        record("ok", f"{key_var}", "set")
        if provider == "openrouter":
            check_openrouter_model(model)
        if try_llm(provider, model):
            working.append(provider)

    print("\n" + "=" * 62)
    if working:
        print(f"READY - working LLM providers: {', '.join(working)}")
        if default_provider not in working:
            print(f"Note: LLM_PROVIDER={default_provider} is not working. Set it to one of the providers above in .env.")
        if len(working) == 1:
            print("Tip: set up a second provider as a backup for when one is slow or rate-limited.")
        return 0
    print("NOT READY - no LLM answered. Fix the [FAIL] items above (see the troubleshooting table in the Lab 0 guide).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
