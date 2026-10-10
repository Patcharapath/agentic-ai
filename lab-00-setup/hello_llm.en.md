# `hello_llm.py` explained, part by part

This is written for people who have written Python in notebooks but have not yet written a program that runs from a terminal. Keep `hello_llm.py` open next to it and read the two together.

In the notebook `hello_llm.en.ipynb`, the code that calls the LLM is two lines:

```python notebook
llm = get_llm()
reply = llm.invoke("อธิบายคำว่า token ในบริบทของ LLM ภายใน 2 ประโยค")
```

`hello_llm.py` does the same thing in about 80 lines. This document explains what the extra lines are for.

## 1. How a notebook and a program differ

| | Notebook | `.py` program |
|---|---|---|
| How it runs | You run one cell at a time | One command in a terminal runs the whole file, top to bottom |
| How you change the question | Edit the code in a cell | Pass a value when you call it; the file stays as it is |
| Where results go | Shown under the cell | Printed to the screen, or written to a file |
| When an error happens | You see a traceback and fix that cell | The program must say what went wrong itself, because the person running it may not be the author |
| Who uses it | Only you | You, a colleague, or another program |
| Variables between runs | Stay in memory until you close the notebook | Gone every time the program ends |

The last row matters most, and it is why Lab 1 has to save its state to a file.

## 2. A map of the file

| Part | What it does | In the notebook? |
|---|---|---|
| The text in `"""..."""` at the top | Says what the file is and how to run it | No |
| `import ...` | Brings in the tools used | Partly |
| `SYSTEM = ...` | The instruction given to the model every time | Yes (inside a cell) |
| `parse_args()` | Reads the values typed after the command in the terminal | No |
| `build_messages()` | Assembles the messages sent to the model | Yes (written inline in a cell) |
| `main()` | The whole sequence of work | No (a notebook uses cell order) |
| `if __name__ == "__main__":` | Where execution starts when the file is run | No |

## 3. The added parts, one at a time

### 3.1 The text at the top of the file (docstring)

The text in `"""..."""` on the first line is called a docstring. Python does not run it; it is for people. Someone opening the file for the first time should know within 10 seconds what it does and how to run it, so the example commands go here.

### 3.2 Imports at the top

```python
import argparse
import sys
import time
from pathlib import Path

from agentlab import PROVIDERS, get_llm, provider_settings, release_model
```

In a notebook we often `import` in the cell that needs it. In a program they all go at the top, so a reader sees at once what the file depends on.

| Import | Comes from | Used here for |
|---|---|---|
| `argparse` | Ships with Python | Reading values from the command line |
| `sys` | Ships with Python | Printing to stderr and returning an exit code |
| `time` | Ships with Python | Timing |
| `Path` | Ships with Python | Handling file paths the same way on macOS and Windows |
| `get_llm` and the others | The course's `agentlab` folder | Building an LLM from the settings in `.env` |

The first group ships with Python; the second is our own code. A blank line separates them.

### 3.3 Constants are written in capitals

```python
SYSTEM = "You are a concise assistant for office document work. Answer in the language of the question."
```

An all-capitals name is the Python convention for "this value does not change while the program runs". It sits at the top so it can be found and changed in one place.

### 3.4 `parse_args()`: taking values from the terminal

This is what saves you from editing code every time the question changes. When you type

```bash
uv run python lab-00-setup/hello_llm.py --file data/inbox/doc_01.txt "What is the total?"
```

everything after the file name is called an argument. This function reads those arguments and returns them as an easy-to-use object.

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask an LLM one question, optionally about a text file.")
    parser.add_argument("question", help="the question to ask")
    parser.add_argument("--file", type=Path, help="a text file to give the model as context")
    parser.add_argument("--out", type=Path, help="also save the answer to this file (UTF-8)")
    parser.add_argument("--provider", choices=list(PROVIDERS), help="override LLM_PROVIDER from .env")
    parser.add_argument("--temperature", type=float, default=0.0, help="0 = repeatable (default), higher = more varied")
    parser.add_argument("--keep-loaded", action="store_true", help="leave the local model in RAM afterwards")
    return parser.parse_args(argv)
```

Line by line:

| What is written | Meaning |
|---|---|
| `"question"` (no `--`) | An argument that is **required**, given without typing its name |
| `"--file"` (with `--`) | An option that is **optional**, given with its name in front |
| `type=Path`, `type=float` | Converts the typed text to the type wanted. If it cannot, the program reports the error for you |
| `default=0.0` | The value used when the option is left out |
| `choices=[...]` | Accepts only the listed values. A typo is rejected with the valid values shown |
| `action="store_true"` | An on/off switch with no value after it. Present means `True` |
| `help="..."` | The description shown when you run with `--help` |

After that the values are available as `args.question`, `args.file`, `args.temperature`. `--keep-loaded` becomes `args.keep_loaded`, because a Python variable name cannot contain a hyphen.

Try `uv run python lab-00-setup/hello_llm.py --help`. The whole help text is generated from these lines; we did not write it.

### 3.5 `build_messages()`: putting a job in a function

```python
def build_messages(question: str, file: Path | None) -> list[tuple[str, str]]:
    """The model sees only what we put here: instructions, the document if any, then the question."""
    if file is None:
        return [("system", SYSTEM), ("user", question)]
    document = file.read_text(encoding="utf-8")
    return [("system", SYSTEM), ("user", f"<document>\n{document}\n</document>\n\n{question}")]
