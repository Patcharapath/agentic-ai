# `invoice_agent.py` อธิบายทีละส่วน

อ่านเอกสารนี้หลังทำ notebook `lab2_tool_agent` จบแล้ว เพราะ `invoice_agent.py` มีคำตอบของ `# TODO` อยู่ เปิดไฟล์ `invoice_agent.py` ไว้ข้างๆ แล้วอ่านไปพร้อมกัน

เรื่องที่อธิบายไปแล้วใน lab ก่อนหน้าจะไม่อธิบายซ้ำ:

- `parse_args()`, `main()`, `try` / `except`, stdout กับ stderr, exit code: ดู `lab-00-setup/hello_llm.th.md`
- State ที่บันทึกลงไฟล์, logging, การเขียน CSV, การข้ามงานที่ทำแล้ว: ดู `lab-01-agent-foundations/inbox_app.th.md`

## 1. ภาพรวม: อะไรย้ายมาจาก notebook และอะไรเพิ่มเข้ามา

| ใน notebook | ใน `invoice_agent.py` | เปลี่ยนอย่างไร |
|---|---|---|
| Tools 4 ตัวจาก `agentlab.invoices` | ตัวเดิม | เหมือนเดิม |
| `run_tool()` ฉบับส่วนที่ 5.2 | `run_tool()` | เหมือนเดิม |
| `run_agent()` ส่วนที่ 3 | `Checker.run_agent()` | **เพิ่ม:** หยุดเมื่อ model เรียกซ้ำ และเขียน trace |
| `check_with_workflow()` ส่วนที่ 6.2 | `Checker.run_workflow()` | เหมือนเดิม |
| `show_trace()` พิมพ์บนจอ | `Checker.trace()` เขียนลงไฟล์ | **ใหม่:** trace อยู่บนดิสก์ |
| เชื่อว่า agent บันทึกผลแล้ว | `Checker.check()` ตรวจฐานข้อมูล | **ใหม่:** ถ้าไม่มีผลให้บันทึก `needs_review` |
| `create_database(reset=True)` ทุกครั้ง | ข้ามใบที่ตรวจแล้ว ล้างเฉพาะเมื่อใส่ `--reset` | **ใหม่:** รันต่อจากที่ค้างได้ |
| `evaluate_checks()` | `score()` | คิดแบบเดิม ทำเมื่อมีไฟล์เฉลย |

## 2. ทำไมต้องเพิ่ม: ปัญหา 3 ข้อของ agent loop ที่รันจริง

1. **Loop ที่ไม่มีขีดจำกัดอาจไม่จบ** Model ที่สับสนอาจเรียก tool เดิมด้วย argument เดิมซ้ำไปเรื่อยๆ ใน notebook คุณกด Interrupt ได้ โปรแกรมที่รันตอนกลางคืนไม่มีใครกด
2. **Agent บอกว่าเสร็จ ไม่ได้แปลว่าเสร็จ** Model อาจตอบว่า "ปฏิเสธใบนี้แล้ว" โดยไม่ได้เรียก `record_result` จริง (คุณเห็นแล้วใน lecture ว่า tools รุ่นแรกทำให้เกิดเรื่องนี้ครึ่งหนึ่งของใบแจ้งหนี้) ถ้าโปรแกรมเชื่อคำตอบ ใบแจ้งหนี้นั้นจะหายไปจากระบบโดยไม่มีใครรู้
3. **ผลผิดต้องตรวจย้อนได้** เมื่อพนักงานบัญชีถามว่า "ทำไมใบนี้ถูกปฏิเสธ" คำตอบต้องอยู่ในไฟล์ ไม่ใช่อยู่บนจอที่ปิดไปแล้ว

## 3. ส่วนที่เพิ่มมา ทีละส่วน

### 3.1 ชี้ tools ที่ใช้ร่วมกันไปที่โฟลเดอร์และฐานข้อมูลของรอบนี้

```python
    # Point the shared tools at this run's folder and database.
    invoices.INVOICE_DIR = args.folder.resolve()
    invoices.DB_PATH = args.out / "procurement.db"
    invoices.create_database(reset=args.reset)
```

Tools ใน `agentlab/invoices.py` อ่านค่า `INVOICE_DIR` และ `DB_PATH` ของ module ทุกครั้งที่ถูกเรียก ไม่ได้จำค่าไว้ตอน import โปรแกรมจึงเปลี่ยนสองค่านี้ได้ก่อนเริ่มงาน แล้ว tools ทุกตัวจะใช้โฟลเดอร์และฐานข้อมูลใหม่ทันที โดยไม่ต้องแก้ code ของ tool

นี่คือเหตุผลที่บรรทัดบนสุดของไฟล์เขียนว่า `from agentlab import invoices` (import ทั้ง module) ไม่ใช่ import แค่ตัวแปร ถ้าเขียน `from agentlab.invoices import DB_PATH` เราจะได้สำเนาของค่า และการเปลี่ยนสำเนาไม่มีผลกับ tools

### 3.2 `run_tool()`: tool ที่ล้มเหลวต้องไม่ทำให้ loop พัง

