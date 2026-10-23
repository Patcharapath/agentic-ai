# `invoice_agent.py` explained, part by part

Read this after finishing the `lab2_tool_agent` notebook, because `invoice_agent.py` contains the answers to its `# TODO` items. Keep `invoice_agent.py` open next to it and read the two together.

Things explained in earlier labs are not repeated here:

- `parse_args()`, `main()`, `try` / `except`, stdout and stderr, exit codes: see `lab-00-setup/hello_llm.en.md`
- State saved to a file, logging, writing CSV, skipping work already done: see `lab-01-agent-foundations/inbox_app.en.md`

## 1. Overview: what moved over from the notebook and what was added

| In the notebook | In `invoice_agent.py` | What changed |
|---|---|---|
| The 4 tools from `agentlab.invoices` | The same | Nothing |
| `run_tool()` from part 5.2 | `run_tool()` | Nothing |
| `run_agent()` from part 3 | `Checker.run_agent()` | **Added:** stops when the model repeats itself, and writes a trace |
| `check_with_workflow()` from part 6.2 | `Checker.run_workflow()` | Nothing |
| `show_trace()` prints to the screen | `Checker.trace()` writes to a file | **New:** the trace lives on disk |
| Trusting that the agent saved a result | `Checker.check()` looks in the database | **New:** records `needs_review` if nothing was saved |
| `create_database(reset=True)` every time | Skips invoices already checked; wipes only with `--reset` | **New:** can carry on where it stopped |
| `evaluate_checks()` | `score()` | Same scoring, when an answer key exists |

## 2. Why the additions: 3 problems of an agent loop running for real

1. **A loop without limits may never end.** A confused model can call the same tool with the same arguments again and again. In the notebook you can press Interrupt; nobody presses anything for a program running overnight.
2. **An agent saying it is done does not mean it is done.** The model may reply "I rejected this invoice" without ever calling `record_result` (the lecture showed the first version of the tools causing exactly that for half the invoices). If the program believed the answer, that invoice would vanish from the system without anyone knowing.
3. **A wrong result has to be traceable.** When an accountant asks "why was this one rejected?", the answer has to be in a file, not on a screen that has since been closed.

## 3. The added parts, one at a time

### 3.1 Pointing the shared tools at this run's folder and database

```python
    # Point the shared tools at this run's folder and database.
    invoices.INVOICE_DIR = args.folder.resolve()
    invoices.DB_PATH = args.out / "procurement.db"
    invoices.create_database(reset=args.reset)
```

The tools in `agentlab/invoices.py` read the module's `INVOICE_DIR` and `DB_PATH` every time they are called; they do not remember the values from import time. So the program can change both before starting, and every tool immediately uses the new folder and database, without touching the tools' code.

That is why the top of the file says `from agentlab import invoices` (the whole module) and does not import the variables themselves. With `from agentlab.invoices import DB_PATH` we would get a copy of the value, and changing the copy would have no effect on the tools.

### 3.2 `run_tool()`: a failing tool must not break the loop

```python
def run_tool(call: dict, tools_by_name: dict) -> str:
    """Run one tool call. Problems become a message for the model instead of a crash."""
    tool = tools_by_name.get(call["name"])
    if tool is None:
        return json.dumps({"error": f"There is no tool called {call['name']}. Available tools: {sorted(tools_by_name)}"})
    try:
        return tool.invoke(call["args"])
    except Exception as error:
        return json.dumps({"error": f"{type(error).__name__}: {error}"})
```

This is the answer to part 5.2 of the notebook, moved over as it was. The key point is that an error becomes **data sent back to the model**, not something that stops the program. The model then has a chance to recover: told there is no tool by that name, it sees the list of tools that do exist and can choose again.

`tools_by_name.get(...)` returns `None` for a missing key, where `tools_by_name[...]` would raise `KeyError`.

### 3.3 `Checker.trace()`: recording every event in a file

```python
    def trace(self, filename: str, kind: str, **data) -> None:
        """Append one event to the trace file, and print it with --trace."""
        event = {"time": datetime.now().isoformat(timespec="seconds"), "file": filename, "event": kind, **data}
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

`traces.jsonl` is in **JSON Lines** format: each line is one complete JSON object, unlike ordinary JSON where the whole file is one object. The advantages:

- You can keep appending with mode `"a"` (append) without reading the existing file
- If the program stops midway, every line already written is still complete and readable
- pandas reads it back in one line: `pd.read_json("out/traces.jsonl", lines=True)`

`**data` accepts any number of named arguments, such as `self.trace(filename, "call", tool=..., args=..., result=...)`, and `**data` again merges them into the event dict.

### 3.4 `Checker.run_agent()`: a loop with limits

```python
        seen_calls = set()
        for _ in range(self.max_steps):
            reply = self.model.invoke(messages)
            self.llm_calls += 1
            messages.append(reply)
            if not reply.tool_calls:
                self.trace(filename, "answer", text=reply.text)
                return reply.text
            for call in reply.tool_calls:
                key = (call["name"], json.dumps(call["args"], sort_keys=True))
                if key in seen_calls:  # the same call again means the model is going round in circles
                    self.trace(filename, "stop", reason=f"repeated call to {call['name']}")
                    return "stopped: repeated tool call"
                seen_calls.add(key)
