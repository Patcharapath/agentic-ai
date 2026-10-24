# `contract_review.py` อธิบายทีละส่วน

อ่านเอกสารนี้หลังทำ notebook `lab3_planning` จบแล้ว เพราะ `contract_review.py` มีคำตอบของ `# TODO` อยู่ เปิดไฟล์ `contract_review.py` ไว้ข้างๆ แล้วอ่านไปพร้อมกัน

เรื่องที่อธิบายไปแล้วใน lab ก่อนหน้าจะไม่อธิบายซ้ำ: `parse_args()`, `main()`, stdout กับ stderr และ exit code (`lab-00-setup/hello_llm.th.md`), logging และการเขียน CSV (`lab-01-agent-foundations/inbox_app.th.md`), การตรวจผลแทนการเชื่อคำบอกของ agent (`lab-02-tool-use/invoice_agent.th.md`)

## 1. ภาพรวม: อะไรย้ายมาจาก notebook และอะไรเพิ่มเข้ามา

| ใน notebook | ใน `contract_review.py` | เปลี่ยนอย่างไร |
|---|---|---|
| `Violations`, `Facts`, `RuleCheck`, `Finding`, `Draft` | ชื่อเดิม ย้ายมาไว้ต้นไฟล์ | เหมือนเดิม |
| `plan_rules()` | `plan_rules()` | เหมือนเดิม |
| `single_call()`, `reflection()` | `Reviewer.single()`, `Reviewer.reflect()` | รวมไว้ใน class เดียว |
| Graph ของส่วนที่ 5 | `Reviewer._build_graph()` | **เพิ่ม:** บันทึกเหตุผลทุกการตรวจ และรายงานกฎที่ตรวจไม่ได้ |
| `ask()` ที่ลองใหม่หนึ่งครั้ง | `Reviewer.ask()` | เหมือนเดิม |
| `run_pattern()` กับ `evaluate()` | loop ใน `main()` กับ `score()` | **เพิ่ม:** เลือกรูปแบบด้วย `--pattern` และสัญญาด้วย `--contracts` |
| ผลอยู่ใน dict | `findings.csv` และ `checks.csv` | **ใหม่:** ผลและเหตุผลอยู่ในไฟล์ |

## 2. ทำไมต้องเพิ่ม: สิ่งที่งานตรวจสัญญาจริงต้องการ

1. **ต้องอธิบายได้ว่าทำไม** ฝ่ายกฎหมายจะไม่ยอมรับคำว่า "สัญญานี้ฝ่าฝืน R7" โดยไม่มีเหตุผล โปรแกรมจึงบันทึกเหตุผลของ model สำหรับการตรวจกฎทุกข้อลง `checks.csv`
2. **ตรวจไม่ได้ ต้องไม่เท่ากับผ่าน** ถ้า model ตอบไม่สำเร็จกับกฎข้อหนึ่ง แล้วโปรแกรมนับว่าผ่าน สัญญาที่ผิดจะหลุดไปโดยไม่มีใครรู้ ซึ่งเป็นความผิดพลาดที่แพงที่สุดในงานนี้
3. **ต้องเลือกได้ระหว่างความเร็วกับความแม่นยำ** วันที่สัญญาเยอะ อาจใช้การถามครั้งเดียวคัดกรองก่อน สัญญาที่มูลค่าสูงใช้ Plan-and-Execute การเลือกรูปแบบจึงควรเป็นตัวเลือกของคำสั่ง ไม่ใช่การแก้ code

## 3. ส่วนที่เพิ่มมา ทีละส่วน

### 3.1 คำถามแบบใช่/ไม่ใช่ แทนตัวเลือกหลายทาง

```python
class Facts(BaseModel):
    # Two yes/no questions, not one "service / goods / other" choice: in testing the small model
    # labelled a computer purchase "service" every time with the choice, and got it right with yes/no.
    buys_goods: bool = Field(description="true if the company is buying products such as computers, equipment or materials")
    is_service: bool = Field(description="true if the supplier performs ongoing work such as maintenance, cleaning, consulting or hosting")
```

ตอนสร้าง lab เราถามประเภทสัญญาเป็นตัวเลือก `"service" / "goods" / "other"` และ model ตอบว่าสัญญาซื้อคอมพิวเตอร์ (c3) เป็น `service` ทุกครั้ง ทั้งที่ถามเป็นข้อความธรรมดาแล้วตอบถูกว่า goods เมื่อเปลี่ยนเป็นคำถามใช่/ไม่ใช่สองข้อ model ตอบถูกทั้ง 5 ฉบับ

