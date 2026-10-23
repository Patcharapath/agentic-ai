# `contract_review.py` explained, part by part

Read this after finishing the `lab3_planning` notebook, because `contract_review.py` contains the answers to its `# TODO` items. Keep `contract_review.py` open next to it and read the two together.

Things explained in earlier labs are not repeated: `parse_args()`, `main()`, stdout and stderr, and exit codes (`lab-00-setup/hello_llm.en.md`); logging and writing CSV (`lab-01-agent-foundations/inbox_app.en.md`); checking results instead of trusting the agent's word (`lab-02-tool-use/invoice_agent.en.md`).

## 1. Overview: what moved over from the notebook and what was added

| In the notebook | In `contract_review.py` | What changed |
|---|---|---|
| `Violations`, `Facts`, `RuleCheck`, `Finding`, `Draft` | Same names, moved to the top of the file | Nothing |
| `plan_rules()` | `plan_rules()` | Nothing |
| `single_call()`, `reflection()` | `Reviewer.single()`, `Reviewer.reflect()` | Gathered into one class |
| The graph from part 5 | `Reviewer._build_graph()` | **Added:** records the reasoning of every check, and reports rules that could not be checked |
| `ask()` with one retry | `Reviewer.ask()` | Nothing |
| `run_pattern()` and `evaluate()` | The loop in `main()` and `score()` | **Added:** choose the pattern with `--pattern` and the contracts with `--contracts` |
| Results in a dict | `findings.csv` and `checks.csv` | **New:** results and reasons go to files |

## 2. Why the additions: what real contract review needs

1. **It must be able to say why.** A legal team will not accept "this contract breaks R7" without a reason. So the program records the model's reasoning for every rule check in `checks.csv`.
2. **Could not check must not mean passed.** If the model fails to answer for a rule and the program counts that as passing, a flawed contract slips through with nobody knowing, the most expensive mistake in this job.
3. **It must be able to choose between speed and accuracy.** On a busy day you might screen with the single call first and use Plan-and-Execute for high-value contracts. So the pattern should be a command option, not a code edit.

## 3. The added parts, one at a time

### 3.1 Yes/no questions instead of a multi-way choice

```python
class Facts(BaseModel):
    # Two yes/no questions, not one "service / goods / other" choice: in testing the small model
    # labelled a computer purchase "service" every time with the choice, and got it right with yes/no.
    buys_goods: bool = Field(description="true if the company is buying products such as computers, equipment or materials")
    is_service: bool = Field(description="true if the supplier performs ongoing work such as maintenance, cleaning, consulting or hosting")
```

While building the lab we asked for the contract type as a `"service" / "goods" / "other"` choice, and the model labelled the computer purchase (c3) `service` every time, although asked in plain text it correctly said goods. Changed to two yes/no questions, the model got all 5 contracts right.

The same lesson as field order in part 4 of the notebook: **the shape of a schema can change the answer.** Always test a schema on real data.

### 3.2 `plan_rules()`: code does the planning

```python
def plan_rules(facts: Facts) -> list[str]:
    """The plan: which policy rules apply to a contract with these facts. Code decides, not the model."""
    rules = ["R1", "R2", "R6", "R7"]
    if facts.total_value_thb > 500_000:
        rules.append("R3")
```

This function calls no LLM. It takes the facts the LLM extracted and decides with plain conditions. As a separate function it can be tested without the model: `plan_rules(Facts(buys_goods=True, is_service=False, total_value_thb=900_000, processes_personal_data=False))` must always give R1, R2, R3, R6, R7, R8.

`500_000` is 500000. Python allows `_` between digits for readability.

### 3.3 `Reviewer`: two models, and somewhere to keep reasons

```python
    def __init__(self, contracts: dict[str, str]):
        self.contracts = contracts
        self.llm = get_llm()
        self.check_llm = get_llm(num_predict=300)  # a rule check needs one sentence, not a page
        self.calls = 0
        self.audit: list[dict] = []  # one row per rule check, for checks.csv
```

- **Two models.** The first is for work that may need longer answers (the single call, drafting and reviewing). The second checks one rule at a time and caps its answer at 300 tokens, so a model that fails to stop wastes no more than that.
- **`self.audit`** keeps every check as a row, written out as `checks.csv` at the end.

