# `inbox_app.py` explained, part by part

Read this after finishing the `lab1_inbox_agents` notebook, because `inbox_app.py` contains the answers to all its `# TODO` items. Keep `inbox_app.py` open next to it and read the two together.

The basics of a program run from a terminal (`parse_args()`, `main()`, `try` / `except`, stdout and stderr, exit codes) are covered in `lab-00-setup/hello_llm.en.md`. This document explains only what is new.

## 1. Overview: what moved over from the notebook and what was added

In the notebook you built several agents to compare them. The program has one agent that can work in 3 ways.

| In the notebook | In `inbox_app.py` | What changed |
|---|---|---|
| `RULES`, `matching_types()` | `RULES`, `matching_types()` | Nothing |
| `SYSTEM`, `FinancialDoc`, `to_iso_date()` | Same names | Nothing |
| `CautiousReflexAgent` | `--agent rules` | Folded into one mode of `InboxAgent` |
| `StatefulLLMAgent` | `--agent llm` | Folded into one mode of `InboxAgent` |
| `HybridAgent` | `--agent hybrid` | Folded into one mode of `InboxAgent` |
| `self.seen = set()` | The `State` class and `state.json` | **New:** state lives on disk |
| `act()` returns a string | The `Decision` class | **New:** the reason and details are recorded too |
| `env.run(agent)` | The loop in `main()` | **New:** reads files from a folder and saves after every document |
| `summarize(runs)` | `score()` | Same scoring, but only when an answer key exists |
| Displaying a DataFrame | `write_csv()` | **New:** results go to files other people can open |
| `print(...)` | `log.info(...)` | **New:** uses logging |

## 2. Why the additions: 3 problems a notebook never meets

1. **When the program ends, every variable is gone.** In the notebook `self.seen` stays in memory for as long as the notebook is open. A program starts from zero every time it runs. An invoice re-sent next week will not be caught unless the numbers already seen were saved to a file.
2. **Nobody is watching the screen.** In the notebook you look at the result under the cell. A real program may run overnight, and the person who has to check opens it later. So the result and reason for every decision have to be in a file.
3. **One document must not stop the whole batch.** In the notebook, if the LLM errors the cell breaks and you run it again. A program working through 300 documents cannot stop at number 17.

Nearly everything that was added is there to solve one of these three.

## 3. The added parts, one at a time

### 3.1 `REPO_ROOT`: finding folders from where the file is

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
```

`__file__` is the path of `inbox_app.py` itself. `.parent` is the folder it sits in (`lab-01-agent-foundations`), and `.parent` again is the `agentic-ai` folder.

This is needed because a path like `"data/inbox"` depends on which folder the terminal is in when you run the program. Run it from another folder and the path is not found. Working it out from the file's own location makes the defaults right every time.

### 3.2 `logging` in place of `print`

```python
log = logging.getLogger("inbox")
```

and in `main()`:

```python
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per HTTP call is too noisy here
```

`log.info(...)` works much like `print(...)`, but every message has a level (`INFO`, `WARNING`, `ERROR`), so we can choose which levels to show without deleting lines from the code.

The second line shows why that is useful. The library that calls the LLM (`httpx`) prints a line for every request it sends, which is too much clutter. We tell it to show only `WARNING` and above, without editing the library's code.

### 3.3 The `State` class: state that survives the program closing

```python
class State:
    """Decisions made so far and the invoice numbers already accepted, kept in a JSON file."""

    def __init__(self, path: Path):
        self.path = path
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.decisions: dict[str, dict] = data.get("decisions", {})
        self.invoice_numbers: dict[str, str] = data.get("invoice_numbers", {})  # number -> first doc_id

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"decisions": self.decisions, "invoice_numbers": self.invoice_numbers}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

This is the notebook's `self.seen = set()`, grown up. It keeps two things:

- `decisions`: the result for every document already done. It answers "has this one been done?"
- `invoice_numbers`: each invoice number received, paired with the ID of the first document that carried it. It answers "which document does this number duplicate?"

| Line | What it does |
|---|---|
| `json.loads(...) if path.exists() else {}` | If a file from an earlier run exists, read it back; if not, start empty |
| `data.get("decisions", {})` | Take the value out, using `{}` if the key is missing and not raising an error |
| `mkdir(parents=True, exist_ok=True)` | Create the destination folder if it is missing, without an error if it is already there |
| `ensure_ascii=False` | Write Thai as Thai, not as unreadable `ก` codes |
| `indent=2` | Indent the file so a person can read it |

We chose JSON because it opens in any editor and Python turns a dict into JSON in one line. A bigger system would use a database, which is a subject of Lab 2.

### 3.4 The `Decision` class: one record per document

```python
@dataclass
class Decision:
    doc_id: str
    action: str  # one of the six document types, or needs_human
    doc_type: str = ""
    doc_no: str = ""
    reason: str = ""
    decided_by: str = ""  # rules | llm
```

