"""Lab 0 - ask an LLM from the command line.

The notebook next to this file explains the ideas one cell at a time. This is
the same thing written as a program you can run for real:

    uv run python lab-00-setup/hello_llm.py "ใบกำกับภาษีต่างจากใบเสร็จรับเงินอย่างไร"
    uv run python lab-00-setup/hello_llm.py --file data/inbox/doc_01.txt "ยอดรวมเท่าไร และครบกำหนดชำระเมื่อไร"
    uv run python lab-00-setup/hello_llm.py --provider openrouter --temperature 0.7 "Name a coffee shop"

The answer goes to standard output, so it can be saved or piped. Timing and
token counts go to standard error and stay out of the saved answer.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from agentlab import PROVIDERS, get_llm, provider_settings, release_model

SYSTEM = "You are a concise assistant for office document work. Answer in the language of the question."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask an LLM one question, optionally about a text file.")
    parser.add_argument("question", help="the question to ask")
    parser.add_argument("--file", type=Path, help="a text file to give the model as context")
    parser.add_argument("--provider", choices=list(PROVIDERS), help="override LLM_PROVIDER from .env")
    parser.add_argument("--temperature", type=float, default=0.0, help="0 = repeatable (default), higher = more varied")
    parser.add_argument("--keep-loaded", action="store_true", help="leave the local model in RAM afterwards")
    return parser.parse_args(argv)


def build_messages(question: str, file: Path | None) -> list[tuple[str, str]]:
    """The model sees only what we put here: instructions, the document if any, then the question."""
    if file is None:
        return [("system", SYSTEM), ("user", question)]
    document = file.read_text(encoding="utf-8")
    return [("system", SYSTEM), ("user", f"<document>\n{document}\n</document>\n\n{question}")]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.file is not None and not args.file.is_file():
        print(f"error: {args.file} is not a file", file=sys.stderr)
        return 2

    provider, model, _ = provider_settings(args.provider)
    print(f"[{provider} / {model}]", file=sys.stderr)
    try:
        llm = get_llm(provider, temperature=args.temperature)
        started = time.time()
        answer = None
        for chunk in llm.stream(build_messages(args.question, args.file)):
            print(chunk.text, end="", flush=True)
            answer = chunk if answer is None else answer + chunk  # chunks add up to the full message
        print(flush=True)
    except Exception as error:  # each provider raises its own error types
        print(f"\nerror: the LLM call failed: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_loaded:
            release_model()

    usage = (answer.usage_metadata or {}) if answer is not None else {}
    print(
        f"[{time.time() - started:.1f}s, {usage.get('input_tokens', '?')} input + {usage.get('output_tokens', '?')} output tokens]",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
