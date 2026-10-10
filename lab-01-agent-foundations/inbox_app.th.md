# `inbox_app.py` อธิบายทีละส่วน

อ่านเอกสารนี้หลังทำ notebook `lab1_inbox_agents` จบแล้ว เพราะ `inbox_app.py` มีคำตอบของ `# TODO` อยู่ครบ เปิดไฟล์ `inbox_app.py` ไว้ข้างๆ แล้วอ่านไปพร้อมกัน

เรื่องพื้นฐานของโปรแกรมที่รันจาก terminal (`parse_args()`, `main()`, `try` / `except`, stdout กับ stderr, exit code) อธิบายไว้แล้วใน `lab-00-setup/hello_llm.th.md` เอกสารนี้อธิบายเฉพาะสิ่งที่ใหม่

## 1. ภาพรวม: อะไรย้ายมาจาก notebook และอะไรเพิ่มเข้ามา

ใน notebook คุณสร้าง agent หลายตัวเพื่อเทียบกัน ในโปรแกรมเหลือ agent ตัวเดียวที่เลือกวิธีทำงานได้ 3 แบบ

| ใน notebook | ใน `inbox_app.py` | เปลี่ยนอย่างไร |
|---|---|---|
| `RULES`, `matching_types()` | `RULES`, `matching_types()` | เหมือนเดิม |
| `SYSTEM`, `FinancialDoc`, `to_iso_date()` | ชื่อเดิม | เหมือนเดิม |
| `CautiousReflexAgent` | `--agent rules` | รวมเข้าเป็นโหมดหนึ่งของ `InboxAgent` |
| `StatefulLLMAgent` | `--agent llm` | รวมเข้าเป็นโหมดหนึ่งของ `InboxAgent` |
| `HybridAgent` | `--agent hybrid` | รวมเข้าเป็นโหมดหนึ่งของ `InboxAgent` |
| `self.seen = set()` | class `State` กับไฟล์ `state.json` | **ใหม่:** state อยู่บนดิสก์ |
| ค่าที่ `act()` คืนเป็นข้อความ | class `Decision` | **ใหม่:** บันทึกเหตุผลและรายละเอียดด้วย |
| `env.run(agent)` | loop ใน `main()` | **ใหม่:** อ่านไฟล์จากโฟลเดอร์ บันทึกหลังทุกฉบับ |
| `summarize(runs)` | `score()` | คิดคะแนนแบบเดิม แต่ทำเฉพาะเมื่อมีไฟล์เฉลย |
| แสดง DataFrame | `write_csv()` | **ใหม่:** ผลอยู่ในไฟล์ที่คนอื่นเปิดได้ |
| `print(...)` | `log.info(...)` | **ใหม่:** ใช้ logging |

## 2. ทำไมต้องเพิ่ม: ปัญหา 3 ข้อที่ notebook ไม่เจอ

1. **โปรแกรมจบแล้วตัวแปรหายหมด** ใน notebook `self.seen` อยู่ใน memory ตลอดที่เปิด notebook ไว้ แต่โปรแกรมเริ่มใหม่จากศูนย์ทุกครั้งที่รัน Invoice ที่ส่งมาซ้ำในสัปดาห์หน้าจะไม่ถูกจับ ถ้าเลขที่ที่เคยเห็นไม่ได้ถูกเก็บลงไฟล์
2. **ไม่มีใครนั่งดูจอ** ใน notebook คุณดูผลใต้ cell โปรแกรมจริงอาจรันตอนกลางคืน คนที่ต้องตรวจจะมาเปิดดูทีหลัง ผลและเหตุผลของทุกการตัดสินใจจึงต้องอยู่ในไฟล์
3. **เอกสารฉบับเดียวต้องไม่ทำให้ทั้งชุดหยุด** ใน notebook ถ้า LLM error cell ก็พังแล้วคุณรันใหม่ โปรแกรมที่ประมวลผล 300 ฉบับจะหยุดที่ฉบับที่ 17 ไม่ได้

ส่วนที่เพิ่มมาเกือบทั้งหมดมีไว้แก้หนึ่งในสามข้อนี้

## 3. ส่วนที่เพิ่มมา ทีละส่วน