### 3.4 `ask()`: retry once, then let the error reach the caller

```python
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
```

On the first failure the loop tries again; on the second, `raise` passes the original error on. `ask()` does not decide what a failure should become, because each caller needs something different: a rule check turns it into "unchecked", while fact extraction has no way to carry on, so the program reports the error.

A bare `raise` works only inside an `except` and means "pass on the error just caught".

### 3.5 A graph built inside the class

```python
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
```

Three differences from the notebook:

- **The node is a function inside a method.** `check_next_rule` is defined inside `_build_graph()`, so it can use `self` (calling `self.ask` and writing `self.audit`) without receiving it as an argument. A function like this is called a closure.
- **Three-way values.** `complies` can be `True` (passes), `False` (fails) or `None` (could not be checked). So the state's type hint says `dict[str, bool | None]`.
- **Every check is recorded**, passed, failed or unchecked, in `self.audit`.

### 3.6 From `None` to "unchecked"

```python
    def plan(self, cid: str) -> dict:
        final = self.graph.invoke({"contract_id": cid}, {"recursion_limit": 30})
        checks = final["checks"]
        return {"violations": sorted(r for r, ok in checks.items() if ok is False),
                "unchecked": sorted(r for r, ok in checks.items() if ok is None)}
```

It uses `ok is False` and `ok is None`, not `not ok`, because `not None` is true as well. Writing `not ok` would count unchecked rules as violations, wrong in the other direction. So unchecked rules get a list of their own and are shown on screen for a person to see.

### 3.7 Choosing the pattern by name

```python
                result = getattr(reviewer, pattern)(cid)
```

`getattr(reviewer, "plan")` returns the method `reviewer.plan`, just like writing `reviewer.plan`, but with the name taken from a variable. So this one line calls `single`, `reflect` or `plan` as the user chose in `--pattern`, with no three-way `if`. The names in `--pattern`'s `choices` must match the method names exactly.

### 3.8 `--show-graph`

```python
    if args.show_graph:
        print(reviewer.graph.get_graph().draw_mermaid())
        return 0
```

LangGraph can turn a graph into Mermaid text. Paste it into <https://mermaid.live> to see it as a picture. Looking at the graph is a good way to check the paths you wrote are the ones you meant. Dashed lines in the picture are conditional edges.

## 4. What `checks.csv` looks like

After a Plan-and-Execute run, each row is one rule check (examples from a real run, shortened):

| contract | rule | complies | reasoning |
|---|---|---|---|
| c1 | R2 | False | Clause 5 sets 15 days' notice, less than the 30 days the rule requires |
| c1 | R3 | False | Value 540,000 THB is over 500,000, but the signer is a manager, not a director |
| c3 | R8 | False | The warranty is 6 months, less than the 12 months the rule requires |
| c5 | R2 | True | 45 days' notice is more than 30 days |

## 5. The parts that match the notebook

All the schemas, `plan_rules()`, the reviewer's instruction for Reflection, the shape of the graph (`extract_facts` → `make_plan` → `check_next_rule` looping) and the scoring by precision, recall and F1.

## 6. Try changing it yourself

1. Add a rule R9 to `data/policy.json`, such as "contracts longer than 12 months must include a price review clause", and change `Facts` and `plan_rules()` to support it. Which field do you need to add to `Facts`?
2. Add a `reasons` column to `findings.csv` that gathers the reasons for the failed rules, so a person can understand everything from one file.
3. At present unchecked rules are not counted in the score. Change them to count as violations (fail closed) and see how precision and recall change. Which suits contract review better?
4. Run `--pattern all --contracts c3` and compare how each pattern judges c3.

## 7. Glossary

| Term | Meaning |
|---|---|
| Audit trail | A record that lets you trace what the system decided, when, and why |
| Fail safe | When something fails, the outcome falls on the safe side; here, a person checks |
| Fail closed | When unsure, treat it as failing |
| Closure | A function defined inside another function that can use the outer function's variables |
| `getattr` | Fetch an object's attribute or method by a name given as text |
| Mermaid | A text language for drawing diagrams such as flowcharts |
| Precision / recall | How much of what is reported is right / how much of what is really wrong is found |
