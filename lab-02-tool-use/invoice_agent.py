"""Lab 2 - the invoice-checking agent as a program.

The notebook builds the agent loop step by step. This file is the result written
the way you would run it for real: it checks every invoice PDF in a folder
against the purchase orders, saves each verdict to the database, and writes a
CSV and a trace of every tool call.

    uv run python lab-02-tool-use/invoice_agent.py                       # check data/invoices
    uv run python lab-02-tool-use/invoice_agent.py --trace               # show every tool call
    uv run python lab-02-tool-use/invoice_agent.py --mode workflow       # same checks, fixed order, no LLM
    uv run python lab-02-tool-use/invoice_agent.py --reset               # forget earlier verdicts

What a program needs that the notebook did not:

- Limits. The loop stops after --max-steps model calls, and stops early if the
  model repeats the same tool call, so a confused model cannot run forever.
- A check that the job was done. If the agent finishes without saving a verdict,
  the program records "needs_review" so nothing slips through silently.
- A trace on disk. Every tool call and result goes to out/traces.jsonl, so a wrong
  verdict can be investigated afterwards.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agentlab import get_llm, release_model
from agentlab import invoices
from agentlab.invoices import SYSTEM_PROMPT, TOOLS, check_invoice_total, compare_with_po, record_result

log = logging.getLogger("invoice_agent")
REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- running one tool safely
def run_tool(call: dict, tools_by_name: dict) -> str:
    """Run one tool call. Problems become a message for the model instead of a crash."""
    tool = tools_by_name.get(call["name"])
    if tool is None:
        return json.dumps({"error": f"There is no tool called {call['name']}. Available tools: {sorted(tools_by_name)}"})
    try:
        return tool.invoke(call["args"])
    except Exception as error:
        return json.dumps({"error": f"{type(error).__name__}: {error}"})


# ---------------------------------------------------------------- the two ways to check an invoice
class Checker:
    def __init__(self, mode: str, max_steps: int, trace_path: Path, show_trace: bool):
        self.mode, self.max_steps = mode, max_steps
        self.trace_path, self.show_trace = trace_path, show_trace
        self.model = get_llm().bind_tools(TOOLS) if mode == "agent" else None
        self.tools_by_name = {t.name: t for t in TOOLS}
        self.llm_calls = 0

    def trace(self, filename: str, kind: str, **data) -> None:
        """Append one event to the trace file, and print it with --trace."""
        event = {"time": datetime.now().isoformat(timespec="seconds"), "file": filename, "event": kind, **data}
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        if self.show_trace:
            detail = json.dumps({k: v for k, v in data.items()}, ensure_ascii=False)
            log.info("    %-6s %s", kind, detail[:150])

    def run_agent(self, filename: str) -> str:
        """The agent loop from the notebook, with limits and a trace. Returns the model's last answer."""
        messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(f"Check invoice {filename}.")]
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
                result = run_tool(call, self.tools_by_name)
                self.trace(filename, "call", tool=call["name"], args=call["args"], result=result[:300])
                messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
        self.trace(filename, "stop", reason=f"max_steps ({self.max_steps}) reached")
        return "stopped: max_steps reached"

    def run_workflow(self, filename: str) -> str:
        """The same tools in a fixed order, decided by rules. No LLM."""
        total = json.loads(check_invoice_total.invoke({"filename": filename}))
        po = json.loads(compare_with_po.invoke({"filename": filename}))
        if "error" in total or not total["total_ok"]:
            verdict, reason = "reject", "total"
        elif "error" in po:
            verdict, reason = "reject", "no_po" if "no PO number" in po["error"] else "po_not_found"
        elif not po["matches_po"]:
            verdict, reason = "reject", "unit_price" if "unit price" in " ".join(po["problems"]) else "quantity"
        else:
            verdict, reason = "approve", "all checks passed"
        record_result.invoke({"filename": filename, "verdict": verdict, "reason": reason})
        self.trace(filename, "rules", verdict=verdict, reason=reason)
        return f"{verdict}: {reason}"

    def check(self, filename: str) -> str:
        answer = self.run_agent(filename) if self.mode == "agent" else self.run_workflow(filename)
        if verdict_for(filename) is None:  # the job is not done until a verdict is saved
            save_needs_review(filename, f"agent finished without saving a verdict ({answer[:80]})")
        return answer


