# Lab 3 · การวางแผนและการให้เหตุผล

คู่มือฉบับเต็มคือ `index.html` ในโฟลเดอร์นี้ (เปิดด้วย browser) หน้านี้สรุปวิธีรันบน terminal

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `index.html` | คู่มือ lab |
| `lab3_planning.th.ipynb`, `lab3_planning.en.ipynb` | Notebook สำหรับทำความเข้าใจทีละขั้น ทำส่วนนี้ก่อน |
| `contract_review.py` | ตรวจสัญญาทั้งโฟลเดอร์ด้วยรูปแบบที่เลือก พร้อมบันทึกเหตุผลของการตรวจทุกข้อ มีคำตอบของ `# TODO` ใน notebook |
| `contract_review.th.md`, `contract_review.en.md` | อธิบาย `contract_review.py` ทีละส่วน: อะไรเพิ่มจาก notebook และเพิ่มมาเพื่ออะไร |

## รันบน terminal

เปิด terminal ในโฟลเดอร์ `agentic-ai` (โฟลเดอร์ที่มี `pyproject.toml`) อัปเดตก่อน แล้วรันโปรแกรม:

```bash
git pull
uv sync
uv run python lab-03-planning/contract_review.py
```

ถ้าเครื่องไม่มี uv ให้เปลี่ยน `uv sync` เป็น `.venv/bin/python -m pip install -e .` และ `uv run python` เป็น `.venv/bin/python` (บน Windows ใช้ `.venv\Scripts\python`)

ค่าเริ่มต้นคือ Plan-and-Execute กับสัญญา 5 ฉบับใน `data/contracts` ใช้เวลาราว 4–6 นาที แล้วเขียนผลลงใน `out/contract_review/`:

| ไฟล์ผลลัพธ์ | เนื้อหา |
|---|---|
| `findings.csv` | กฎที่ฝ่าฝืนของแต่ละสัญญา แยกตามรูปแบบ |
| `checks.csv` | การตรวจกฎทุกข้อ: ผ่านหรือไม่ และเหตุผลของ model |

| ตัวเลือก | ทำอะไร | ค่าเริ่มต้น |
|---|---|---|
| `FOLDER` | โฟลเดอร์ของสัญญา `.txt` | `data/contracts` |
| `--pattern plan` / `single` / `reflect` / `all` | Plan-and-Execute / ถามครั้งเดียว / ร่างแล้วตรวจ / ทั้งสามแบบ | `plan` |
| `--contracts c1 c5` | ตรวจเฉพาะบางฉบับ | ทุกฉบับ |
| `--out PATH` | โฟลเดอร์สำหรับผลลัพธ์ | `out/contract_review` |
| `--show-graph` | พิมพ์ graph ของ Plan-and-Execute แบบ Mermaid แล้วจบ | |
| `--help` | แสดงตัวเลือกทั้งหมด | |

```bash
uv run python lab-03-planning/contract_review.py --pattern single --contracts c1 c5
uv run python lab-03-planning/contract_review.py --show-graph
```

กด `Ctrl+C` เพื่อหยุด ผลของสัญญาที่ตรวจเสร็จแล้วยังถูกเขียนลงไฟล์

<details>
<summary>English</summary>

The full guide is `index.html` in this folder (open it in a browser). This page summarises how to run things from a terminal. Do the notebook first: `contract_review.py` contains the answers to its `# TODO` items. `contract_review.en.md` explains the program part by part.

Open a terminal in the `agentic-ai` folder (the one containing `pyproject.toml`), update, then run the program:

```bash
git pull
uv sync
uv run python lab-03-planning/contract_review.py
```

Without uv, replace `uv sync` with `.venv/bin/python -m pip install -e .` and `uv run python` with `.venv/bin/python` (on Windows, `.venv\Scripts\python`).

The default is Plan-and-Execute on the 5 contracts in `data/contracts`, taking about 4–6 minutes. It writes `findings.csv` (the rules each contract breaks, by pattern) and `checks.csv` (every rule check with the model's reasoning) to `out/contract_review/`.

Options: `FOLDER` (default `data/contracts`), `--pattern plan|single|reflect|all` (default `plan`), `--contracts c1 c5`, `--out PATH` (default `out/contract_review`), `--show-graph`, `--help`. Press `Ctrl+C` to stop; results for contracts already reviewed are still written.

</details>
