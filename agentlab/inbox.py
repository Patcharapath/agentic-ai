"""The document inbox: a small task environment used in Lab 1.

Documents arrive one at a time. For each one the agent chooses an action:
route it to one of six document types, or hand it to a person
(``needs_human``). The environment scores every action, which makes the
performance measure explicit and lets different agents be compared fairly.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from agentlab.llm import release_model

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOC_TYPES = ["invoice", "receipt", "purchase_order", "contract", "leave_request", "other"]
ACTIONS = DOC_TYPES + ["needs_human"]


@dataclass(frozen=True)
class Percept:
    """What the agent senses at one step: a single document."""

    doc_id: str
    text: str


class Agent(Protocol):
    def act(self, percept: Percept) -> str: ...


def load_labels() -> pd.DataFrame:
    """Ground truth for the inbox, one row per document."""
    return pd.read_csv(DATA_DIR / "inbox_labels.csv", dtype={"doc_no": "string", "issue_date": "string"}).set_index("doc_id")


class InboxEnvironment:
    """Feeds documents to an agent in arrival order and scores its actions.

    The three rewards are the performance measure. Change them and the
    "best" agent may change too.
    """

    def __init__(self, correct: float = 1.0, abstain: float = 0.0, wrong: float = -1.0, limit: int | None = None):
        self.rewards = {"correct": correct, "abstain": abstain, "wrong": wrong}
        self.labels = load_labels()
        ids = list(self.labels.index)[:limit]
        self.percepts = [Percept(i, (DATA_DIR / "inbox" / f"{i}.txt").read_text(encoding="utf-8")) for i in ids]

    def score(self, doc_id: str, action: str) -> tuple[str, float]:
        expected = self.labels.loc[doc_id, "expected_action"]
        if action == expected:
            outcome = "correct"
        elif action == "needs_human":
            outcome = "abstain"
        else:
            outcome = "wrong"
        return outcome, self.rewards[outcome]

    def run(self, agent: Agent, verbose: bool = False, release: bool = True) -> pd.DataFrame:
        """Run one episode: every document once, in order. Returns one row per document.

        When the episode ends the local model is unloaded to give its RAM back
        (see ``release_model``). Pass ``release=False`` to keep it loaded.
        """
        if hasattr(agent, "reset"):
            agent.reset()
        rows = []
        for percept in self.percepts:
            start = time.time()
            action = agent.act(percept)
            seconds = time.time() - start
            if action not in ACTIONS:
                raise ValueError(f"{type(agent).__name__} returned {action!r}; valid actions are {ACTIONS}")
            outcome, reward = self.score(percept.doc_id, action)
            rows.append({
                "doc_id": percept.doc_id,
                "expected": self.labels.loc[percept.doc_id, "expected_action"],
                "action": action,
                "outcome": outcome,
                "reward": reward,
                "seconds": round(seconds, 2),
            })
            if verbose:
                print(f"{percept.doc_id}  {action:15s} {outcome}")
        if release:
            release_model()
        return pd.DataFrame(rows).set_index("doc_id")


def summarize(runs: dict[str, pd.DataFrame], agents: dict[str, object] | None = None) -> pd.DataFrame:
    """One row per agent: total reward, outcome counts, time, and LLM calls if the agent counts them."""
    rows = []
    for name, df in runs.items():
        counts = df["outcome"].value_counts()
        row = {
            "agent": name,
            "reward": df["reward"].sum(),
            "correct": int(counts.get("correct", 0)),
            "abstain": int(counts.get("abstain", 0)),
            "wrong": int(counts.get("wrong", 0)),
            "seconds": round(df["seconds"].sum(), 1),
        }
        if agents is not None:
            row["llm_calls"] = getattr(agents.get(name), "llm_calls", 0)
        rows.append(row)
    return pd.DataFrame(rows).set_index("agent")
