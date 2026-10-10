# `hello_llm.py` อธิบายทีละส่วน

เอกสารนี้เขียนสำหรับคนที่เคยเขียน Python ใน notebook แต่ยังไม่เคยเขียนโปรแกรมที่รันจาก terminal เปิดไฟล์ `hello_llm.py` ไว้ข้างๆ แล้วอ่านไปพร้อมกัน

ใน notebook `hello_llm.th.ipynb` code ที่เรียก LLM มีแค่สองบรรทัด:

```python notebook
llm = get_llm()
reply = llm.invoke("อธิบายคำว่า token ในบริบทของ LLM ภายใน 2 ประโยค")
```

ไฟล์ `hello_llm.py` ทำสิ่งเดียวกัน แต่ยาวราว 80 บรรทัด เอกสารนี้อธิบายว่าบรรทัดที่เพิ่มมามีไว้ทำอะไร

## 1. Notebook กับโปรแกรมต่างกันอย่างไร

| | Notebook | โปรแกรม `.py` |
|---|---|---|
| รันอย่างไร | กดรันทีละ cell | พิมพ์คำสั่งเดียวใน terminal รันทั้งไฟล์จากบนลงล่าง |
| เปลี่ยนคำถามอย่างไร | แก้ code ใน cell | ส่งค่าเข้าไปตอนเรียก ไม่ต้องแก้ไฟล์ |
| ผลลัพธ์ไปไหน | แสดงใต้ cell | พิมพ์ออกจอ หรือเขียนลงไฟล์ |
| ถ้าเกิด error | เห็น traceback แล้วแก้ cell นั้น | โปรแกรมต้องบอกเองว่าผิดอะไร เพราะคนรันอาจไม่ใช่คนเขียน |
| ใครเรียกใช้ | คุณคนเดียว | คุณ เพื่อนร่วมงาน หรือโปรแกรมอื่น |
| ตัวแปรระหว่างการรัน | ค้างอยู่ใน memory จนปิด notebook | หายทุกครั้งที่โปรแกรมจบ |

แถวสุดท้ายสำคัญที่สุด และเป็นเหตุผลที่ Lab 1 ต้องบันทึก state ลงไฟล์

## 2. แผนที่ของไฟล์

| ส่วน | ทำหน้าที่ | มีใน notebook หรือไม่ |
|---|---|---|
| ข้อความใน `"""..."""` บนสุด | บอกว่าไฟล์นี้คืออะไรและรันอย่างไร | ไม่มี |
| `import ...` | นำเครื่องมือเข้ามาใช้ | มีบางส่วน |
| `SYSTEM = ...` | คำสั่งที่ให้ model ทุกครั้ง | มี (อยู่ใน cell) |
| `parse_args()` | อ่านค่าที่พิมพ์ตามหลังคำสั่งใน terminal | ไม่มี |
| `build_messages()` | ประกอบ message ที่จะส่งให้ model | มี (เขียนตรงๆ ใน cell) |
| `main()` | ลำดับการทำงานทั้งหมด | ไม่มี (notebook ใช้ลำดับของ cell) |
| `if __name__ == "__main__":` | จุดเริ่มต้นเมื่อรันไฟล์นี้ | ไม่มี |

## 3. ส่วนที่เพิ่มมา ทีละส่วน

### 3.1 ข้อความบนสุดของไฟล์ (docstring)

ข้อความใน `"""..."""` ที่บรรทัดแรกเรียกว่า docstring Python ไม่ได้รันมัน มีไว้ให้คนอ่าน คนที่เปิดไฟล์นี้เป็นครั้งแรกควรรู้ภายใน 10 วินาทีว่าไฟล์นี้ทำอะไรและรันอย่างไร จึงใส่ตัวอย่างคำสั่งไว้ตรงนี้

### 3.2 `import` ไว้บนสุด

```python
import argparse
import sys
import time
from pathlib import Path

from agentlab import PROVIDERS, get_llm, provider_settings, release_model
```

ใน notebook เรามัก `import` ใน cell ที่ต้องใช้ ในโปรแกรมให้รวมไว้บนสุด คนอ่านจะเห็นทันทีว่าไฟล์นี้พึ่งอะไรบ้าง

