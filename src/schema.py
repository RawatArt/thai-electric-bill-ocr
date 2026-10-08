"""The exact fields we want out of every bill.

Pydantic validates the model's output and gives us a typed record to export.
Every field can be null — a photo can be blurry and a field can be missing;
we'd rather get a null than crash. But every field is *required* in the JSON
schema, so the model must answer each one (with a value or null) instead of
silently skipping it.

Dates: the model copies them exactly as printed (Thai month names, พ.ศ. years)
and we normalize here in Python. Asking a 7B model to convert 2569 -> 2026
itself gave wrong years (e.g. 2016); plain code gets it right every time.
"""

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

BE_OFFSET = 543  # Thai Buddhist Era year = Gregorian year + 543

# full names and abbreviations (dots/spaces stripped before lookup)
THAI_MONTHS = {
    "มกราคม": 1, "มค": 1,
    "กุมภาพันธ์": 2, "กพ": 2,
    "มีนาคม": 3, "มีค": 3,
    "เมษายน": 4, "เมย": 4,
    "พฤษภาคม": 5, "พค": 5,
    "มิถุนายน": 6, "มิย": 6,
    "กรกฎาคม": 7, "กค": 7,
    "สิงหาคม": 8, "สค": 8,
    "กันยายน": 9, "กย": 9,
    "ตุลาคม": 10, "ตค": 10,
    "พฤศจิกายน": 11, "พย": 11,
    "ธันวาคม": 12, "ธค": 12,
}


def _to_gregorian(year_text: str) -> int:
    year = int(year_text)
    if len(year_text) == 2:  # short พ.ศ. like "69" -> 2569
        year += 2500
    return year - BE_OFFSET if year > 2400 else year


def _parse_thai_date(text: str) -> Optional[tuple[int, int, Optional[int]]]:
    """Return (year, month, day|None) in ค.ศ., or None if the format is unknown.

    Handles: 2569-09, 2569-10-15, 09/2569, 15/10/2569, 15/10/69,
             กันยายน 2569, มิถุนายน/2569, ก.ย. 69, 15 ต.ค. 2569,
             and ranges like "22/09/69 - 02/10/69 (เดือนปัจจุบัน)" -> last date
    """
    s = re.sub(r"\(.*?\)", "", text).strip()  # drop notes like (เดือนปัจจุบัน)
    # MEA prints the due date as a pay-from/pay-until range; the deadline is last
    s = re.split(r"\s+[-–]\s+|\s*ถึง\s*", s)[-1].strip()
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", s):
        return _to_gregorian(m[1]), int(m[2]), int(m[3]) if m[3] else None
    if m := re.fullmatch(r"(?:(\d{1,2})/)?(\d{1,2})/(\d{4}|\d{2})", s):
        return _to_gregorian(m[3]), int(m[2]), int(m[1]) if m[1] else None
    if m := re.fullmatch(r"(?:(\d{1,2})\s*)?([^\d\s/][^\d/]*?)[\s/]*(\d{4}|\d{2})", s):
        month = THAI_MONTHS.get(re.sub(r"[.\s]", "", m[2]))
        if month:
            return _to_gregorian(m[3]), month, int(m[1]) if m[1] else None
    return None


class ElectricityBill(BaseModel):
    provider: Optional[str] = Field(
        ..., description="Utility: 'MEA' (กฟน.) or 'PEA' (กฟภ.)"
    )
    customer_id: Optional[str] = Field(
        ...,
        description="Customer account number (บัญชีแสดงสัญญา / CA); "
        "null if the box is empty",
    )
    billing_period: Optional[str] = Field(
        ...,
        # no concrete example here: the model copied example dates into bills
        # that had no date printed at all
        description="Bill month (ประจำเดือน) copied exactly as printed; "
        "null if the bill does not show it.",
    )
    units_kwh: Optional[float] = Field(
        ..., description="Electricity used this period, in kWh (จำนวนหน่วย)"
    )
    energy_charge: Optional[float] = Field(..., description="ค่าพลังงานไฟฟ้า (THB)")
    ft_charge: Optional[float] = Field(..., description="ค่า Ft (THB, can be negative)")
    service_charge: Optional[float] = Field(..., description="ค่าบริการ (THB)")
    vat: Optional[float] = Field(..., description="ภาษีมูลค่าเพิ่ม (THB)")
    total_amount: Optional[float] = Field(
        ..., description="Final amount due, THB (จำนวนเงินรวมทั้งสิ้น)"
    )
    due_date: Optional[str] = Field(
        ...,
        description="Payment due date (กำหนดชำระ) copied exactly as printed; "
        "null if the bill does not show it.",
    )

    @field_validator("billing_period")
    @classmethod
    def _normalize_period(cls, v: Optional[str]) -> Optional[str]:
        parsed = v and _parse_thai_date(v)
        if not parsed:
            return v  # unknown format: keep raw so a human can see it
        year, month, _ = parsed
        return f"{year:04d}-{month:02d}"

    @field_validator("due_date")
    @classmethod
    def _normalize_due_date(cls, v: Optional[str]) -> Optional[str]:
        parsed = v and _parse_thai_date(v)
        if not parsed or parsed[2] is None:
            return v
        year, month, day = parsed
        return f"{year:04d}-{month:02d}-{day:02d}"