บทเรียนเดียวกับลำดับ field ในส่วนที่ 4 ของ notebook: **รูปร่างของ schema เปลี่ยนคำตอบได้** ทดสอบ schema กับข้อมูลจริงเสมอ

### 3.2 `plan_rules()`: code เป็นผู้วางแผน

```python
def plan_rules(facts: Facts) -> list[str]:
    """The plan: which policy rules apply to a contract with these facts. Code decides, not the model."""
    rules = ["R1", "R2", "R6", "R7"]
    if facts.total_value_thb > 500_000:
        rules.append("R3")
```

Function นี้ไม่เรียก LLM เลย มันรับข้อเท็จจริงที่ LLM ดึงมา แล้วตัดสินด้วยเงื่อนไขธรรมดา การแยกเป็น function ทำให้ทดสอบได้โดยไม่ต้องเปิด model เช่น `plan_rules(Facts(buys_goods=True, is_service=False, total_value_thb=900_000, processes_personal_data=False))` ต้องได้ R1, R2, R3, R6, R7, R8 เสมอ

`500_000` คือ 500000 Python อนุญาตให้ใช้ `_` คั่นหลักเพื่อให้อ่านง่าย

### 3.3 `Reviewer`: model สองตัว และที่เก็บเหตุผล

```python
    def __init__(self, contracts: dict[str, str]):
        self.contracts = contracts
        self.llm = get_llm()
        self.check_llm = get_llm(num_predict=300)  # a rule check needs one sentence, not a page
        self.calls = 0
        self.audit: list[dict] = []  # one row per rule check, for checks.csv
```

- **Model สองตัว** ตัวแรกใช้กับงานที่อาจต้องเขียนยาว (การถามครั้งเดียว ร่างและตรวจ) ตัวที่สองใช้ตรวจทีละกฎ และจำกัดคำตอบที่ 300 token ถ้า model เขียนไม่หยุด จะเสียเวลาไม่เกินนั้น
- **`self.audit`** เก็บการตรวจทุกครั้งเป็นแถวหนึ่ง แล้วเขียนเป็น `checks.csv` ตอนจบ

### 3.4 `ask()`: ลองใหม่หนึ่งครั้ง แล้วปล่อยให้ error ไปถึงผู้เรียก

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

ครั้งแรกที่ล้มเหลว loop ลองใหม่ ครั้งที่สองล้มเหลว `raise` ส่ง error เดิมต่อออกไป `ask()` ไม่ได้ตัดสินว่าความล้มเหลวควรเป็นอะไร เพราะแต่ละที่ที่เรียกมันต้องการต่างกัน: การตรวจกฎแปลงเป็น "unchecked" ส่วนการดึงข้อเท็จจริงไม่มีทางทำต่อได้ จึงปล่อยให้โปรแกรมแจ้ง error

`raise` ที่ไม่มีอะไรตามหลัง ใช้ได้เฉพาะใน `except` และหมายถึง "ส่ง error ที่เพิ่งจับได้ต่อไป"

### 3.5 Graph ที่สร้างภายใน class

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

สามจุดที่ต่างจาก notebook:

- **Node เป็น function ภายใน method** `check_next_rule` ถูกนิยามภายใน `_build_graph()` จึงใช้ `self` ได้ (เรียก `self.ask` และเขียน `self.audit`) โดยไม่ต้องส่งเข้าไปเป็น argument function แบบนี้เรียกว่า closure
- **ค่าสามสถานะ** `complies` เป็นได้ `True` (ผ่าน), `False` (ไม่ผ่าน) และ `None` (ตรวจไม่ได้) Type hint ของ state จึงเขียนว่า `dict[str, bool | None]`
- **บันทึกทุกการตรวจ** ทั้งที่ผ่าน ไม่ผ่าน และตรวจไม่ได้ ลง `self.audit`

### 3.6 จาก `None` สู่ "unchecked"

```python
    def plan(self, cid: str) -> dict:
        final = self.graph.invoke({"contract_id": cid}, {"recursion_limit": 30})
        checks = final["checks"]
        return {"violations": sorted(r for r, ok in checks.items() if ok is False),
                "unchecked": sorted(r for r, ok in checks.items() if ok is None)}
```

ใช้ `ok is False` และ `ok is None` ไม่ใช่ `not ok` เพราะ `not None` ก็เป็นจริงเช่นกัน ถ้าเขียน `not ok` กฎที่ตรวจไม่ได้จะถูกนับเป็นการฝ่าฝืน ซึ่งผิดอีกทางหนึ่ง กฎที่ตรวจไม่ได้จึงแยกเป็นรายการของตัวเอง และแสดงบนจอให้คนเห็น