```python
def run_tool(call: dict, tools_by_name: dict) -> str:
    """Run one tool call. Problems become a message for the model instead of a crash."""
    tool = tools_by_name.get(call["name"])
    if tool is None:
        return json.dumps({"error": f"There is no tool called {call['name']}. Available tools: {sorted(tools_by_name)}"})
    try:
        return tool.invoke(call["args"])
    except Exception as error:
        return json.dumps({"error": f"{type(error).__name__}: {error}"})
```

นี่คือคำตอบของส่วนที่ 5.2 ใน notebook ย้ายมาตามเดิม จุดสำคัญคือ error กลายเป็น **ข้อมูลที่ส่งกลับไปให้ model** ไม่ใช่สิ่งที่หยุดโปรแกรม Model จึงมีโอกาสแก้เอง เช่น เมื่อได้ยินว่าไม่มี tool ชื่อนั้น มันเห็นรายชื่อ tool ที่มีอยู่จริงและเลือกใหม่ได้

`tools_by_name.get(...)` คืน `None` เมื่อไม่มี key แทนการ raise `KeyError` เหมือน `tools_by_name[...]`

### 3.3 `Checker.trace()`: บันทึกทุกเหตุการณ์ลงไฟล์

```python
    def trace(self, filename: str, kind: str, **data) -> None:
        """Append one event to the trace file, and print it with --trace."""
        event = {"time": datetime.now().isoformat(timespec="seconds"), "file": filename, "event": kind, **data}
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

ไฟล์ `traces.jsonl` เป็นรูปแบบ **JSON Lines**: แต่ละบรรทัดคือ JSON หนึ่งก้อนที่สมบูรณ์ในตัวเอง ต่างจาก JSON ธรรมดาที่ทั้งไฟล์เป็นก้อนเดียว ข้อดีคือ:

- เขียนต่อท้ายได้เรื่อยๆ ด้วยโหมด `"a"` (append) โดยไม่ต้องอ่านไฟล์เดิม
- ถ้าโปรแกรมหยุดกลางคัน บรรทัดที่เขียนไปแล้วยังอ่านได้ครบ
- อ่านกลับด้วย pandas ได้ในบรรทัดเดียว: `pd.read_json("out/traces.jsonl", lines=True)`

`**data` รับ argument ที่มีชื่อกี่ตัวก็ได้ เช่น `self.trace(filename, "call", tool=..., args=..., result=...)` แล้วรวมเข้าไปใน dict ของเหตุการณ์ด้วย `**data` อีกครั้ง

### 3.4 `Checker.run_agent()`: loop ที่มีขีดจำกัด

```python
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
```

โครงเหมือน `run_agent` ใน notebook ทุกบรรทัด เพิ่มขีดจำกัดสองชั้น:

| ขีดจำกัด | กันอะไร |
|---|---|
| `for _ in range(self.max_steps)` | กันไม่ให้ loop ยาวเกินจำนวนรอบที่กำหนด ไม่ว่าเหตุผลอะไร |
| `seen_calls` | หยุดทันทีเมื่อ model เรียก tool เดิมด้วย argument เดิมซ้ำ ซึ่งแทบทุกครั้งแปลว่ามันหลงทาง |

ทำไม key ต้องใช้ `json.dumps(call["args"], sort_keys=True)`: argument เป็น dict ซึ่งใส่ใน `set` ไม่ได้ (dict เปลี่ยนค่าได้ Python จึงไม่ให้ใช้เป็นสมาชิกของ set) เราจึงแปลงเป็นข้อความก่อน และ `sort_keys=True` ทำให้ `{"a": 1, "b": 2}` กับ `{"b": 2, "a": 1}` ได้ข้อความเดียวกัน

### 3.5 `Checker.check()`: งานยังไม่เสร็จจนกว่าผลจะถูกบันทึก

```python
    def check(self, filename: str) -> str:
        answer = self.run_agent(filename) if self.mode == "agent" else self.run_workflow(filename)
        if verdict_for(filename) is None:  # the job is not done until a verdict is saved
            save_needs_review(filename, f"agent finished without saving a verdict ({answer[:80]})")
        return answer
```

นี่คือคำตอบของปัญหาข้อ 2 หลังจาก agent จบ โปรแกรม **ตรวจผลในโลกจริง** (ฐานข้อมูล) ไม่ได้เชื่อคำตอบของ model ถ้าไม่มีผลอยู่ในฐานข้อมูล แปลว่า agent ไม่ได้เรียก `record_result` หรือถูกหยุดก่อน โปรแกรมจึงบันทึก `needs_review` เพื่อให้คนเห็นและตามต่อ

หลักการนี้ใช้ได้กับ agent ทุกตัว: ตรวจผลของ action ที่ต้องเกิดขึ้น ไม่ใช่ตรวจข้อความที่ agent พูด

### 3.6 SQL กับเครื่องหมาย `?`

```python
def verdict_for(filename: str) -> dict | None:
    rows = invoices.query("SELECT * FROM invoice_checks WHERE file = ?", (filename,))
    return rows[0] if rows else None