| สิ่งที่ import | มาจากไหน | ใช้ทำอะไรในไฟล์นี้ |
|---|---|---|
| `argparse` | มากับ Python | อ่านค่าจาก command line |
| `sys` | มากับ Python | พิมพ์ไปที่ stderr และส่ง exit code |
| `time` | มากับ Python | จับเวลา |
| `Path` | มากับ Python | จัดการ path ของไฟล์ ใช้ได้ทั้ง macOS และ Windows |
| `get_llm` และตัวอื่น | โฟลเดอร์ `agentlab` ของวิชา | สร้าง LLM ตามค่าใน `.env` |

กลุ่มแรกคือของที่มากับ Python กลุ่มที่สองคือ code ของเราเอง เว้นบรรทัดคั่นไว้ให้แยกออก

### 3.3 ค่าคงที่เขียนด้วยตัวพิมพ์ใหญ่

```python
SYSTEM = "You are a concise assistant for office document work. Answer in the language of the question."
```

ชื่อตัวพิมพ์ใหญ่ทั้งหมดเป็นข้อตกลงของ Python ว่า "ค่านี้ไม่เปลี่ยนระหว่างรัน" วางไว้บนสุดเพื่อให้หาเจอและแก้ได้ในที่เดียว

### 3.4 `parse_args()`: รับค่าจาก terminal

นี่คือส่วนที่ทำให้ไม่ต้องแก้ code ทุกครั้งที่เปลี่ยนคำถาม เมื่อคุณพิมพ์

```bash
uv run python lab-00-setup/hello_llm.py --file data/inbox/doc_01.txt "ยอดรวมเท่าไร"
```

ทุกอย่างที่อยู่หลังชื่อไฟล์เรียกว่า argument function นี้อ่าน argument เหล่านั้นแล้วคืนเป็น object ที่ใช้ง่าย

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask an LLM one question, optionally about a text file.")
    parser.add_argument("question", help="the question to ask")
    parser.add_argument("--file", type=Path, help="a text file to give the model as context")
    parser.add_argument("--out", type=Path, help="also save the answer to this file (UTF-8)")
    parser.add_argument("--provider", choices=list(PROVIDERS), help="override LLM_PROVIDER from .env")
    parser.add_argument("--temperature", type=float, default=0.0, help="0 = repeatable (default), higher = more varied")
    parser.add_argument("--keep-loaded", action="store_true", help="leave the local model in RAM afterwards")
    return parser.parse_args(argv)
```

อ่านทีละบรรทัด:

| สิ่งที่เขียน | ความหมาย |
|---|---|
| `"question"` (ไม่มี `--`) | Argument ที่ **ต้องใส่** และไม่ต้องพิมพ์ชื่อ |
| `"--file"` (มี `--`) | ตัวเลือกที่ **ไม่ใส่ก็ได้** ต้องพิมพ์ชื่อนำหน้า |
| `type=Path`, `type=float` | แปลงข้อความที่พิมพ์เป็นชนิดที่ต้องการ ถ้าแปลงไม่ได้โปรแกรมแจ้ง error ให้เอง |
| `default=0.0` | ค่าที่ใช้เมื่อไม่ได้ใส่ตัวเลือกนี้ |
| `choices=[...]` | รับเฉพาะค่าในรายการ พิมพ์ผิดจะถูกปฏิเสธพร้อมบอกค่าที่ใช้ได้ |
| `action="store_true"` | ตัวเลือกแบบเปิดปิด ไม่มีค่าตามหลัง ใส่แล้วเป็น `True` |
| `help="..."` | คำอธิบายที่แสดงเมื่อรันด้วย `--help` |

หลังจากนั้นใช้ค่าได้ด้วย `args.question`, `args.file`, `args.temperature` ส่วน `--keep-loaded` กลายเป็น `args.keep_loaded` เพราะชื่อตัวแปรใน Python มีขีดกลางไม่ได้

ลองรัน `uv run python lab-00-setup/hello_llm.py --help` ข้อความช่วยเหลือทั้งหมดถูกสร้างจากบรรทัดเหล่านี้ เราไม่ได้เขียนเอง

### 3.5 `build_messages()`: แยกงานออกเป็น function

```python
def build_messages(question: str, file: Path | None) -> list[tuple[str, str]]:
    """The model sees only what we put here: instructions, the document if any, then the question."""
    if file is None:
        return [("system", SYSTEM), ("user", question)]
    document = file.read_text(encoding="utf-8")
    return [("system", SYSTEM), ("user", f"<document>\n{document}\n</document>\n\n{question}")]