```

In the notebook we wrote the message list straight into a cell. In a program we make it a function for three reasons: the job gets a name, it can be tested by itself, and it can be called again from elsewhere.

Two things to notice:

- `encoding="utf-8"` must always be given when reading a file containing Thai. Without it Windows uses another encoding and reads the Thai wrongly.
- The document is wrapped in `<document>...</document>` so the model can tell which part is the document and which is the question. This is the context window from Module 0: the model sees only what this function assembles.

### 3.6 `main()`: the whole sequence of work

In a notebook the sequence of work is the order of the cells. In a program we put it in one function called `main()`. Read it top to bottom and you see the whole story, in 5 stages.

**Stage 1: check the input before doing anything slow**

```python
    if args.file is not None and not args.file.is_file():
        print(f"error: {args.file} is not a file", file=sys.stderr)
        return 2
```

If the path is wrong, say so at once and stop, without waiting for the model to load first. The principle: check whatever can be checked quickly, first.

**Stage 2: print supporting information to stderr**

```python
    provider, model, _ = provider_settings(args.provider)
    print(f"[{provider} / {model}]", file=sys.stderr)
```

A program has two channels to print on: **stdout** for results, and **stderr** for supporting messages and errors. On screen the two are mixed together, but another program that uses the result reads only stdout. So the model name, timing and token counts go to stderr with `file=sys.stderr`, and the model's answer goes to stdout.

**Stage 3: call the LLM inside `try` / `except` / `finally`**

```python
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
```

| Part | When it runs | What it is for here |
|---|---|---|
| `try:` | Always | The work that may fail: calling the LLM |
| `except Exception as error:` | When an error happens inside `try` | Print the cause as a short message and end with exit code 1 |
| `finally:` | Always, on success or failure | Give the model's RAM back |

An LLM call can fail in many ways: Ollama is not running, there is no API key, the quota is used up, or the network drops. In a notebook you see a long traceback and fix it yourself. In a program the person running it should see one sentence saying what happened.

Inside the loop there are two things:

- `print(chunk.text, end="", flush=True)` prints each piece at once, without starting a new line (`end=""`) and without waiting for the buffer to fill (`flush=True`), so the answer streams onto the screen.
- `answer = ... answer + chunk` adds the pieces into a single message, because the token counts live on the combined message.

**Stage 4: save to a file if asked**

```python
    if args.out is not None and answer is not None:
        args.out.write_text(answer.text + "\n", encoding="utf-8")
        print(f"[saved to {args.out}]", file=sys.stderr)
```

**Stage 5: report timing and tokens, then end with `return 0`**

### 3.7 The last two lines

```python
if __name__ == "__main__":
    sys.exit(main())
```

These two lines close almost every Python program. They mean "if this file is being run directly, call `main()` and hand its return value back as the exit code".

The `if` is there so another file can `import` functions from this one without `main()` running as a side effect.

### 3.8 Type hints

```python
def main(argv: list[str] | None = None) -> int:
```

The parts `: list[str] | None` and `-> int` are type hints. They say what type a function takes and returns. Python does not enforce them, but the editor uses them to warn when you pass the wrong type, and a reader understands the function without reading its body.

`argv` is there to make testing easy: other code can call `main(["a question", "--temperature", "0.5"])` without opening a terminal. When nothing is passed, the program reads from the terminal as usual.

## 4. Exit codes

When a program ends it hands one number back to the terminal, called the exit code. Other programs use that number to decide whether to carry on or stop.

| Exit code | Meaning in this file |
|---|---|
| 0 | Success |
| 1 | The LLM call failed |
| 2 | A bad argument, such as `--file` pointing at a file that does not exist |

See the exit code of the last command with `echo $?` (macOS) or `echo $LASTEXITCODE` (PowerShell).

## 5. Try changing it yourself

1. Add a `--system` option so the user can change the system text from the terminal, with `SYSTEM` as the default. You change one line in `parse_args()` and pass the value on to `build_messages()`.
2. Run with `--file` pointing at a file that does not exist and look at the exit code. Then quit Ollama and run again. How do the exit codes differ?
3. Remove `flush=True` from the `print` inside the loop and run it. How does the answer appear on screen now?

## 6. Glossary

| Term | Meaning |
|---|---|
| Terminal | A window for typing commands. In the editor, open it from the Terminal menu |
| Argument | A value typed after the program name when calling it |
| Option / flag | An argument that starts with `--` and may be left out |
| stdout / stderr | A program's output channels: one for results, one for supporting messages and errors |
| Exit code | The number a program returns when it ends. 0 means success |
| Exception | An error raised while running. Caught with `try` / `except` |
| Docstring | The explanatory text in `"""..."""` at the top of a file or function |
| Type hint | A statement of the types a function takes and returns |