# ---------------------------------------------------------------- the database
def verdict_for(filename: str) -> dict | None:
    rows = invoices.query("SELECT * FROM invoice_checks WHERE file = ?", (filename,))
    return rows[0] if rows else None


def save_needs_review(filename: str, reason: str) -> None:
    with sqlite3.connect(invoices.create_database()) as db:
        db.execute("INSERT OR REPLACE INTO invoice_checks VALUES (?, ?, ?, ?, ?)",
                   (Path(filename).stem, filename, "needs_review", reason, datetime.now().isoformat(timespec="seconds")))


def score(rows: list[dict], labels_path: Path) -> str:
    with labels_path.open(encoding="utf-8") as f:
        expected = {r["file"]: r for r in csv.DictReader(f)}
    right = sum(1 for r in rows if r["file"] in expected and r["verdict"] == expected[r["file"]]["expected_verdict"]
                and (expected[r["file"]]["issue"] == "none" or expected[r["file"]]["issue"] in r["reason"]))
    return f"{right} of {sum(r['file'] in expected for r in rows)} correct (verdict and reason)"


# ---------------------------------------------------------------- command line
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check invoice PDFs against purchase orders with a tool-using agent.")
    parser.add_argument("folder", nargs="?", type=Path, default=REPO_ROOT / "data" / "invoices", help="folder of invoice PDFs (default: data/invoices)")
    parser.add_argument("--mode", choices=["agent", "workflow"], default="agent", help="agent (default): the LLM chooses the tools; workflow: fixed order, no LLM")
    parser.add_argument("--max-steps", type=int, default=8, help="most model calls per invoice (default: 8)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "out", help="folder for the database, CSV and trace (default: out)")
    parser.add_argument("--limit", type=int, help="check at most this many new invoices")
    parser.add_argument("--trace", action="store_true", help="print every tool call as it happens")
    parser.add_argument("--reset", action="store_true", help="start from a fresh database, forgetting earlier verdicts")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not args.folder.is_dir():
        log.error("error: %s is not a folder", args.folder)
        return 2

    # Point the shared tools at this run's folder and database.
    invoices.INVOICE_DIR = args.folder.resolve()
    invoices.DB_PATH = args.out / "procurement.db"
    invoices.create_database(reset=args.reset)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.reset:
        (args.out / "traces.jsonl").unlink(missing_ok=True)

    files = sorted(p.name for p in args.folder.glob("*.pdf"))
    pending = [f for f in files if verdict_for(f) is None]
    todo = pending[: args.limit]
    log.info("%d invoices in %s, %d already checked, %d to check now (mode: %s)",
             len(files), args.folder, len(files) - len(pending), len(todo), args.mode)

    try:
        checker = Checker(args.mode, args.max_steps, args.out / "traces.jsonl", args.trace)
    except Exception as error:
        log.error("error: could not start the LLM: %s", error)
        return 1
    started = time.time()
    try:
        for filename in todo:
            t = time.time()
            checker.check(filename)
            row = verdict_for(filename)
            log.info("%s  %-12s %-12s %s  (%.1fs)", filename, row["invoice_no"], row["verdict"], row["reason"][:60], time.time() - t)
    except KeyboardInterrupt:
        log.info("stopped; run again to continue where it left off")
    finally:
        release_model()

    rows = invoices.recorded_checks()
    with (args.out / "invoice_checks.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "invoice_no", "verdict", "reason", "checked_at"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("\n%d LLM calls, %.0fs. Wrote %s and traces.jsonl", checker.llm_calls, time.time() - started, args.out / "invoice_checks.csv")

    labels = args.folder.parent / f"{args.folder.name}_labels.csv"
    if labels.exists():
        log.info("against %s: %s", labels.name, score(rows, labels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