```

ค่าที่มาจากภายนอก (ชื่อไฟล์ ข้อความจาก model) ต้องส่งเข้า SQL ผ่านเครื่องหมาย `?` เสมอ อย่าต่อเป็นข้อความด้วย f-string แบบ `f"... WHERE file = '{filename}'"` เพราะถ้าชื่อไฟล์มีเครื่องหมาย `'` อยู่ คำสั่ง SQL จะเปลี่ยนความหมาย ซึ่งเรียกว่า SQL injection ส่วน `(filename,)` ที่มีจุลภาคท้ายคือ tuple ที่มีสมาชิกตัวเดียว

### 3.7 `Checker.run_workflow()` และ `--mode`

Code เดียวกับส่วนที่ 6.2 ของ notebook ที่ย้ายมาอยู่ใน class เดียวกับ agent ทำให้เปรียบเทียบสองแบบได้ด้วยคำสั่งเดียว:

```bash
uv run python lab-02-tool-use/invoice_agent.py --reset
uv run python lab-02-tool-use/invoice_agent.py --reset --mode workflow
```

`__init__` สร้าง model เฉพาะในโหมด agent:

```python
        self.model = get_llm().bind_tools(TOOLS) if mode == "agent" else None
```

โหมด workflow จึงรันได้แม้ไม่ได้เปิด Ollama

## 4. `traces.jsonl` หน้าตาเป็นอย่างไร

หลังรันหนึ่งรอบ แต่ละบรรทัดในไฟล์คือหนึ่งเหตุการณ์ (ตัดให้สั้นลง):

```json
{"time": "2026-10-23T20:03:49", "file": "inv_03.pdf", "event": "call", "tool": "check_invoice_total", "args": {"filename": "inv_03.pdf"}, "result": "{\"subtotal\": 48750.0, ... \"total_ok\": true}"}
{"time": "2026-10-23T20:03:49", "file": "inv_03.pdf", "event": "call", "tool": "compare_with_po", "args": {"filename": "inv_03.pdf"}, "result": "{\"po_number\": \"PO-2026-121\", \"matches_po\": false, ...}"}
{"time": "2026-10-23T20:03:52", "file": "inv_03.pdf", "event": "call", "tool": "record_result", "args": {"filename": "inv_03.pdf", "verdict": "reject", "reason": "unit_price"}, "result": "{\"saved\": true, ...}"}
{"time": "2026-10-23T20:03:54", "file": "inv_03.pdf", "event": "answer", "text": "inv_03.pdf: reject unit_price"}
```

สองบรรทัดแรกมีเวลาเดียวกัน เพราะ model ขอเรียกสอง tools พร้อมกันในคำตอบเดียว (parallel tool calls)

## 5. ส่วนที่เหมือน notebook

Tools ทั้ง 4 ตัว, `SYSTEM_PROMPT`, `run_tool()`, โครงของ agent loop และ rules ของ workflow ย้ายมาโดยไม่เปลี่ยน

## 6. ลองแก้เอง

1. เพิ่มตัวเลือก `--provider` ที่ส่งต่อให้ `get_llm()` แล้วลองรันกับ API ที่คุณมี key เทียบเวลาและผลกับ local model
2. ตอนนี้ `seen_calls` หยุดตั้งแต่ครั้งแรกที่เรียกซ้ำ เปลี่ยนให้ยอมให้ซ้ำได้หนึ่งครั้ง แล้วหยุดเมื่อซ้ำครั้งที่สอง
3. เพิ่มคอลัมน์ `llm_calls` ใน `invoice_checks.csv` ให้รู้ว่าแต่ละใบใช้ LLM กี่ครั้ง (ต้องนับแยกต่อใบ)
4. อ่าน `out/traces.jsonl` ด้วย pandas แล้วนับว่าแต่ละ tool ถูกเรียกกี่ครั้ง

## 7. คำศัพท์

| คำ | ความหมาย |
|---|---|
| Trace | บันทึกลำดับเหตุการณ์ของการรันหนึ่งครั้ง ทุก LLM call และ tool call |
| JSON Lines (`.jsonl`) | ไฟล์ที่แต่ละบรรทัดเป็น JSON หนึ่งก้อน เขียนต่อท้ายได้เรื่อยๆ |
| Side effect | ผลที่ tool ทิ้งไว้ในโลกจริง เช่น การบันทึกลงฐานข้อมูล |
| Verification | การตรวจว่าผลที่ต้องการเกิดขึ้นจริง แทนการเชื่อคำบอกของ agent |
| Max steps | ขีดจำกัดจำนวนรอบของ agent loop |
| Loop detection | การตรวจจับว่า agent กำลังทำสิ่งเดิมซ้ำ |
| SQL injection | การโจมตีที่ใส่ข้อความพิเศษเข้าไปเปลี่ยนความหมายของคำสั่ง SQL กันได้ด้วย `?` |
| Module attribute | ตัวแปรระดับ module เช่น `invoices.DB_PATH` เปลี่ยนจากภายนอกได้ |
