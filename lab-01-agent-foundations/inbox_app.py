"""Lab 1 - the inbox agent as a program.

The notebook builds four agents step by step to explain the ideas. This file
is the result written the way you would run it for real: point it at a folder
of documents and it routes each one, extracts the fields of financial
documents, and writes its decisions to files.

    uv run python lab-01-agent-foundations/inbox_app.py                    # process data/inbox
    uv run python lab-01-agent-foundations/inbox_app.py --agent hybrid     # rules first, LLM when unsure
    uv run python lab-01-agent-foundations/inbox_app.py my_folder --out out/my-run
    uv run python lab-01-agent-foundations/inbox_app.py --reset            # forget earlier runs

What a program needs that the notebook did not:

- State on disk. The invoice numbers seen so far survive a restart, so a
  duplicate is caught even when it arrives next week.
- A record of every decision and its reason, for the person who has to check.
- Failure handling. A document the LLM cannot process goes to a person
  instead of stopping the run.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from agentlab import get_llm, release_model

log = logging.getLogger("inbox")
REPO_ROOT = Path(__file__).resolve().parent.parent
FINANCIAL = {"invoice", "receipt", "purchase_order"}
REWARDS = {"correct": 1, "abstain": 0, "wrong": -1}

# ---------------------------------------------------------------- reading a document
RULES = [
    ("ใบแจ้งหนี้", "invoice"), ("invoice", "invoice"),
    ("ใบเสร็จ", "receipt"), ("receipt", "receipt"),
    ("ใบสั่งซื้อ", "purchase_order"), ("purchase order", "purchase_order"),
    ("สัญญา", "contract"), ("agreement", "contract"),
    ("ขอลา", "leave_request"), ("leave", "leave_request"),
]
DOC_NO = re.compile(r"\b[A-Z]{2,3}-\d[\d-]*\b")

SYSTEM = """You sort incoming business documents. Choose the type that says what the document IS, not what it mentions.
- invoice: a seller asks a buyer to pay for goods or services
- receipt: confirms that a payment has already been received
- purchase_order: a buyer orders goods or services from a seller
- contract: a signed agreement or an amendment to one
- leave_request: an employee asks for time off
- other: anything else, such as memos, announcements, minutes, quotations"""


class Reading(BaseModel):
    """What the LLM reports about one document.

    Two short fields and no free-text explanation: output tokens are the slow part,
    and asking for a written reason made every document take three times as long.
    """

    doc_type: Literal["invoice", "receipt", "purchase_order", "contract", "leave_request", "other"]
    doc_no: str | None = Field(description="The document's own number, exactly as printed; null if it has none")


class FinancialDoc(BaseModel):
    doc_no: str = Field(description="The document's own number, exactly as printed")
    issue_date_text: str | None = Field(description="The date the document was issued, copied exactly as printed; null if it has none")
    total: float = Field(description="Final total amount including VAT")
    currency: Literal["THB", "USD", "EUR"]


MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
MONTHS.update({m: i for i, m in enumerate(
    ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"], 1)})


def to_iso_date(text: str | None) -> str:
    """'5 October 2026' or '5 ตุลาคม 2569' -> '2026-10-05'. Code does this; a small model gets it wrong."""
    match = re.search(r"(\d{1,2})\s+(\S+)\s+(\d{4})", text or "")
    if not match or match.group(2).lower() not in MONTHS:
        return ""
    day, month, year = int(match.group(1)), MONTHS[match.group(2).lower()], int(match.group(3))
    if year > 2400:  # Buddhist era
        year -= 543
    return f"{year:04d}-{month:02d}-{day:02d}"


def matching_types(text: str) -> set[str]:
    text = text.lower()
    return {doc_type for keyword, doc_type in RULES if keyword in text}


# ---------------------------------------------------------------- state that survives a restart
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


# ---------------------------------------------------------------- the agent
@dataclass
class Decision:
    doc_id: str
    action: str  # one of the six document types, or needs_human
    doc_type: str = ""
    doc_no: str = ""
    reason: str = ""
    decided_by: str = ""  # rules | llm
    issue_date: str = ""
    total: str = ""
    currency: str = ""
    seconds: float = 0.0


class InboxAgent:
    """Chooses an action for each document. The LLM reads; this class keeps the state and the checks."""

    def __init__(self, mode: str, state: State):
        self.mode, self.state = mode, state
        self.llm = None if mode == "rules" else get_llm()
        self.llm_calls = 0

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

    def extract(self, text: str) -> dict[str, str]:
        self.llm_calls += 1
        doc = self.llm.with_structured_output(FinancialDoc).invoke(
            [("system", "Extract the fields from this business document."), ("user", text)])
        return {"issue_date": to_iso_date(doc.issue_date_text), "total": f"{doc.total:.2f}", "currency": doc.currency}

    def decide(self, doc_id: str, text: str) -> Decision:
        started = time.time()
        try:
            reading, decided_by = self.read(text)
        except Exception as error:  # a failed LLM call must not stop the whole run
            return Decision(doc_id, "needs_human", reason=f"could not read the document: {error}"[:200], decided_by="llm")
        if reading is None:
            return Decision(doc_id, "needs_human", reason="no single keyword rule matched", decided_by=decided_by)

        reason = "one keyword rule matched" if decided_by == "rules" else "classified by the LLM"
        decision = Decision(doc_id, reading.doc_type, reading.doc_type, reading.doc_no or "", reason, decided_by)
        if reading.doc_type == "invoice" and reading.doc_no:
            first = self.state.invoice_numbers.setdefault(reading.doc_no, doc_id)
            if first != doc_id:
                decision.action = "needs_human"
                decision.reason = f"invoice number {reading.doc_no} was already received in {first}"
        if self.llm is not None and reading.doc_type in FINANCIAL:
            try:
                for key, value in self.extract(text).items():
                    setattr(decision, key, value)
            except Exception as error:
                decision.reason += f" (fields not extracted: {error})"[:120]
        decision.seconds = round(time.time() - started, 2)
        return decision


# ---------------------------------------------------------------- running it
def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel shows Thai correctly
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def score(decisions: dict[str, dict], labels_path: Path) -> str:
    """Compare with an answer key, using the same performance measure as the notebook."""
    with labels_path.open(encoding="utf-8") as f:
        expected = {row["doc_id"]: row["expected_action"] for row in csv.DictReader(f)}
    counts = {"correct": 0, "abstain": 0, "wrong": 0}
    for doc_id, decision in decisions.items():
        if doc_id not in expected:
            continue
        if decision["action"] == expected[doc_id]:
            counts["correct"] += 1
        elif decision["action"] == "needs_human":
            counts["abstain"] += 1
        else:
            counts["wrong"] += 1
    reward = sum(REWARDS[outcome] * n for outcome, n in counts.items())
    return f"reward {reward}  (correct {counts['correct']}, handed to a person {counts['abstain']}, wrong {counts['wrong']})"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route a folder of documents and extract the fields of financial ones.")
    parser.add_argument("folder", nargs="?", type=Path, default=REPO_ROOT / "data" / "inbox", help="folder of .txt documents (default: data/inbox)")
    parser.add_argument("--agent", choices=["llm", "hybrid", "rules"], default="llm", help="llm (default), hybrid = rules first, rules = no LLM at all")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "out" / "inbox", help="where results and state are written (default: out/inbox)")
    parser.add_argument("--limit", type=int, help="process at most this many new documents")
    parser.add_argument("--reset", action="store_true", help="forget earlier runs before starting")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per HTTP call is too noisy here
    if not args.folder.is_dir():
        log.error("error: %s is not a folder", args.folder)
        return 2
    state_path = args.out / "state.json"
    if args.reset and state_path.exists():
        state_path.unlink()
    state = State(state_path)

    files = sorted(args.folder.glob("*.txt"))
    pending = [f for f in files if f.stem not in state.decisions]
    new = pending[: args.limit]
    log.info("%d documents in %s, %d already processed, %d to do now (agent: %s)",
             len(files), args.folder, len(files) - len(pending), len(new), args.agent)

    try:
        agent = InboxAgent(args.agent, state)
    except Exception as error:
        log.error("error: could not start the LLM: %s", error)
        return 1
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

    args.out.mkdir(parents=True, exist_ok=True)
    rows = [state.decisions[k] for k in sorted(state.decisions)]
    write_csv(args.out / "routing.csv", rows, ["doc_id", "action", "doc_type", "doc_no", "decided_by", "seconds", "reason"])
    write_csv(args.out / "extracted.csv", [r for r in rows if r["total"]], ["doc_id", "doc_type", "doc_no", "issue_date", "total", "currency"])
    log.info("\nwrote %s and extracted.csv (%d documents so far, %d LLM calls this run)", args.out / "routing.csv", len(rows), agent.llm_calls)

    labels = args.folder.parent / f"{args.folder.name}_labels.csv"
    if labels.exists():
        log.info("against %s: %s", labels.name, score(state.decisions, labels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
