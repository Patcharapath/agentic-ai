# Agentic AI Labs (DS660)

Coding lab ของรายวิชา Agentic AI ใช้ LangChain และ LangGraph กับ local model ผ่าน Ollama เป็นหลัก
Coding labs for the Agentic AI course, built on LangChain and LangGraph with a local model through Ollama as the main route.

## เริ่มต้น / Quick start

ต้องมีก่อน / You need first: [VS Code](https://code.visualstudio.com/download) หรือ / or [Antigravity IDE](https://antigravity.google/download), [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/), [Ollama](https://ollama.com/download)

```bash
git clone https://github.com/VRU-AI-SWU/agentic-ai.git
cd agentic-ai
uv sync
ollama pull qwen3.5:4b
uv run python lab-00-setup/check_setup.py
```

คู่มือฉบับเต็มของ Lab 0 (ไทย/อังกฤษ, macOS/Windows, VS Code/Antigravity) อยู่ที่ `lab-00-setup/index.html` เปิดด้วย browser หลัง clone
The full Lab 0 guide (Thai/English, macOS/Windows, VS Code/Antigravity) is `lab-00-setup/index.html`; open it in a browser after cloning.

ก่อนเข้า class ทุกครั้ง / Before every class:

```bash
git pull
uv sync
```

บันทึก notebook ที่คุณแก้เป็นชื่อที่ลงท้ายด้วย `.mine.ipynb` เพื่อไม่ให้ `git pull` ชนกับงานของคุณ
Save notebooks you edit under a name ending in `.mine.ipynb` so `git pull` never collides with your work.

## โครงสร้าง / Layout

| Path | เนื้อหา / Contents |
|---|---|
| `lab-XX-*/index.html` | คู่มือ lab สลับภาษาได้ / Lab guide with a language toggle |
| `lab-XX-*/*.ipynb` | Notebook ฉบับ `.th` และ `.en` (code เหมือนกัน) / `.th` and `.en` notebooks (same code) |
| `agentlab/` | Code ที่ทุก lab ใช้ร่วมกัน เช่น `get_llm()` / Helpers shared by all labs |
| `.env.example` | แม่แบบการตั้งค่า คัดลอกเป็น `.env` / Settings template; copy to `.env` |

## ความปลอดภัยของข้อมูล / Data safety

อย่า commit ไฟล์ `.env` และอย่าส่งเอกสารจริงขององค์กรหรือข้อมูลส่วนบุคคลไปยัง free API ให้ใช้ local model แทน
Never commit `.env`, and never send real company documents or personal data to a free API; use the local model.