### 3.1 `REPO_ROOT`: หาโฟลเดอร์จากตำแหน่งของไฟล์

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
```

`__file__` คือ path ของไฟล์ `inbox_app.py` เอง `.parent` คือโฟลเดอร์ที่มันอยู่ (`lab-01-agent-foundations`) และ `.parent` อีกครั้งคือโฟลเดอร์ `agentic-ai`

ที่ต้องทำแบบนี้เพราะ path แบบ `"data/inbox"` ขึ้นกับว่า terminal อยู่ที่โฟลเดอร์ไหนตอนรัน ถ้ารันจากโฟลเดอร์อื่นจะหาไม่เจอ การคำนวณจากตำแหน่งของไฟล์ทำให้ค่าเริ่มต้นถูกเสมอ

### 3.2 `logging` แทน `print`

```python
log = logging.getLogger("inbox")
```

และใน `main()`:

```python
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per HTTP call is too noisy here
```

`log.info(...)` ทำงานคล้าย `print(...)` แต่ข้อความแต่ละบรรทัดมีระดับความสำคัญ (`INFO`, `WARNING`, `ERROR`) เราจึงเลือกได้ว่าจะแสดงระดับไหน โดยไม่ต้องลบบรรทัดออกจาก code

บรรทัดที่สองเป็นตัวอย่างของประโยชน์นี้: library ที่ใช้เรียก LLM (`httpx`) พิมพ์หนึ่งบรรทัดทุกครั้งที่ส่ง request ซึ่งรกเกินไป เราบอกให้มันแสดงเฉพาะระดับ `WARNING` ขึ้นไป โดยไม่ต้องแก้ code ของ library

### 3.3 class `State`: state ที่ไม่หายเมื่อปิดโปรแกรม

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

นี่คือ `self.seen = set()` จาก notebook ที่โตขึ้น มันเก็บสองอย่าง:

- `decisions` ผลของเอกสารทุกฉบับที่ทำแล้ว ใช้ตอบคำถามว่า "ฉบับนี้ทำไปแล้วหรือยัง"
- `invoice_numbers` เลขที่ invoice ที่เคยรับ คู่กับรหัสของเอกสารฉบับแรกที่มีเลขนั้น ใช้ตอบคำถามว่า "เลขนี้ซ้ำกับฉบับไหน"

| บรรทัด | ทำอะไร |
|---|---|
| `json.loads(...) if path.exists() else {}` | ถ้ามีไฟล์จากรอบก่อนให้อ่านกลับมา ถ้าไม่มีให้เริ่มจากว่าง |
| `data.get("decisions", {})` | หยิบค่าออกมา ถ้าไม่มี key นี้ให้ใช้ `{}` แทนการ error |
| `mkdir(parents=True, exist_ok=True)` | สร้างโฟลเดอร์ปลายทางถ้ายังไม่มี และไม่ error ถ้ามีอยู่แล้ว |
| `ensure_ascii=False` | เขียนภาษาไทยเป็นภาษาไทย ไม่แปลงเป็นรหัส `ก` ที่อ่านไม่ออก |
| `indent=2` | จัดย่อหน้าให้คนเปิดอ่านได้ |

เราเลือก JSON เพราะเปิดอ่านด้วย editor ได้ และ Python แปลง dict เป็น JSON ได้ในบรรทัดเดียว ระบบที่ใหญ่กว่านี้จะใช้ฐานข้อมูล ซึ่งเป็นเรื่องของ Lab 2

### 3.4 class `Decision`: หนึ่งบันทึกต่อหนึ่งเอกสาร

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

ใน notebook `act()` คืนแค่ข้อความเดียว เช่น `"invoice"` คนที่มาตรวจทีหลังต้องการมากกว่านั้น: ทำไมถึงตัดสินแบบนี้ ใครตัดสิน (กฎหรือ LLM) เลขที่เอกสารคืออะไร

`@dataclass` คือวิธีสั้นๆ ในการสร้าง class ที่มีไว้เก็บข้อมูล เราเขียนแค่ชื่อ field กับชนิด Python สร้าง `__init__` ให้เอง ค่าหลัง `=` คือค่าเริ่มต้น จึงสร้างได้ด้วย `Decision(doc_id, "needs_human", reason="...")` โดยไม่ต้องใส่ทุก field

ใน `main()` เราใช้ `asdict(decision)` แปลงเป็น dict เพื่อเก็บลง JSON และเขียนเป็นแถวใน CSV

### 3.5 `InboxAgent.read()`: ใครเป็นคนอ่านเอกสาร

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

Function นี้รวม agent 3 แบบจาก notebook ไว้ในที่เดียว เงื่อนไข `if` ตัดสินว่ากฎจะจัดการเอกสารนี้เองหรือไม่:

| โหมด | กฎจัดการเองเมื่อ | นอกนั้น |
|---|---|---|
| `rules` | ทุกครั้ง | ถ้ากฎไม่แน่ใจ คืน `None` ซึ่งจะกลายเป็น `needs_human` |
| `hybrid` | มีประเภทเดียวที่ตรง และไม่ใช่ invoice | ส่งให้ LLM |
| `llm` | ไม่เคย | ส่งให้ LLM ทุกฉบับ |

Function คืนค่าสองอย่างพร้อมกัน คือผลการอ่านและชื่อของผู้ตัดสิน (`"rules"` หรือ `"llm"`) เพื่อบันทึกลง `Decision` การรู้ว่าใครตัดสินช่วยมากเมื่อต้องหาว่าความผิดพลาดมาจากไหน

### 3.6 `Reading`: ขอ output ให้สั้นที่สุด

```python
    doc_type: Literal["invoice", "receipt", "purchase_order", "contract", "leave_request", "other"]
    doc_no: str | None = Field(description="The document's own number, exactly as printed; null if it has none")