```

ใน notebook เราเขียนรายการ message ตรงๆ ใน cell ในโปรแกรมเราแยกเป็น function ด้วยเหตุผลสามข้อ: ตั้งชื่อให้งานนั้นได้ ทดสอบแยกได้ และเรียกซ้ำจากที่อื่นได้

สองจุดที่ควรสังเกต:

- `encoding="utf-8"` ต้องระบุเสมอเมื่ออ่านไฟล์ที่มีภาษาไทย ถ้าไม่ระบุ Windows จะใช้ encoding อื่นและอ่านภาษาไทยผิด
- เอกสารถูกครอบด้วย `<document>...</document>` เพื่อให้ model แยกได้ว่าส่วนไหนคือเอกสารและส่วนไหนคือคำถาม นี่คือเรื่อง context window จาก Module 0: model เห็นเฉพาะสิ่งที่ function นี้ประกอบขึ้น

### 3.6 `main()`: ลำดับการทำงานทั้งหมด

ใน notebook ลำดับการทำงานคือลำดับของ cell ในโปรแกรมเรารวมไว้ใน function เดียวชื่อ `main()` อ่านจากบนลงล่างจะเห็นทั้งเรื่อง มี 5 ช่วง

**ช่วงที่ 1: ตรวจ input ก่อนทำงานที่ใช้เวลา**

```python
    if args.file is not None and not args.file.is_file():
        print(f"error: {args.file} is not a file", file=sys.stderr)
        return 2
```

ถ้า path ผิด ให้บอกทันทีแล้วจบ ไม่ต้องรอโหลด model ก่อนจึงรู้ว่าผิด หลักการคือ ตรวจสิ่งที่ตรวจได้เร็วก่อนเสมอ

**ช่วงที่ 2: พิมพ์ข้อมูลประกอบไปที่ stderr**

```python
    provider, model, _ = provider_settings(args.provider)
    print(f"[{provider} / {model}]", file=sys.stderr)