```

The shape is the notebook's `run_agent`, line for line, with two layers of limit added:

| Limit | What it prevents |
|---|---|
| `for _ in range(self.max_steps)` | The loop running past a set number of rounds, whatever the reason |
| `seen_calls` | Carrying on when the model repeats the same tool call with the same arguments, which almost always means it is lost |

Why the key uses `json.dumps(call["args"], sort_keys=True)`: the arguments are a dict, and a dict cannot go in a `set` (dicts can change, so Python does not allow them as set members). So we turn them into text first, and `sort_keys=True` makes `{"a": 1, "b": 2}` and `{"b": 2, "a": 1}` give the same text.

### 3.5 `Checker.check()`: the job is not done until the result is saved

```python
    def check(self, filename: str) -> str:
        answer = self.run_agent(filename) if self.mode == "agent" else self.run_workflow(filename)
        if verdict_for(filename) is None:  # the job is not done until a verdict is saved
            save_needs_review(filename, f"agent finished without saving a verdict ({answer[:80]})")
        return answer
```

This answers problem 2. After the agent finishes, the program **checks the real world** (the database) instead of believing the model's reply. If no result is in the database, the agent never called `record_result`, or was stopped first, so the program records `needs_review` for a person to see and follow up.

The principle applies to every agent: check the effect of the action that had to happen, not the words the agent said.

### 3.6 SQL and the `?` placeholder

```python
def verdict_for(filename: str) -> dict | None:
    rows = invoices.query("SELECT * FROM invoice_checks WHERE file = ?", (filename,))
    return rows[0] if rows else None
```

Values that come from outside (file names, text from the model) must always go into SQL through a `?` placeholder. Never build the command as text with an f-string like `f"... WHERE file = '{filename}'"`: if the file name contained a `'`, the SQL would change its meaning, which is called SQL injection. `(filename,)` with the trailing comma is a one-element tuple.

### 3.7 `Checker.run_workflow()` and `--mode`

The same code as part 6.2 of the notebook, moved into the same class as the agent so the two can be compared with one command:

```bash
uv run python lab-02-tool-use/invoice_agent.py --reset
uv run python lab-02-tool-use/invoice_agent.py --reset --mode workflow
```

`__init__` creates the model only in agent mode:

```python
        self.model = get_llm().bind_tools(TOOLS) if mode == "agent" else None
```

So workflow mode runs even with Ollama switched off.

## 4. What `traces.jsonl` looks like

After a run, each line of the file is one event (shortened here):

```json
{"time": "2026-10-23T20:03:49", "file": "inv_03.pdf", "event": "call", "tool": "check_invoice_total", "args": {"filename": "inv_03.pdf"}, "result": "{\"subtotal\": 48750.0, ... \"total_ok\": true}"}
{"time": "2026-10-23T20:03:49", "file": "inv_03.pdf", "event": "call", "tool": "compare_with_po", "args": {"filename": "inv_03.pdf"}, "result": "{\"po_number\": \"PO-2026-121\", \"matches_po\": false, ...}"}
{"time": "2026-10-23T20:03:52", "file": "inv_03.pdf", "event": "call", "tool": "record_result", "args": {"filename": "inv_03.pdf", "verdict": "reject", "reason": "unit_price"}, "result": "{\"saved\": true, ...}"}
{"time": "2026-10-23T20:03:54", "file": "inv_03.pdf", "event": "answer", "text": "inv_03.pdf: reject unit_price"}
```

The first two lines have the same time because the model asked for two tools at once in a single reply (parallel tool calls).

## 5. The parts that match the notebook

The 4 tools, `SYSTEM_PROMPT`, `run_tool()`, the shape of the agent loop and the workflow's rules moved over unchanged.

## 6. Try changing it yourself

1. Add a `--provider` option passed on to `get_llm()`, and run with an API you have a key for. Compare time and results with the local model.
2. At present `seen_calls` stops at the first repeat. Change it to allow one repeat and stop at the second.
3. Add an `llm_calls` column to `invoice_checks.csv` so you can see how many LLM calls each invoice used (you need to count per invoice).
4. Read `out/traces.jsonl` with pandas and count how many times each tool was called.

## 7. Glossary

| Term | Meaning |
|---|---|
| Trace | A record of the sequence of events in one run: every LLM call and tool call |
| JSON Lines (`.jsonl`) | A file where each line is one JSON object, so you can keep appending |
| Side effect | Something a tool leaves behind in the real world, such as a database record |
| Verification | Checking that the intended effect really happened, instead of trusting the agent's word |
| Max steps | The limit on the number of rounds of the agent loop |
| Loop detection | Noticing that an agent is doing the same thing over and over |
| SQL injection | An attack that slips special text into an SQL command to change its meaning; prevented with `?` |
| Module attribute | A module-level variable such as `invoices.DB_PATH`, which can be changed from outside |