```

Schema นี้เหมือน `Routing` ใน notebook มีแค่สอง field ฉบับแรกของโปรแกรมนี้มี field ที่สามให้ LLM เขียนเหตุผลประกอบ ผลคือรอบเต็ม 24 ฉบับช้าลงจาก 82 เป็น 135 วินาที เพราะ output token คือส่วนที่ช้า (Module 0) เราจึงตัดออก และให้ code เขียนเหตุผลสั้นๆ เอง

บทเรียน: ทุก field ที่ขอจาก LLM มีราคา ขอเฉพาะสิ่งที่จะนำไปใช้

### 3.7 `InboxAgent.decide()`: การตัดสินใจหนึ่งครั้ง พร้อมการรับมือความล้มเหลว

**ส่วนที่ 1: ถ้าอ่านไม่ได้ ให้ส่งคน**

```python
        try:
            reading, decided_by = self.read(text)
        except Exception as error:  # a failed LLM call must not stop the whole run
            return Decision(doc_id, "needs_human", reason=f"could not read the document: {error}"[:200], decided_by="llm")
        if reading is None:
            return Decision(doc_id, "needs_human", reason="no single keyword rule matched", decided_by=decided_by)
```

นี่คือคำตอบของปัญหาข้อ 3 เมื่อ LLM error เราไม่ปล่อยให้โปรแกรมพัง แต่เปลี่ยน error เป็นการตัดสินใจที่ปลอดภัยที่สุด คือ `needs_human` พร้อมบันทึกสาเหตุไว้ `[:200]` ตัดข้อความ error ให้ไม่ยาวเกินไปในไฟล์ CSV

**ส่วนที่ 2: ตรวจ invoice ซ้ำ**

```python
        if reading.doc_type == "invoice" and reading.doc_no:
            first = self.state.invoice_numbers.setdefault(reading.doc_no, doc_id)
            if first != doc_id:
                decision.action = "needs_human"
                decision.reason = f"invoice number {reading.doc_no} was already received in {first}"
