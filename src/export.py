"""Where the validated data goes next.

Layer 1 (done here): append each bill to a CSV.
Layer 2 (พี่อาร์ตทำต่อ): push to a Google Sheet so it updates live — this is the
part that turns "an OCR script" into "a tool a shop/accountant would actually use".
See push_to_sheet() below for the stub + README roadmap.
"""

import csv
from collections.abc import Sequence
from pathlib import Path

from src.schema import ElectricityBill


def to_csv(
    bill: ElectricityBill,
    csv_path: str = "output/bills.csv",
    issues: Sequence[str] = (),
) -> None:
    """Append one bill; `issues` (from validate.check_bill) mark rows to double-check."""
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    row = bill.model_dump()
    row["needs_review"] = bool(issues)
    row["review_notes"] = "; ".join(issues)
    # utf-8-sig so Excel opens Thai text correctly
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def push_to_sheet(bill: ElectricityBill) -> None:
    """TODO (Layer 2): append to a Google Sheet with gspread.

    Sketch:
        import gspread
        gc = gspread.service_account(filename=os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        ws = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
        ws.append_row(list(bill.model_dump().values()))

    Note for the portfolio story: the *image* still never leaves the machine —
    only the already-extracted fields go to the Sheet. Say that explicitly in the demo.
    """
    raise NotImplementedError("Layer 2 — implement with gspread")