```

โปรแกรมมีช่องทางพิมพ์สองช่อง **stdout** สำหรับผลลัพธ์ และ **stderr** สำหรับข้อความประกอบและ error บนจอทั้งสองช่องปนกัน แต่โปรแกรมอื่นที่นำผลลัพธ์ไปใช้ต่อจะอ่านเฉพาะ stdout เราจึงส่งชื่อ model เวลา และจำนวน token ไปที่ stderr ด้วย `file=sys.stderr` ส่วนคำตอบของ model ไปที่ stdout

**ช่วงที่ 3: เรียก LLM ภายใน `try` / `except` / `finally`**

```python
    try:
        llm = get_llm(provider, temperature=args.temperature)
        started = time.time()
        answer = None
        for chunk in llm.stream(build_messages(args.question, args.file)):
            print(chunk.text, end="", flush=True)
            answer = chunk if answer is None else answer + chunk  # chunks add up to the full message
        print(flush=True)
    except Exception as error:  # each provider raises its own error types
        print(f"\nerror: the LLM call failed: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_loaded:
            release_model()
```

| ส่วน | รันเมื่อไร | ใช้ทำอะไรที่นี่ |
|---|---|---|
| `try:` | เสมอ | งานที่อาจล้มเหลว คือการเรียก LLM |
| `except Exception as error:` | เมื่อเกิด error ใน `try` | พิมพ์สาเหตุเป็นข้อความสั้นๆ แล้วจบด้วย exit code 1 |
| `finally:` | เสมอ ไม่ว่าสำเร็จหรือล้มเหลว | คืน RAM ของ model |

การเรียก LLM ล้มเหลวได้หลายแบบ: Ollama ไม่ได้เปิด ไม่มี API key ใช้เกินโควตา หรืออินเทอร์เน็ตหลุด ใน notebook คุณเห็น traceback ยาวแล้วแก้เอง ในโปรแกรม คนรันควรเห็นประโยคเดียวที่บอกว่าเกิดอะไรขึ้น

ภายใน loop มีสองเรื่อง:

- `print(chunk.text, end="", flush=True)` พิมพ์แต่ละชิ้นทันทีโดยไม่ขึ้นบรรทัดใหม่ (`end=""`) และไม่รอให้ buffer เต็ม (`flush=True`) คำตอบจึงไหลออกมาบนจอ
- `answer = ... answer + chunk` รวมชิ้นทั้งหมดเป็น message เดียว เพราะจำนวน token อยู่ใน message ที่รวมแล้ว

**ช่วงที่ 4: บันทึกลงไฟล์ถ้าขอไว้**

```python
    if args.out is not None and answer is not None:
        args.out.write_text(answer.text + "\n", encoding="utf-8")
        print(f"[saved to {args.out}]", file=sys.stderr)
```

**ช่วงที่ 5: รายงานเวลาและ token แล้วจบด้วย `return 0`**

### 3.7 สองบรรทัดสุดท้าย

```python
if __name__ == "__main__":
    sys.exit(main())
```

สองบรรทัดนี้อยู่ท้ายโปรแกรม Python เกือบทุกไฟล์ ความหมายคือ "ถ้าไฟล์นี้ถูกรันโดยตรง ให้เรียก `main()` แล้วส่งค่าที่มันคืนเป็น exit code"

เงื่อนไข `if` มีไว้เพื่อให้ไฟล์อื่น `import` function จากไฟล์นี้ไปใช้ได้ โดยที่ `main()` ไม่ถูกรันไปด้วย

### 3.8 Type hint

```python
def main(argv: list[str] | None = None) -> int:
```

ส่วน `: list[str] | None` และ `-> int` เรียกว่า type hint บอกว่า function รับและคืนค่าชนิดใด Python ไม่ได้บังคับตามนี้ แต่ editor ใช้ข้อมูลนี้เตือนเมื่อเราส่งค่าผิดชนิด และคนอ่านเข้าใจ function ได้โดยไม่ต้องอ่านข้างใน

`argv` มีไว้ให้ทดสอบได้ง่าย: เรียก `main(["คำถาม", "--temperature", "0.5"])` จาก code อื่นได้โดยไม่ต้องเปิด terminal ถ้าไม่ส่งอะไร โปรแกรมจะอ่านจาก terminal ตามปกติ

## 4. Exit code

เมื่อโปรแกรมจบ มันส่งตัวเลขหนึ่งตัวกลับไปให้ terminal เรียกว่า exit code โปรแกรมอื่นใช้ตัวเลขนี้ตัดสินว่าจะทำขั้นต่อไปหรือหยุด

| Exit code | ความหมายในไฟล์นี้ |
|---|---|
| 0 | สำเร็จ |
| 1 | เรียก LLM ไม่สำเร็จ |
| 2 | Argument ที่ให้มาผิด เช่น `--file` ชี้ไปที่ไฟล์ที่ไม่มี |

ดู exit code ของคำสั่งล่าสุดได้ด้วย `echo $?` (macOS) หรือ `echo $LASTEXITCODE` (PowerShell)

## 5. ลองแก้เอง

1. เพิ่มตัวเลือก `--system` ให้ผู้ใช้เปลี่ยนข้อความ system ได้จาก terminal โดยใช้ `SYSTEM` เป็นค่าเริ่มต้น คุณต้องแก้ `parse_args()` หนึ่งบรรทัด และส่งค่าต่อไปให้ `build_messages()`
2. รันด้วย `--file` ที่ชี้ไปยังไฟล์ที่ไม่มีอยู่ แล้วดู exit code จากนั้นปิด Ollama แล้วรันอีกครั้ง exit code ต่างกันอย่างไร
3. ลบ `flush=True` ออกจาก `print` ใน loop แล้วรัน สังเกตว่าคำตอบแสดงบนจอต่างจากเดิมอย่างไร

## 6. คำศัพท์

| คำ | ความหมาย |
|---|---|
| Terminal | หน้าต่างสำหรับพิมพ์คำสั่ง ใน editor เปิดจากเมนู Terminal |
| Argument | ค่าที่พิมพ์ตามหลังชื่อโปรแกรมตอนเรียก |
| Option / flag | Argument ที่ขึ้นต้นด้วย `--` และไม่ใส่ก็ได้ |
| stdout / stderr | ช่องทางพิมพ์ของโปรแกรม สำหรับผลลัพธ์ และสำหรับข้อความประกอบกับ error |
| Exit code | ตัวเลขที่โปรแกรมส่งกลับเมื่อจบ 0 คือสำเร็จ |
| Exception | Error ที่เกิดระหว่างรัน จับได้ด้วย `try` / `except` |
| Docstring | ข้อความอธิบายใน `"""..."""` ที่ต้นไฟล์หรือต้น function |
| Type hint | การระบุชนิดของค่าที่ function รับและคืน |