```

ใน notebook เราเขียน `if doc_no in self.seen` แล้วตามด้วย `self.seen.add(doc_no)` ที่นี่ใช้ `setdefault` ซึ่งทำสองอย่างในบรรทัดเดียว:

- ถ้าเลขนี้ **ยังไม่มี** ใน dict ให้เก็บไว้คู่กับ `doc_id` ปัจจุบัน แล้วคืน `doc_id` ปัจจุบัน
- ถ้าเลขนี้ **มีแล้ว** ให้คืน `doc_id` ของฉบับแรกที่มีเลขนี้ โดยไม่แก้อะไร

ดังนั้นถ้า `first != doc_id` แปลว่าเลขนี้เคยมาแล้วในเอกสารฉบับอื่น และเรารู้ด้วยว่าฉบับไหน จึงเขียนไว้ในเหตุผลให้คนตรวจเปิดเทียบได้ทันที

**ส่วนที่ 3: ดึงข้อมูล โดยไม่ให้ความล้มเหลวกระทบการจำแนก**

```python
        if self.llm is not None and reading.doc_type in FINANCIAL:
            try:
                for key, value in self.extract(text).items():
                    setattr(decision, key, value)
            except Exception as error:
                decision.reason += f" (fields not extracted: {error})"[:120]
```

การดึงข้อมูลเป็น LLM call ครั้งที่สอง ถ้าครั้งนี้ล้มเหลว การจำแนกที่ทำสำเร็จไปแล้วยังใช้ได้ เราจึงครอบด้วย `try` แยกต่างหาก และแค่จดไว้ในเหตุผลว่าดึงข้อมูลไม่ได้

`setattr(decision, key, value)` เท่ากับเขียน `decision.issue_date = ...`, `decision.total = ...` ทีละบรรทัด แต่ทำใน loop

### 3.8 `write_csv()`: ผลลัพธ์ที่เปิดด้วย Excel ได้

```python
def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel shows Thai correctly
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
```

| สิ่งที่เขียน | ทำไม |
|---|---|
| `encoding="utf-8-sig"` | Excel บน Windows จะแสดงภาษาไทยเพี้ยนถ้าเป็น `utf-8` ธรรมดา `utf-8-sig` ใส่เครื่องหมายต้นไฟล์ที่บอก Excel ว่านี่คือ UTF-8 |
| `newline=""` | กันไม่ให้มีบรรทัดว่างแทรกระหว่างแถวบน Windows |
| `with ... as f:` | ปิดไฟล์ให้เองเมื่อจบ แม้จะเกิด error |
| `extrasaction="ignore"` | แต่ละแถวมี field มากกว่าที่ต้องการเขียน ให้ข้าม field ที่ไม่อยู่ใน `columns` |

### 3.9 `main()`: ลำดับการทำงาน

1. อ่าน argument และตั้งค่า logging
2. ตรวจว่าโฟลเดอร์ที่ให้มามีอยู่จริง ถ้าไม่มีจบด้วย exit code 2
3. โหลด `State` จากไฟล์ (หรือลบก่อนถ้าใส่ `--reset`)
4. หาเอกสารที่ยังไม่ได้ทำ
5. ทำทีละฉบับ และบันทึก state หลังทุกฉบับ
6. คืน RAM ของ model
7. เขียน `routing.csv` และ `extracted.csv`
8. ถ้ามีไฟล์เฉลย ให้คิดคะแนน

**ขั้นที่ 4: ข้ามเอกสารที่ทำแล้ว**

```python
    files = sorted(args.folder.glob("*.txt"))
    pending = [f for f in files if f.stem not in state.decisions]
    new = pending[: args.limit]
```

`glob("*.txt")` หาไฟล์ `.txt` ทั้งหมดในโฟลเดอร์ `f.stem` คือชื่อไฟล์ที่ไม่มีนามสกุล เช่น `doc_01` ซึ่งเราใช้เป็นรหัสเอกสาร บรรทัดที่สองคือเหตุผลที่รันซ้ำแล้วไม่เรียก LLM อีก: เอกสารที่มีผลอยู่ใน state แล้วถูกกรองออก

**ขั้นที่ 5 และ 6: loop หลัก**

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

Loop นี้ทำหน้าที่แทน `env.run(agent)` ใน notebook สามจุดที่ต่างออกไป:

- `state.save()` อยู่ **ใน** loop ไม่ใช่หลัง loop ถ้าไฟดับตอนฉบับที่ 200 งาน 199 ฉบับแรกยังอยู่ และรันใหม่จะทำต่อจากฉบับที่ 200
- `except KeyboardInterrupt` จับการกด Ctrl+C โปรแกรมจึงจบอย่างเรียบร้อยและยังเขียน CSV ของสิ่งที่ทำไปแล้ว
- `finally: release_model()` คืน RAM เสมอ ไม่ว่าจะจบแบบไหน

**ขั้นที่ 8: คิดคะแนนเฉพาะเมื่อมีเฉลย**

```python
    labels = args.folder.parent / f"{args.folder.name}_labels.csv"
    if labels.exists():
        log.info("against %s: %s", labels.name, score(state.decisions, labels))
