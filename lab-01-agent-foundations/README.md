# Lab 1 · Agent สี่แบบใน environment เดียวกัน

คู่มือฉบับเต็มคือ `index.html` ในโฟลเดอร์นี้ (เปิดด้วย browser) หน้านี้สรุปวิธีรันบน terminal

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `index.html` | คู่มือ lab |
| `lab1_inbox_agents.th.ipynb`, `lab1_inbox_agents.en.ipynb` | Notebook สำหรับทำความเข้าใจทีละขั้น ทำส่วนนี้ก่อน |
| `inbox_app.py` | Agent ตัวเดียวกันที่เขียนเป็นโปรแกรมสำหรับรันจริง มีคำตอบของ `# TODO` ใน notebook |
| `inbox_app.th.md`, `inbox_app.en.md` | อธิบาย `inbox_app.py` ทีละส่วน: อะไรเพิ่มจาก notebook และเพิ่มมาเพื่ออะไร |

## รันบน terminal

เปิด terminal ในโฟลเดอร์ `agentic-ai` (โฟลเดอร์ที่มี `pyproject.toml`) อัปเดตก่อน แล้วรันโปรแกรม:

```bash
git pull
uv sync
uv run python lab-01-agent-foundations/inbox_app.py
```

ถ้าเครื่องไม่มี uv ให้เปลี่ยน `uv sync` เป็น `.venv/bin/python -m pip install -e .` และ `uv run python` เป็น `.venv/bin/python` (บน Windows ใช้ `.venv\Scripts\python`)

โปรแกรมประมวลผลเอกสาร 24 ฉบับใน `data/inbox` ใช้เวลาราว 1–3 นาที แล้วเขียนผลลงใน `out/inbox/`:

| ไฟล์ผลลัพธ์ | เนื้อหา |
|---|---|
| `routing.csv` | การตัดสินใจของทุกเอกสารพร้อมเหตุผล |
| `extracted.csv` | เลขที่ วันที่ ยอดรวม และสกุลเงินของเอกสารการเงิน |
| `state.json` | เอกสารที่ทำแล้ว และเลขที่ invoice ที่เคยรับ |

| ตัวเลือก | ทำอะไร | ค่าเริ่มต้น |
|---|---|---|
| `FOLDER` | โฟลเดอร์ของไฟล์ `.txt` ที่จะประมวลผล | `data/inbox` |
| `--agent llm` / `hybrid` / `rules` | LLM อ่านทุกฉบับ / กฎก่อนแล้ว LLM เมื่อไม่แน่ใจ / กฎอย่างเดียว | `llm` |
| `--out PATH` | โฟลเดอร์สำหรับผลลัพธ์และ state | `out/inbox` |
| `--limit N` | ประมวลผลเอกสารใหม่ไม่เกิน N ฉบับ | ทั้งหมด |
| `--reset` | ลบ state ของรอบก่อนแล้วเริ่มใหม่ | |
| `--help` | แสดงตัวเลือกทั้งหมด | |

```bash
uv run python lab-01-agent-foundations/inbox_app.py --agent hybrid --limit 8 --out out/hybrid-test
uv run python lab-01-agent-foundations/inbox_app.py --reset --agent rules
```

รันคำสั่งเดิมซ้ำ โปรแกรมจะข้ามเอกสารที่ทำแล้ว กด `Ctrl+C` เพื่อหยุด แล้วรันใหม่เพื่อทำต่อจากที่ค้าง

<details>
<summary>English</summary>

The full guide is `index.html` in this folder (open it in a browser). This page summarises how to run things from a terminal. Do the notebook first: `inbox_app.py` contains the answers to its `# TODO` items.

Open a terminal in the `agentic-ai` folder (the one containing `pyproject.toml`), update, then run the program:

```bash
git pull
uv sync
uv run python lab-01-agent-foundations/inbox_app.py
```

Without uv, replace `uv sync` with `.venv/bin/python -m pip install -e .` and `uv run python` with `.venv/bin/python` (on Windows, `.venv\Scripts\python`).

The program processes the 24 documents in `data/inbox` in about 1–3 minutes and writes `routing.csv` (every decision with its reason), `extracted.csv` (number, date, total, currency of the financial documents) and `state.json` (documents done and invoice numbers received) to `out/inbox/`.

`inbox_app.en.md` explains the program part by part: what was added to the notebook and why.

Options: `FOLDER` (default `data/inbox`), `--agent llm|hybrid|rules` (default `llm`), `--out PATH` (default `out/inbox`), `--limit N`, `--reset`, `--help`.

Running the same command again skips documents already done. Press `Ctrl+C` to stop, and run again to continue where it left off.

</details>
