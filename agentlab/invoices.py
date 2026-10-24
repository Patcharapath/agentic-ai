"""Tools and data for Lab 2: checking supplier invoices against purchase orders.

The invoices are PDF files in ``data/invoices``. The purchase orders live in a
SQLite database that ``create_database()`` builds from ``data/procurement_seed.sql``.

Each tool is a plain Python function wrapped with LangChain's ``@tool``. The
function name, the docstring and the argument descriptions become the tool
definition the model reads, so they are written for the model as much as for
people. Every tool returns a short JSON string, and reports problems as data
(an ``"error"`` field saying what to do next) instead of raising.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal

import pdfplumber
from langchain_core.tools import tool

REPO_ROOT = Path(__file__).resolve().parent.parent
INVOICE_DIR = REPO_ROOT / "data" / "invoices"
SEED = REPO_ROOT / "data" / "procurement_seed.sql"
DB_PATH = REPO_ROOT / "out" / "procurement.db"
VAT_RATE = 0.07
TOTAL_LABELS = ("รวมทั้งสิ้น", "total due")


# ---------------------------------------------------------------- database
def create_database(path: Path | None = None, reset: bool = False) -> Path:
    """Build the purchase-order database from the seed file. With reset=True, start from scratch.

    Without a path it uses the module's DB_PATH, which a program may point elsewhere.
    """
    path = Path(path or DB_PATH)
    if reset and path.exists():
        path.unlink()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.executescript(SEED.read_text(encoding="utf-8"))
    return path


def query(sql: str, params: tuple = ()) -> list[dict]:
    with sqlite3.connect(create_database()) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql, params)]


def recorded_checks() -> list[dict]:
    """Everything record_result has written so far."""
    return query("SELECT * FROM invoice_checks ORDER BY file")


# ---------------------------------------------------------------- reading PDFs
def _invoice_path(filename: str) -> Path:
    """Only files inside data/invoices may be opened: a tool must not read whatever path it is given."""
    path = (INVOICE_DIR / Path(filename).name).resolve()
    if path.parent != INVOICE_DIR.resolve() or not path.exists():
        raise FileNotFoundError(f"{filename} is not in data/invoices")
    return path


def _number(text: str) -> float:
    return float(text.replace(",", ""))


def _line_items(path: Path) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        tables = pdf.pages[0].extract_tables()
    rows = tables[0][1:] if tables else []  # skip the header row
    return [{"item_code": r[0], "description": r[1], "qty": int(_number(r[2])), "unit_price": _number(r[3]), "amount": _number(r[4])}
            for r in rows]


def _printed_total(text: str) -> float | None:
    for line in text.splitlines():
        if any(label in line.lower() for label in TOTAL_LABELS):
            amounts = re.findall(r"\d[\d,]*\.\d{2}", line)
            if amounts:
                return _number(amounts[-1])
    return None


def _invoice_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return pdf.pages[0].extract_text()


def _header_value(text: str, labels: tuple[str, ...], pattern: str) -> str | None:
    """Find a value such as the invoice or PO number on the line that carries one of the labels."""
    for line in text.splitlines():
        if any(label in line.lower() for label in labels):
            match = re.search(pattern, line)
            if match:
                return match.group()
    return None


def invoice_header(filename: str) -> dict:
    """Invoice number and PO number as printed. Code reads them, so the model never has to copy them."""
    text = _invoice_text(_invoice_path(filename))
    return {
        "invoice_no": _header_value(text, ("เลขที่", "invoice no"), r"[A-Z]{2,3}-[A-Z0-9-]+"),
        "po_number": _header_value(text, ("ใบสั่งซื้อ", "purchase order"), r"PO-[0-9-]+"),
    }


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


# ---------------------------------------------------------------- the tools
@tool(parse_docstring=True)
def read_invoice(filename: str) -> str:
    """Return the full text of an invoice PDF.

    Use it to see what the invoice says: supplier, items, amounts and any purchase order (PO) number.

    Args:
        filename: File name of the invoice, e.g. inv_01.pdf
    """
    try:
        return _invoice_text(_invoice_path(filename))
    except FileNotFoundError as e:
        return _error(f"{e}. Check the file name.")


@tool(parse_docstring=True)
def check_invoice_total(filename: str) -> str:
    """Recalculate an invoice's total from its line items plus 7% VAT and compare it with the total printed on the invoice.

    Use this instead of doing the arithmetic yourself.

    Args:
        filename: File name of the invoice, e.g. inv_01.pdf
    """
    try:
        path = _invoice_path(filename)
    except FileNotFoundError as e:
        return _error(f"{e}. Check the file name.")
    subtotal = round(sum(item["amount"] for item in _line_items(path)), 2)
    expected = round(subtotal * (1 + VAT_RATE), 2)
    printed = _printed_total(_invoice_text(path))
    if printed is None:
        return _error("No printed total found on the invoice. Reject it with reason 'total'.")
    return json.dumps({"subtotal": subtotal, "vat": round(subtotal * VAT_RATE, 2), "expected_total": expected,
                       "printed_total": printed, "total_ok": abs(expected - printed) < 0.01})


@tool(parse_docstring=True)
def compare_with_po(filename: str) -> str:
    """Compare each line of an invoice with the purchase order (PO) printed on it: item code, quantity and unit price.

    The tool finds the PO number on the invoice itself. Returns the differences found, or an
    error if the invoice shows no PO number or the PO does not exist.

    Args:
        filename: File name of the invoice, e.g. inv_01.pdf
    """
    try:
        path = _invoice_path(filename)
    except FileNotFoundError as e:
        return _error(f"{e}. Check the file name.")
    po_number = invoice_header(filename)["po_number"]
    if po_number is None:
        return _error("The invoice shows no PO number. Reject it with reason 'no_po'.")
    po = {row["item_code"]: row for row in query("SELECT * FROM po_lines WHERE po_number = ?", (po_number,))}
    if not po:
        return _error(f"Purchase order {po_number} does not exist. Reject the invoice with reason 'po_not_found'.")
    problems = []
    for item in _line_items(path):
        ordered = po.get(item["item_code"])
        if ordered is None:
            problems.append(f"{item['item_code']} is not on {po_number}")
            continue
        if item["qty"] > ordered["qty"]:
            problems.append(f"{item['item_code']}: invoiced quantity {item['qty']} is more than the {ordered['qty']} ordered")
        if abs(item["unit_price"] - ordered["unit_price"]) > 0.005:
            problems.append(f"{item['item_code']}: invoiced unit price {item['unit_price']:,.2f} differs from the PO price {ordered['unit_price']:,.2f}")
    return json.dumps({"po_number": po_number, "matches_po": not problems, "problems": problems}, ensure_ascii=False)


@tool(parse_docstring=True)
def record_result(filename: str, verdict: Literal["approve", "reject"], reason: str) -> str:
    """Save the final verdict for an invoice to the accounts database.

    Call it exactly once per invoice, after all checks are done. Calling it again for the
    same invoice replaces the earlier verdict.

    Args:
        filename: File name of the invoice, e.g. inv_01.pdf
        verdict: approve only if every check passed; otherwise reject
        reason: One short sentence. For a rejection, name the failed check: total, unit_price, quantity, po_not_found or no_po
    """
    try:
        invoice_no = invoice_header(filename)["invoice_no"] or Path(filename).stem
    except FileNotFoundError as e:
        return _error(f"{e}. Check the file name.")
    with sqlite3.connect(create_database()) as db:
        db.execute("INSERT OR REPLACE INTO invoice_checks VALUES (?, ?, ?, ?, ?)",
                   (invoice_no, Path(filename).name, verdict, reason.strip(), datetime.now().isoformat(timespec="seconds")))
    return json.dumps({"saved": True, "invoice_no": invoice_no, "verdict": verdict})


TOOLS = [read_invoice, check_invoice_total, compare_with_po, record_result]

SYSTEM_PROMPT = """You check supplier invoices for the accounts team, using the tools provided.

