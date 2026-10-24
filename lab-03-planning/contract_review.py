"""Lab 3 - review contracts against the company policy with a chosen reasoning pattern.

The notebook compares the patterns on three contracts. This program runs them on
a whole folder and keeps an audit trail: for Plan-and-Execute, the reasoning
behind every single rule check is saved, so a person can see why a contract
was flagged.

    uv run python lab-03-planning/contract_review.py                     # plan-and-execute on data/contracts
    uv run python lab-03-planning/contract_review.py --pattern all       # single, reflect and plan, then compare
    uv run python lab-03-planning/contract_review.py --contracts c1 c5   # only some contracts
    uv run python lab-03-planning/contract_review.py --show-graph        # print the Plan-and-Execute graph

What a program needs that the notebook did not:

- An audit trail. Every rule check is written to checks.csv with the model's reasoning.
- Failing safe. A rule the model could not check is reported as "unchecked" for a
  person to look at, instead of silently counting as compliant.
- Patterns as a choice. --pattern picks the trade-off between cost and accuracy.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path
from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agentlab import get_llm, release_model
from agentlab.contracts import RULES, policy_text

log = logging.getLogger("contract_review")
REPO_ROOT = Path(__file__).resolve().parent.parent
RuleId = Literal["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]
REVIEWER = "You review contracts against the company contract policy. A rule counts only if it applies to this kind of contract."
REVIEW_INSTRUCTION = (
    "You are a senior reviewer checking a first reviewer's findings. Keep a finding only if the rule applies to this kind "
    "of contract AND the contract really breaks it. Remove every other finding. Add any rule the first reviewer missed."
)


# ---------------------------------------------------------------- what we ask the model for
class Violations(BaseModel):
    violated: list[RuleId] = Field(description="IDs of the policy rules this contract breaks; empty if it breaks none")


class Facts(BaseModel):
    # Two yes/no questions, not one "service / goods / other" choice: in testing the small model
    # labelled a computer purchase "service" every time with the choice, and got it right with yes/no.
    buys_goods: bool = Field(description="true if the company is buying products such as computers, equipment or materials")
    is_service: bool = Field(description="true if the supplier performs ongoing work such as maintenance, cleaning, consulting or hosting")
    total_value_thb: float = Field(description="Total value of the contract in THB for its whole term")
    processes_personal_data: bool = Field(description="true if the supplier will handle personal data, such as customers' names or phone numbers")


class RuleCheck(BaseModel):
    reasoning: str = Field(description="At most 15 words: the relevant clause, and whether it meets the rule")
    complies: bool = Field(description="true if the contract satisfies the rule")


class Finding(BaseModel):
    rule_id: RuleId
    reason: str = Field(description="At most 15 words")


class Draft(BaseModel):
    findings: list[Finding] = Field(description="Every rule the contract breaks; empty if none")


def plan_rules(facts: Facts) -> list[str]:
    """The plan: which policy rules apply to a contract with these facts. Code decides, not the model."""
    rules = ["R1", "R2", "R6", "R7"]
    if facts.total_value_thb > 500_000:
        rules.append("R3")
    if facts.is_service:
        rules.append("R4")
    if facts.processes_personal_data:
        rules.append("R5")
    if facts.buys_goods:
        rules.append("R8")
    return sorted(rules)


# ---------------------------------------------------------------- the reviewer
class Reviewer:
    def __init__(self, contracts: dict[str, str]):
        self.contracts = contracts
        self.llm = get_llm()
        self.check_llm = get_llm(num_predict=300)  # a rule check needs one sentence, not a page
        self.calls = 0
        self.audit: list[dict] = []  # one row per rule check, for checks.csv
        self.graph = self._build_graph()

    def ask(self, schema, system: str, user: str, model=None):
        """One structured call, retried once: a small model sometimes fails to finish the JSON."""
        chain = (model or self.llm).with_structured_output(schema)
        messages = [SystemMessage(system), HumanMessage(user)]
        for attempt in (1, 2):
            self.calls += 1
            try:
                return chain.invoke(messages)
            except Exception:
                if attempt == 2:
                    raise

    # -- single call
    def single(self, cid: str) -> dict:
        out = self.ask(Violations, REVIEWER, f"Policy:\n{policy_text()}\n\nContract:\n{self.contracts[cid]}\n\nWhich rules does the contract break?")
        return {"violations": sorted(set(out.violated)), "unchecked": []}

    # -- reflection
    def reflect(self, cid: str) -> dict:
        text = self.contracts[cid]
        draft = self.ask(Draft, REVIEWER, f"Policy:\n{policy_text()}\n\nContract:\n{text}\n\nWhich rules does the contract break, and why?")
        listed = "\n".join(f"- {f.rule_id}: {f.reason}" for f in draft.findings) or "(none)"
        review = self.ask(Violations, REVIEW_INSTRUCTION,
                          f"Policy:\n{policy_text()}\n\nContract:\n{text}\n\nFirst reviewer's findings:\n{listed}\n\nWhich rules does the contract really break?")
        return {"violations": sorted(set(review.violated)), "unchecked": []}

    # -- plan-and-execute, as a LangGraph graph
    def _build_graph(self):
        class ReviewState(TypedDict, total=False):
            contract_id: str
            facts: Facts
            plan: list[str]
            checks: dict[str, bool | None]  # None: could not be checked

        def extract_facts(state):
            return {"facts": self.ask(Facts, "You extract facts from a contract.", self.contracts[state["contract_id"]])}

        def make_plan(state):
            return {"plan": plan_rules(state["facts"]), "checks": {}}

        def check_next_rule(state):
            cid, rid = state["contract_id"], state["plan"][0]
            try:
                result = self.ask(RuleCheck, "You check one contract against one policy rule. Keep the reasoning brief.",
                                  f"Rule {rid}: {RULES[rid]['text']}\n\nContract:\n{self.contracts[cid]}\n\nDoes the contract satisfy this rule?",
                                  model=self.check_llm)
                complies, reasoning = result.complies, result.reasoning
            except Exception as error:  # fail safe: a person looks at it
                complies, reasoning = None, f"could not check: {type(error).__name__}"
            self.audit.append({"contract": cid, "rule": rid, "complies": complies, "reasoning": reasoning})
            return {"plan": state["plan"][1:], "checks": {**state["checks"], rid: complies}}

        def route(state):
            return "check_next_rule" if state["plan"] else END

        graph = StateGraph(ReviewState)
        graph.add_node("extract_facts", extract_facts)
        graph.add_node("make_plan", make_plan)
        graph.add_node("check_next_rule", check_next_rule)
        graph.add_edge(START, "extract_facts")
        graph.add_edge("extract_facts", "make_plan")
        graph.add_conditional_edges("make_plan", route, ["check_next_rule", END])
        graph.add_conditional_edges("check_next_rule", route, ["check_next_rule", END])
        return graph.compile()

    def plan(self, cid: str) -> dict:
        final = self.graph.invoke({"contract_id": cid}, {"recursion_limit": 30})
        checks = final["checks"]
        return {"violations": sorted(r for r, ok in checks.items() if ok is False),
                "unchecked": sorted(r for r, ok in checks.items() if ok is None)}


# ---------------------------------------------------------------- scoring and output
def load_answer_key(folder: Path) -> dict[str, set[str]] | None:
    path = folder.parent / f"{folder.name}_labels.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return {r["contract_id"]: set(filter(None, r["violated_rules"].split(";"))) for r in csv.DictReader(f)}


def score(found: dict[str, list[str]], key: dict[str, set[str]]) -> str:
    tp = sum(len(set(v) & key[c]) for c, v in found.items() if c in key)
    fp = sum(len(set(v) - key[c]) for c, v in found.items() if c in key)
    fn = sum(len(key[c] - set(v)) for c, v in found.items() if c in key)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return f"precision {precision:.2f}  recall {recall:.2f}  F1 {f1:.2f}  (tp {tp}, fp {fp}, fn {fn})"


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review contracts against the company policy with a chosen reasoning pattern.")
    parser.add_argument("folder", nargs="?", type=Path, default=REPO_ROOT / "data" / "contracts", help="folder of contract .txt files (default: data/contracts)")
    parser.add_argument("--pattern", choices=["single", "reflect", "plan", "all"], default="plan", help="which pattern to run (default: plan)")
    parser.add_argument("--contracts", nargs="+", metavar="ID", help="only these contract IDs, e.g. c1 c5")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "out" / "contract_review", help="folder for the results (default: out/contract_review)")
    parser.add_argument("--show-graph", action="store_true", help="print the Plan-and-Execute graph as Mermaid and stop")
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
    contracts = {p.stem: p.read_text(encoding="utf-8") for p in sorted(args.folder.glob("*.txt"))}
    if args.contracts:
        missing = set(args.contracts) - set(contracts)
        if missing:
            log.error("error: no such contract(s): %s (available: %s)", ", ".join(sorted(missing)), ", ".join(contracts))
            return 2
        contracts = {cid: contracts[cid] for cid in args.contracts}

    try:
        reviewer = Reviewer(contracts)
    except Exception as error:
        log.error("error: could not start the LLM: %s", error)
        return 1
    if args.show_graph:
        print(reviewer.graph.get_graph().draw_mermaid())
        return 0

    patterns = ["single", "reflect", "plan"] if args.pattern == "all" else [args.pattern]
    key = load_answer_key(args.folder)
    args.out.mkdir(parents=True, exist_ok=True)
    rows, summary = [], []
    try:
        for pattern in patterns:
            reviewer.calls, started, found = 0, time.time(), {}
            log.info("== %s on %d contracts", pattern, len(contracts))
            for cid in contracts:
                result = getattr(reviewer, pattern)(cid)
                found[cid] = result["violations"]
                rows.append({"pattern": pattern, "contract": cid, "violations": ";".join(result["violations"]) or "-",
                             "unchecked": ";".join(result["unchecked"])})
                note = f"  unchecked: {', '.join(result['unchecked'])}" if result["unchecked"] else ""
                log.info("   %s  %s%s", cid, ", ".join(result["violations"]) or "(complies)", note)
            release_model()
            line = f"{pattern}: {reviewer.calls} LLM calls, {time.time() - started:.0f}s"
            if key:
                line += "  |  " + score(found, key)
            summary.append(line)
    except KeyboardInterrupt:
        log.info("stopped")
    finally:
        release_model()

    write_csv(args.out / "findings.csv", rows, ["pattern", "contract", "violations", "unchecked"])
    if reviewer.audit:
        write_csv(args.out / "checks.csv", reviewer.audit, ["contract", "rule", "complies", "reasoning"])
    log.info("\n%s\nWrote %s%s", "\n".join(summary), args.out / "findings.csv", " and checks.csv" if reviewer.audit else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