```

ใน lab เรามีไฟล์เฉลย `data/inbox_labels.csv` แต่เอกสารจริงไม่มีเฉลย โปรแกรมจึงมองหาไฟล์ชื่อเดียวกับโฟลเดอร์ตามด้วย `_labels.csv` ถ้าเจอก็คิดคะแนน ถ้าไม่เจอก็ข้าม

## 4. `state.json` หน้าตาเป็นอย่างไร

หลังรันหนึ่งรอบ เปิด `out/inbox/state.json` จะเห็นโครงแบบนี้ (ย่อให้เหลือสองฉบับ):

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

`doc_14` มี `doc_type` เป็น `invoice` แต่ `action` เป็น `needs_human` สองค่านี้ต่างกันได้: `doc_type` คือสิ่งที่เอกสารเป็น ส่วน `action` คือสิ่งที่ agent ตัดสินใจทำ

## 5. ส่วนที่เหมือน notebook

ส่วนเหล่านี้ย้ายมาโดยไม่เปลี่ยน ถ้าคุณทำ notebook จบแล้วจะคุ้นทันที: รายการ `RULES`, `DOC_NO`, ข้อความ `SYSTEM`, schema `FinancialDoc`, ตาราง `MONTHS`, function `to_iso_date()` และ `matching_types()`

## 6. ลองแก้เอง

1. เพิ่มประเภทเอกสาร `quotation` (ใบเสนอราคา) คุณต้องแก้กี่ที่ ลองไล่ดู: `RULES`, `SYSTEM`, `Reading` แล้วรันด้วย `--reset` เพื่อดูว่า `doc_23` ถูกจัดอย่างไร
2. เพิ่มตัวเลือก `--verbose` ที่ตั้งระดับ logging เป็น `DEBUG` แล้วเพิ่ม `log.debug(...)` ใน `read()` ให้บอกว่ากฎข้อไหนตรง
3. ตอนนี้ตรวจซ้ำเฉพาะ invoice ขยายให้ตรวจใบเสร็จและใบสั่งซื้อด้วย คุณต้องเปลี่ยนชื่อ `invoice_numbers` หรือไม่ และ state เก่าที่บันทึกไว้แล้วจะยังใช้ได้หรือไม่
4. สร้างโฟลเดอร์ใหม่ที่มีไฟล์ `.txt` ของคุณเอง 3–4 ไฟล์ แล้วรันด้วย `uv run python lab-01-agent-foundations/inbox_app.py โฟลเดอร์ของคุณ --out out/mine`

## 7. คำศัพท์

| คำ | ความหมาย |
|---|---|
| State | ข้อมูลที่โปรแกรมต้องจำข้ามขั้นตอนหรือข้ามการรัน |
| Persist | เก็บข้อมูลลงดิสก์เพื่อให้อยู่รอดหลังโปรแกรมจบ |
| JSON | รูปแบบไฟล์ข้อความสำหรับเก็บ dict และ list อ่านได้ทั้งคนและโปรแกรม |
| CSV | ไฟล์ตารางที่คั่นค่าด้วยจุลภาค เปิดด้วย Excel ได้ |
| Dataclass | class ที่มีไว้เก็บข้อมูล สร้างด้วย `@dataclass` |
| Logging | การพิมพ์ข้อความแบบมีระดับความสำคัญ เปิดปิดได้โดยไม่แก้ code |
| Idempotent | รันซ้ำกี่ครั้งก็ได้ผลเดิม โปรแกรมนี้ข้ามเอกสารที่ทำแล้วจึงรันซ้ำได้อย่างปลอดภัย |
| Fallback | สิ่งที่ทำเมื่อวิธีหลักล้มเหลว ที่นี่คือส่งเอกสารให้คน |