For the invoice you are given:
1. Call check_invoice_total.
2. Call compare_with_po.
3. Call record_result once. The verdict is "approve" only if the total is correct and the invoice matches
   its purchase order. Otherwise it is "reject", and the reason names the failed check: total, unit_price,
   quantity, po_not_found or no_po.
4. Reply with one line: the invoice number, the verdict and the reason.

Never do arithmetic yourself. Use read_invoice only if you need to see the invoice text."""


def evaluate_checks() -> "pd.DataFrame":
    """Compare the verdicts saved by record_result with the answer key in data/invoices_labels.csv."""
    import pandas as pd

    labels = pd.read_csv(REPO_ROOT / "data" / "invoices_labels.csv").set_index("file")
    saved = pd.DataFrame(recorded_checks(), columns=["invoice_no", "file", "verdict", "reason", "checked_at"]).set_index("file")
    table = labels[["invoice_no", "expected_verdict", "issue"]].join(saved[["verdict", "reason"]], how="left")
    table["verdict"] = table["verdict"].fillna("(not saved)")
    table["reason"] = table["reason"].fillna("")
    # A rejection is only right if it names the check that actually failed.
    named = [issue == "none" or issue in reason for issue, reason in zip(table["issue"], table["reason"])]
    table["correct"] = (table["verdict"] == table["expected_verdict"]) & pd.Series(named, index=table.index)
    return table
