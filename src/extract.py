"""Image -> structured bill, using a local vision LLM (Qwen2.5-VL in LM Studio).

Nothing leaves the machine. We talk to LM Studio's OpenAI-compatible server,
ask for output that matches our Pydantic schema (structured output), then
validate it. Because it's the OpenAI-compatible API, the same code also works
with Ollama / vLLM / llama.cpp — just change LLM_BASE_URL and LLM_MODEL.

TODO (พี่อาร์ตทำต่อ — นี่คือจุดที่เป็น "ฝีมือจริง"):
  1. ลองรันกับใบเสร็จจริง แล้วดูว่า field ไหนพลาดบ่อย
  2. ปรับ PROMPT ให้แม่นขึ้น (เช่น บอกตำแหน่งตัวเลขบนบิล MEA vs PEA)
  3. ถ้าจำเป็น เพิ่มขั้น pre-process รูป (crop/contrast) ก่อนส่งเข้าโมเดล
"""

import base64
import mimetypes
import os

from openai import OpenAI

from src.schema import ElectricityBill

# LM Studio defaults; override with env vars to point at another local server.
BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
MODEL = os.environ.get("LLM_MODEL", "qwen/qwen2.5-vl-7b")

PROMPT = """You are reading a photo of a Thai electricity bill (ใบแจ้งค่าไฟฟ้า),
issued by either MEA (การไฟฟ้านครหลวง, กฟน.) or PEA (การไฟฟ้าส่วนภูมิภาค, กฟภ.).

Use ONLY the "ใบแจ้งค่าไฟฟ้า" part (this month's bill, at the top). The same paper
often has other parts with DIFFERENT numbers — ignore them completely:
- a receipt for LAST month printed below it (ใบเสร็จรับเงิน / ใบกำกับภาษี),
- the usage history table (ประวัติการใช้ไฟฟ้า).

Fill EVERY field of the schema. Where to look on the bill:
- provider: "MEA" or "PEA", from the logo / header.
- customer_id: the customer account number (บัญชีแสดงสัญญา / CA / หมายเลขผู้ใช้ไฟฟ้า).
  Never use a meter reading here. If the box is empty or hidden (often blurred or
  covered for privacy), null.
- billing_period: the bill month (ประจำเดือน), often printed next to ค่าพลังงานไฟฟ้า.
- units_kwh: near the top there is a meter row with these column headers, left to
  right: วันที่จดเลขอ่าน (Meter Reading Date) | เลขอ่านครั้งหลัง (Last Meter Reading) |
  เลขอ่านครั้งก่อน (Previous Meter Reading) | จำนวนหน่วย (kWh) | ตัวคูณ (Multiplier).
  units_kwh is the number printed UNDER the จำนวนหน่วย (kWh) header. It is always
  printed when that row is visible, so do not return null for it. Check: it equals
  เลขอ่านครั้งหลัง minus เลขอ่านครั้งก่อน. NOT the meter readings themselves and
  NOT the usage history table.
- energy_charge: the baht amount on the ค่าพลังงานไฟฟ้า line.
- ft_charge: the baht amount on the ค่าไฟฟ้าผันแปร (Ft) line, from the amount column on
  the right. NOT the rate per unit (บาท/หน่วย) printed in the middle of that line.
  Copy its sign exactly as printed: positive unless a minus sign is shown.
- service_charge: the baht amount on the ค่าบริการ line.
- vat: the baht amount on the ภาษีมูลค่าเพิ่ม line (not the "7 %").
- total_amount: รวมเงินที่ต้องชำระทั้งสิ้น (Amount), the final amount to pay.
  NOT the subtotal before VAT (รวมค่าไฟฟ้าก่อนภาษีมูลค่าเพิ่ม).
- due_date: โปรดชำระเงินตั้งแต่วันที่ / กำหนดชำระ (Due Date).

Rules:
- Numbers as plain numbers: no thousands separators, no "บาท", no currency symbol.
- Dates (billing_period, due_date): copy the text EXACTLY as printed on the bill,
  including a range like "<date> - <date>". Do NOT reformat, translate or convert
  the year — the program converts dates itself.
  Many bills (or cropped photos) have no due date or bill month: then return null.
  The meter reading date (วันที่จดเลขอ่าน) is NOT the due date.
- If a field is not visible or you are unsure, return null for it. Do not guess,
  and never invent a value that is not printed on this bill.
"""

client = OpenAI(base_url=BASE_URL, api_key="local")  # local servers ignore the key


def _image_data_url(image_path: str) -> str:
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def extract_bill(image_path: str) -> ElectricityBill:
    """Run one image through the local model and return a validated bill."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                ],
            }
        ],
        # force JSON matching the schema
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "electricity_bill",
                "schema": ElectricityBill.model_json_schema(),
            },
        },
        temperature=0,  # deterministic extraction
    )
    return ElectricityBill.model_validate_json(response.choices[0].message.content)
