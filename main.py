"""CLI: python main.py <image> [<image> ...] [--csv output/bills.csv]

Example:
    python main.py samples/bill1.jpg
    python main.py samples/*.jpg --csv output/bills.csv
"""

import argparse
from pathlib import Path

from src.export import to_csv
from src.extract import extract_bill
from src.validate import check_bill


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Thai electricity bill OCR (local / on-premise)"
    )
    parser.add_argument("images", nargs="+", help="path(s) to bill image(s)")
    parser.add_argument("--csv", default="output/bills.csv", help="CSV output path")
    args = parser.parse_args()

    ok, failed, review = 0, 0, 0
    for img in args.images:
        if not Path(img).exists():
            print(f"[skip] not found: {img}")
            failed += 1
            continue
        print(f"[read] {img}")
        try:
            bill = extract_bill(img)
        except Exception as e:  # keep going if one photo fails
            print(f"[error] {img}: {e}")
            failed += 1
            continue
        print(bill.model_dump_json(indent=2))
        issues = check_bill(bill)
        for issue in issues:
            print(f"[review] {issue}")
        to_csv(bill, args.csv, issues)
        ok += 1
        review += bool(issues)

    print(
        f"\nDone. {ok} ok ({review} need review), {failed} failed -> {args.csv}"
    )


if __name__ == "__main__":
    main()
