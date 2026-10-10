# Lab 0 · เตรียมเครื่องและเรียก LLM ครั้งแรก

คู่มือฉบับเต็มคือ `index.html` ในโฟลเดอร์นี้ (เปิดด้วย browser) หน้านี้สรุปวิธีรันบน terminal

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `index.html` | คู่มือ lab สลับภาษาและระบบปฏิบัติการได้ |
| `check_setup.py` | ตรวจว่าเครื่องพร้อม |
| `hello_llm.th.ipynb`, `hello_llm.en.ipynb` | Notebook สำหรับทำความเข้าใจทีละขั้น |
| `hello_llm.py` | โปรแกรมที่รันจริงจาก terminal |
| `hello_llm.th.md`, `hello_llm.en.md` | อธิบาย `hello_llm.py` ทีละส่วน: อะไรเพิ่มจาก notebook และเพิ่มมาเพื่ออะไร |

## รันบน terminal

เปิด terminal ในโฟลเดอร์ `agentic-ai` (โฟลเดอร์ที่มี `pyproject.toml`) แล้วรัน:

```bash
uv run python lab-00-setup/check_setup.py
uv run python lab-00-setup/hello_llm.py "ใบกำกับภาษีต่างจากใบเสร็จรับเงินอย่างไร"
uv run python lab-00-setup/hello_llm.py --file data/inbox/doc_01.txt "ยอดรวมเท่าไร และต้องชำระภายในกี่วัน"
```

ถ้าเครื่องไม่มี uv ให้เปลี่ยน `uv run python` เป็น `.venv/bin/python` (macOS) หรือ `.venv\Scripts\python` (Windows)

| ตัวเลือกของ `hello_llm.py` | ทำอะไร |
|---|---|
| `--file PATH` | แนบไฟล์ข้อความให้ model อ่านก่อนตอบ |
| `--out PATH` | บันทึกคำตอบลงไฟล์ด้วย |
| `--provider NAME` | ใช้ `ollama`, `openrouter`, `groq` หรือ `google` แทนค่าใน `.env` |
| `--temperature N` | 0 คือคำตอบคงเส้นคงวา (ค่าเริ่มต้น) |
| `--keep-loaded` | ไม่คืน RAM หลังจบ |
| `--help` | แสดงตัวเลือกทั้งหมด |

กด `Ctrl+C` เพื่อหยุดโปรแกรม

<details>
<summary>English</summary>

The full guide is `index.html` in this folder (open it in a browser). This page summarises how to run things from a terminal.

Open a terminal in the `agentic-ai` folder (the one containing `pyproject.toml`) and run:

```bash
uv run python lab-00-setup/check_setup.py
uv run python lab-00-setup/hello_llm.py "How is a tax invoice different from a receipt?"
uv run python lab-00-setup/hello_llm.py --file data/inbox/doc_01.txt "What is the total, and how many days until it is due?"
```

Without uv, replace `uv run python` with `.venv/bin/python` (macOS) or `.venv\Scripts\python` (Windows).

`hello_llm.en.md` explains the program part by part: what was added to the notebook and why.

Options of `hello_llm.py`: `--file PATH` gives the model a text file to read, `--out PATH` also saves the answer, `--provider NAME` overrides `.env`, `--temperature N` (0 is the default), `--keep-loaded` keeps the model in RAM, `--help` lists everything. Press `Ctrl+C` to stop.

</details>
