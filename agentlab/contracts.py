"""Data, tools and scoring for Lab 3: reviewing contracts against a company policy.

Five contracts in ``data/contracts`` (Thai and English) are checked against the
eight rules in ``data/policy.json``. Not every rule applies to every contract:
some apply only to service contracts, to purchases of goods, to contracts over
500,000 THB, or to suppliers that process personal data. Deciding which rules
to check is the planning part of the task.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from langchain_core.tools import tool

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
POLICY = json.loads((DATA / "policy.json").read_text(encoding="utf-8"))
RULES = {r["id"]: r for r in POLICY["rules"]}
RULE_IDS = list(RULES)
CLASS_SET = ["c1", "c2", "c5"]  # the three contracts used in class; all five run in the program


def load_contracts() -> dict[str, str]:
    """contract_id -> full text, e.g. {"c1": "สัญญาจ้างบริการ..."}"""
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted((DATA / "contracts").glob("*.txt"))}


def load_labels() -> pd.DataFrame:
    labels = pd.read_csv(DATA / "contracts_labels.csv", dtype=str, keep_default_na=False).set_index("contract_id")
    for col in ("applicable_rules", "violated_rules"):
        labels[col] = labels[col].map(lambda s: set(filter(None, s.split(";"))))
    return labels


def policy_text(rule_ids: list[str] | None = None, with_scope: bool = True) -> str:
    """The policy as text for a prompt: every rule, or only the ones listed."""
    lines = []
    for rid in rule_ids or RULE_IDS:
        r = RULES[rid]
        scope = f" (applies to {r['applies_to']})" if with_scope else ""
        lines.append(f"{rid} {r['title']}{scope}: {r['text']}")
    return "\n".join(lines)


def evaluate(predictions: dict[str, set[str]], contract_ids: list[str] | None = None) -> pd.DataFrame:
    """Compare predicted violations with the answer key, one row per contract plus a total row.

    precision: of the violations reported, how many are real
    recall:    of the real violations, how many were reported
    Only the contracts in contract_ids are scored (default: every contract in predictions).
    """
    labels = load_labels()
    ids = contract_ids or [cid for cid in labels.index if cid in predictions]
    rows = []
    for cid in ids:
        truth = labels.loc[cid, "violated_rules"]
        found = set(predictions.get(cid, set()))
        rows.append({"contract": cid, "expected": ";".join(sorted(truth)) or "-", "found": ";".join(sorted(found)) or "-",
                     "tp": len(found & truth), "fp": len(found - truth), "fn": len(truth - found)})
    table = pd.DataFrame(rows).set_index("contract")
    tp, fp, fn = (int(table[c].sum()) for c in ("tp", "fp", "fn"))
    table.loc["total"] = ["", "", tp, fp, fn]
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    table.attrs.update(precision=round(precision, 2), recall=round(recall, 2), f1=round(f1, 2))
    return table


def score_line(name: str, table: pd.DataFrame) -> dict:
    return {"pattern": name, **table.attrs, "tp": int(table.loc["total", "tp"]),
            "fp": int(table.loc["total", "fp"]), "fn": int(table.loc["total", "fn"])}


# ---------------------------------------------------------------- tools for the ReAct agent
@tool(parse_docstring=True)
def read_contract(contract_id: str) -> str:
    """Return the full text of a contract.

    Args:
        contract_id: The contract's ID, e.g. c1
    """
    contracts = load_contracts()
    if contract_id not in contracts:
        return json.dumps({"error": f"No contract {contract_id}. Available: {sorted(contracts)}"})
    return contracts[contract_id]


@tool(parse_docstring=True)
def list_policy_rules() -> str:
    """List every rule of the company contract policy: its ID, title and which contracts it applies to.

    Use it to decide which rules matter for a contract before checking them one by one.
    """
    return json.dumps([{"id": r["id"], "title": r["title"], "applies_to": r["applies_to"]} for r in POLICY["rules"]], ensure_ascii=False)


@tool(parse_docstring=True)
def get_policy_rule(rule_id: str) -> str:
    """Return the full wording of one policy rule.

    Args:
        rule_id: The rule's ID, from R1 to R8
    """
    rule = RULES.get(rule_id.strip().upper())
    if rule is None:
        return json.dumps({"error": f"No rule {rule_id}. Rules are {RULE_IDS}."})
    return json.dumps(rule, ensure_ascii=False)


TOOLS = [read_contract, list_policy_rules, get_policy_rule]