### 3.7 เลือกรูปแบบด้วยชื่อ

```python
                result = getattr(reviewer, pattern)(cid)
```

`getattr(reviewer, "plan")` คืน method `reviewer.plan` เหมือนเขียน `reviewer.plan` ตรงๆ แต่ชื่อมาจากตัวแปร บรรทัดเดียวนี้จึงเรียก `single`, `reflect` หรือ `plan` ได้ตามที่ผู้ใช้เลือกใน `--pattern` โดยไม่ต้องเขียน `if` สามชั้น ชื่อใน `choices` ของ `--pattern` ต้องตรงกับชื่อ method ทุกตัว

### 3.8 `--show-graph`

```python
    if args.show_graph:
        print(reviewer.graph.get_graph().draw_mermaid())
        return 0
```

LangGraph แปลง graph เป็นข้อความรูปแบบ Mermaid ได้ นำไปวางใน <https://mermaid.live> แล้วจะเห็นเป็นภาพ การดู graph ช่วยตรวจว่าเส้นทางที่เขียนไว้ตรงกับที่ตั้งใจหรือไม่ เส้นประในภาพคือ conditional edge

## 4. `checks.csv` หน้าตาเป็นอย่างไร

หลังรัน Plan-and-Execute แต่ละแถวคือการตรวจกฎหนึ่งข้อ (ตัวอย่างจากการรันจริง ตัดให้สั้นลง):

| contract | rule | complies | reasoning |
|---|---|---|---|
| c1 | R2 | False | ข้อ 5 กำหนดแจ้งล่วงหน้า 15 วัน น้อยกว่า 30 วันที่กฎกำหนด |
| c1 | R3 | False | มูลค่า 540,000 บาท เกิน 500,000 แต่ผู้ลงนามเป็นผู้จัดการ ไม่ใช่กรรมการ |
| c3 | R8 | False | รับประกัน 6 เดือน น้อยกว่า 12 เดือนที่กฎกำหนด |
| c5 | R2 | True | แจ้งล่วงหน้า 45 วัน มากกว่า 30 วัน |

คอลัมน์ `reasoning` จริงเป็นภาษาอังกฤษตามที่ model เขียน ตารางนี้แปลให้อ่านง่าย

## 5. ส่วนที่เหมือน notebook

Schema ทั้งหมด, `plan_rules()`, คำสั่งของผู้ตรวจใน Reflection, โครงของ graph (`extract_facts` → `make_plan` → `check_next_rule` วนซ้ำ) และการให้คะแนนด้วย precision, recall, F1

## 6. ลองแก้เอง

1. เพิ่มกฎ R9 ใน `data/policy.json` เช่น "สัญญาที่ยาวเกิน 12 เดือนต้องมีข้อทบทวนราคา" แล้วแก้ `Facts` และ `plan_rules()` ให้รองรับ คุณต้องเพิ่ม field อะไรใน `Facts`
2. เพิ่มคอลัมน์ `reasons` ใน `findings.csv` ที่รวมเหตุผลของกฎที่ไม่ผ่าน เพื่อให้คนอ่านไฟล์เดียวแล้วเข้าใจ
3. ตอนนี้กฎที่ตรวจไม่ได้ไม่ถูกนับในคะแนน เปลี่ยนให้นับเป็นการฝ่าฝืน (fail closed) แล้วดูว่า precision กับ recall เปลี่ยนอย่างไร แบบไหนเหมาะกับงานตรวจสัญญามากกว่า
4. รัน `--pattern all --contracts c3` แล้วเทียบว่าแต่ละรูปแบบตัดสิน c3 อย่างไร

## 7. คำศัพท์

| คำ | ความหมาย |
|---|---|
| Audit trail | บันทึกที่ตรวจย้อนได้ว่าระบบตัดสินอะไร เมื่อไร และเพราะอะไร |
| Fail safe | เมื่อทำงานไม่สำเร็จ ให้ผลออกมาในทางที่ปลอดภัย ที่นี่คือส่งให้คนตรวจ |
| Fail closed | เมื่อไม่แน่ใจ ให้ถือว่าไม่ผ่าน |
| Closure | Function ที่นิยามภายในอีก function และใช้ตัวแปรของ function ด้านนอกได้ |
| `getattr` | ดึง attribute หรือ method ของ object ด้วยชื่อที่เป็นข้อความ |
| Mermaid | ภาษาข้อความสำหรับวาดแผนภาพ เช่น flowchart |
| Precision / recall | สิ่งที่รายงานถูกกี่ส่วน / สิ่งที่ผิดจริงถูกพบกี่ส่วน |