In the notebook `act()` returned a single string such as `"invoice"`. Someone checking later needs more than that: why was this decided, who decided it (rules or the LLM), and what is the document number?

`@dataclass` is a short way to make a class whose job is to hold data. We write only the field names and types, and Python generates `__init__` for us. A value after `=` is a default, so we can write `Decision(doc_id, "needs_human", reason="...")` without supplying every field.

In `main()` we use `asdict(decision)` to turn it into a dict, for storing in the JSON and writing as a CSV row.

### 3.5 `InboxAgent.read()`: who reads the document

```python
    def read(self, text: str) -> tuple[Reading | None, str]:
        """Return (reading, who decided). A reading of None means nobody could tell."""
        types = matching_types(text)
        sure = len(types) == 1
        # Rules handle the document alone only when they are sure. In hybrid mode an invoice
        # still goes to the LLM, which reads the number the duplicate check needs.
        if self.mode == "rules" or (self.mode == "hybrid" and sure and "invoice" not in types):
            if not sure:
                return None, "rules"
            number = DOC_NO.search(text)
            return Reading(doc_type=next(iter(types)), doc_no=number.group() if number else None), "rules"
        self.llm_calls += 1
        return self.llm.with_structured_output(Reading).invoke([("system", SYSTEM), ("user", text)]), "llm"
```

This function holds 3 of the notebook's agents in one place. The `if` decides whether the rules handle this document themselves:

| Mode | Rules handle it when | Otherwise |
|---|---|---|
| `rules` | Always | If the rules are unsure it returns `None`, which becomes `needs_human` |
| `hybrid` | Exactly one type matches and it is not an invoice | Goes to the LLM |
| `llm` | Never | Every document goes to the LLM |

The function returns two things at once: the reading, and who made it (`"rules"` or `"llm"`), which is recorded in the `Decision`. Knowing who decided helps a great deal when you have to find where a mistake came from.

### 3.6 `Reading`: ask for the shortest output that will do

```python
    doc_type: Literal["invoice", "receipt", "purchase_order", "contract", "leave_request", "other"]
    doc_no: str | None = Field(description="The document's own number, exactly as printed; null if it has none")
```

This schema is the notebook's `Routing`: just two fields. The first version of this program had a third field for the LLM to write its reason. A full run of 24 documents went from 82 to 135 seconds, because output tokens are the slow part (Module 0). So we removed it and let code write a short reason.

The lesson: every field you ask an LLM for has a price. Ask only for what you will use.

### 3.7 `InboxAgent.decide()`: one decision, with failure handling

**Part 1: if it cannot be read, send it to a person**

```python
        try:
            reading, decided_by = self.read(text)
        except Exception as error:  # a failed LLM call must not stop the whole run
            return Decision(doc_id, "needs_human", reason=f"could not read the document: {error}"[:200], decided_by="llm")
        if reading is None:
            return Decision(doc_id, "needs_human", reason="no single keyword rule matched", decided_by=decided_by)
```

This answers problem 3. When the LLM errors we do not let the program crash. We turn the error into the safest decision available, `needs_human`, and record the cause. `[:200]` trims the error text so it does not run on in the CSV.

**Part 2: check for a duplicate invoice**

```python
        if reading.doc_type == "invoice" and reading.doc_no:
            first = self.state.invoice_numbers.setdefault(reading.doc_no, doc_id)
            if first != doc_id:
                decision.action = "needs_human"
                decision.reason = f"invoice number {reading.doc_no} was already received in {first}"
```

In the notebook we wrote `if doc_no in self.seen` followed by `self.seen.add(doc_no)`. Here `setdefault` does both in one line:

- If the number is **not yet** in the dict, store it paired with the current `doc_id`, and return the current `doc_id`
- If the number **is already there**, return the `doc_id` of the first document that carried it, changing nothing

So `first != doc_id` means the number arrived before in a different document, and we know which one. We put that in the reason so the person checking can open both and compare.

**Part 3: extract the fields, without letting a failure undo the classification**

```python
        if self.llm is not None and reading.doc_type in FINANCIAL:
            try:
                for key, value in self.extract(text).items():
                    setattr(decision, key, value)
            except Exception as error:
                decision.reason += f" (fields not extracted: {error})"[:120]
```

Extraction is a second LLM call. If it fails, the classification that already succeeded is still good. So it gets its own `try`, and a failure is only noted in the reason.

`setattr(decision, key, value)` is the same as writing `decision.issue_date = ...`, `decision.total = ...` line by line, done in a loop.

### 3.8 `write_csv()`: results that open in Excel

```python
def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel shows Thai correctly
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
```

| What is written | Why |
|---|---|
| `encoding="utf-8-sig"` | Excel on Windows shows Thai as garbage in plain `utf-8`. `utf-8-sig` adds a marker at the start of the file telling Excel it is UTF-8 |
| `newline=""` | Stops blank lines appearing between rows on Windows |
| `with ... as f:` | Closes the file for us at the end, even after an error |
| `extrasaction="ignore"` | Each row has more fields than we want to write; skip those not in `columns` |

