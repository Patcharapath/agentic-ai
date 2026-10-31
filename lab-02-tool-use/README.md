# Lab 2 · Tools และ agent loop

คู่มือฉบับเต็มคือ `index.html` ในโฟลเดอร์นี้ (เปิดด้วย browser) หน้านี้สรุปวิธีรันบน terminal

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `index.html` | คู่มือ lab |
| `lab2_tool_agent.th.ipynb`, `lab2_tool_agent.en.ipynb` | Notebook สำหรับทำความเข้าใจทีละขั้น ทำส่วนนี้ก่อน |
| `lab2_tool_agent.solution.th.ipynb`, `lab2_tool_agent.solution.ipynb` | เฉลยของ `# TODO` พร้อมคำอธิบายว่าทำไมเขียนแบบนี้ (ไทย, อังกฤษ) ลองทำเองก่อนค่อยเปิดดู |
| `invoice_agent.py` | Agent ตัวเดียวกันที่เขียนเป็นโปรแกรมสำหรับรันจริง มีคำตอบของ `# TODO` ใน notebook |
| `invoice_agent.th.md`, `invoice_agent.en.md` | อธิบาย `invoice_agent.py` ทีละส่วน: อะไรเพิ่มจาก notebook และเพิ่มมาเพื่ออะไร |
| `mcp_server.py` | ให้บริการ tools ผ่าน MCP ใช้ในส่วน Stretch ของ notebook |

## รันบน terminal

เปิด terminal ในโฟลเดอร์ `agentic-ai` (โฟลเดอร์ที่มี `pyproject.toml`) อัปเดตก่อน แล้วรันโปรแกรม:

```bash
git pull
uv sync
uv run python lab-02-tool-use/invoice_agent.py --trace
```

ถ้าเครื่องไม่มี uv ให้เปลี่ยน `uv sync` เป็น `.venv/bin/python -m pip install -e .` และ `uv run python` เป็น `.venv/bin/python` (บน Windows ใช้ `.venv\Scripts\python`)

โปรแกรมตรวจใบแจ้งหนี้ PDF 8 ฉบับใน `data/invoices` ใช้เวลาราว 1–3 นาที แล้วเขียนผลลงใน `out/`:

| ไฟล์ผลลัพธ์ | เนื้อหา |
|---|---|
| `procurement.db` | ฐานข้อมูล SQLite: ใบสั่งซื้อ และผลการตรวจในตาราง `invoice_checks` |
| `invoice_checks.csv` | ผลการตรวจทุกฉบับ |
| `traces.jsonl` | ทุก tool call และผลลัพธ์ บรรทัดละหนึ่งเหตุการณ์ |

| ตัวเลือก | ทำอะไร | ค่าเริ่มต้น |
|---|---|---|
| `FOLDER` | โฟลเดอร์ของใบแจ้งหนี้ PDF | `data/invoices` |
| `--mode agent` / `workflow` | LLM เลือก tools เอง / เรียกตามลำดับตายตัว ไม่ใช้ LLM | `agent` |
| `--max-steps N` | จำนวน LLM call สูงสุดต่อใบแจ้งหนี้ | 8 |
| `--trace` | แสดงทุก tool call บนจอ | |
| `--out PATH` | โฟลเดอร์สำหรับฐานข้อมูล CSV และ trace | `out` |
| `--limit N` | ตรวจใบแจ้งหนี้ใหม่ไม่เกิน N ฉบับ | ทั้งหมด |
| `--reset` | เริ่มจากฐานข้อมูลใหม่ | |
| `--help` | แสดงตัวเลือกทั้งหมด | |

```bash
uv run python lab-02-tool-use/invoice_agent.py --reset --mode workflow
uv run python lab-02-tool-use/invoice_agent.py --reset --max-steps 1 --limit 3
```

รันคำสั่งเดิมซ้ำ โปรแกรมจะข้ามใบที่ตรวจแล้ว กด `Ctrl+C` เพื่อหยุด แล้วรันใหม่เพื่อทำต่อจากที่ค้าง

<details>
<summary>English</summary>

The full guide is `index.html` in this folder (open it in a browser). This page summarises how to run things from a terminal. Do the notebook first: `invoice_agent.py` contains the answers to its `# TODO` items. `invoice_agent.en.md` explains the program part by part, and `mcp_server.py` serves the tools over MCP for the notebook's Stretch part. Answers to the `# TODO` items, with explanations of why they are written that way, are in `lab2_tool_agent.solution.ipynb` (Thai: `lab2_tool_agent.solution.th.ipynb`). Try them yourself first.

Open a terminal in the `agentic-ai` folder (the one containing `pyproject.toml`), update, then run the program:

```bash
git pull
uv sync
uv run python lab-02-tool-use/invoice_agent.py --trace
```

Without uv, replace `uv sync` with `.venv/bin/python -m pip install -e .` and `uv run python` with `.venv/bin/python` (on Windows, `.venv\Scripts\python`).

The program checks the 8 PDF invoices in `data/invoices` in about 1–3 minutes and writes `procurement.db` (purchase orders and the results in `invoice_checks`), `invoice_checks.csv` and `traces.jsonl` (every tool call and result) to `out/`.

Options: `FOLDER` (default `data/invoices`), `--mode agent|workflow` (default `agent`), `--max-steps N` (default 8), `--trace`, `--out PATH` (default `out`), `--limit N`, `--reset`, `--help`.

Running the same command again skips invoices already checked. Press `Ctrl+C` to stop, and run again to continue where it left off.

</details>