### 3.9 `main()`: the sequence of work

1. Read the arguments and set up logging
2. Check the folder given exists; if not, end with exit code 2
3. Load `State` from its file (deleting it first if `--reset` was given)
4. Find the documents not yet done
5. Do them one at a time, saving the state after each
6. Give the model's RAM back
7. Write `routing.csv` and `extracted.csv`
8. If there is an answer key, score the run

**Step 4: skip documents already done**

```python
    files = sorted(args.folder.glob("*.txt"))
    pending = [f for f in files if f.stem not in state.decisions]
    new = pending[: args.limit]
```

`glob("*.txt")` finds every `.txt` file in the folder. `f.stem` is the file name without its extension, such as `doc_01`, which we use as the document ID. The second line is why a second run makes no LLM calls: documents that already have a result in the state are filtered out.

**Steps 5 and 6: the main loop**

```python
    try:
        for file in new:
            decision = agent.decide(file.stem, file.read_text(encoding="utf-8"))
            state.decisions[decision.doc_id] = asdict(decision)
            state.save()  # after every document, so an interrupted run loses nothing
            log.info("%s  %-14s %s", decision.doc_id, decision.action, decision.reason)
    except KeyboardInterrupt:
        log.info("stopped; run again to continue where it left off")
    finally:
        release_model()
```

This loop does the job of `env.run(agent)` in the notebook, with three differences:

- `state.save()` is **inside** the loop, not after it. If the power fails at document 200, the first 199 are kept, and the next run carries on from 200
- `except KeyboardInterrupt` catches Ctrl+C, so the program ends cleanly and still writes the CSV for what it finished
- `finally: release_model()` gives the RAM back however the loop ends

**Step 8: score only when there is an answer key**

```python
    labels = args.folder.parent / f"{args.folder.name}_labels.csv"
    if labels.exists():
        log.info("against %s: %s", labels.name, score(state.decisions, labels))
```

In the lab we have the answer key `data/inbox_labels.csv`, but real documents come with no answers. So the program looks for a file named after the folder plus `_labels.csv`. If it is there it scores the run; if not it skips the step.

## 4. What `state.json` looks like

After one run, open `out/inbox/state.json` and you see this structure (cut down to two documents):

```json
{
  "decisions": {
    "doc_01": {
      "doc_id": "doc_01",
      "action": "invoice",
      "doc_type": "invoice",
      "doc_no": "INV-2026-0042",
      "reason": "classified by the LLM",
      "decided_by": "llm",
      "issue_date": "2026-10-01",
      "total": "5885.00",
      "currency": "THB",
      "seconds": 3.1
    },
    "doc_14": {
      "doc_id": "doc_14",
      "action": "needs_human",
      "doc_type": "invoice",
      "doc_no": "INV-2026-0042",
      "reason": "invoice number INV-2026-0042 was already received in doc_01",
      "decided_by": "llm",
      "issue_date": "2026-10-01",
      "total": "5885.00",
      "currency": "THB",
      "seconds": 2.8
    }
  },
  "invoice_numbers": {
    "INV-2026-0042": "doc_01"
  }
}
```

`doc_14` has `doc_type` `invoice` but `action` `needs_human`. The two can differ: `doc_type` is what the document is, and `action` is what the agent decided to do with it.

## 5. The parts that match the notebook

These moved over unchanged. If you finished the notebook you will recognise them at once: the `RULES` list, `DOC_NO`, the `SYSTEM` text, the `FinancialDoc` schema, the `MONTHS` table, and the functions `to_iso_date()` and `matching_types()`.

## 6. Try changing it yourself

1. Add a document type `quotation`. How many places do you have to change? Go through them: `RULES`, `SYSTEM`, `Reading`. Then run with `--reset` and see how `doc_23` is handled.
2. Add a `--verbose` option that sets the logging level to `DEBUG`, then add a `log.debug(...)` in `read()` that says which rule matched.
3. At present only invoices are checked for duplicates. Extend that to receipts and purchase orders. Do you need to rename `invoice_numbers`, and will state saved by the old version still work?
4. Make a new folder with 3–4 `.txt` files of your own and run `uv run python lab-01-agent-foundations/inbox_app.py your_folder --out out/mine`.

## 7. Glossary

| Term | Meaning |
|---|---|
| State | Data a program has to remember across steps or across runs |
| Persist | To store data on disk so it survives the program ending |
| JSON | A text file format for dicts and lists, readable by people and programs |
| CSV | A table file with values separated by commas. Opens in Excel |
| Dataclass | A class whose job is to hold data, made with `@dataclass` |
| Logging | Printing messages that carry a level, so they can be switched on and off without editing code |
| Idempotent | Giving the same result however many times it is run. This program skips documents already done, so re-running is safe |
| Fallback | What you do when the main way fails. Here, sending the document to a person |
