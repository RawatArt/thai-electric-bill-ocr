"""Measure extraction accuracy against hand-checked labels.

    python evaluate.py                        # every bill in samples/labels.json
    python evaluate.py --only S__5316616.jpg  # one bill

Run it before and after every prompt / pre-processing change: a 7B model is
sensitive to wording, and fixing one field can quietly break another.
The numbers printed at the end are what goes in the README "Results" section.
"""

import argparse
import json
import time
from pathlib import Path

from src.extract import extract_bill
from src.schema import ElectricityBill
from src.validate import check_bill

FIELDS = list(ElectricityBill.model_fields)


def same(expected, got) -> bool:
    if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
        return abs(expected - got) < 0.005
    return expected == got


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate bill extraction accuracy")
    parser.add_argument("--labels", default="samples/labels.json")
    parser.add_argument("--only", help="evaluate a single image from the labels file")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    labels = {
        name: fields
        for name, fields in json.loads(labels_path.read_text(encoding="utf-8")).items()
        if not name.startswith("_")
    }
    if args.only:
        labels = {args.only: labels[args.only]}

    field_hits = dict.fromkeys(FIELDS, 0)
    seconds: list[float] = []
    # did the sanity check flag the bills that actually had errors?
    caught, missed, false_alarms, clean_passed = 0, 0, 0, 0

    for name, expected in labels.items():
        image = labels_path.parent / name
        start = time.perf_counter()
        try:
            bill = extract_bill(str(image))
        except Exception as e:  # count a crash as every field wrong
            print(f"\n[error] {name}: {e}")
            missed += 1
            continue
        seconds.append(time.perf_counter() - start)

        got = bill.model_dump()
        wrong = [f for f in FIELDS if not same(expected.get(f), got[f])]
        for f in FIELDS:
            field_hits[f] += f not in wrong
        flagged = bool(check_bill(bill))
        if wrong:
            caught += flagged
            missed += not flagged
        else:
            false_alarms += flagged
            clean_passed += not flagged

        status = "flagged" if flagged else "not flagged"
        print(f"\n{name}: {len(FIELDS) - len(wrong)}/{len(FIELDS)} correct, "
              f"{seconds[-1]:.0f}s, {status}")
        for f in wrong:
            print(f"  {f:15} expected {expected.get(f)!r:14} got {got[f]!r}")

    n = len(labels)
    total_hits = sum(field_hits.values())
    print("\n=== per field ===")
    for f in FIELDS:
        print(f"  {f:15} {field_hits[f]}/{n}  ({field_hits[f] / n:.0%})")
    print(f"\noverall: {total_hits}/{n * len(FIELDS)} fields "
          f"({total_hits / (n * len(FIELDS)):.0%}) on {n} bills")
    if seconds:
        print(f"time:    {sum(seconds) / len(seconds):.0f}s per bill on average")
    print(f"review flag: caught {caught} of {caught + missed} bills with errors, "
          f"{false_alarms} false alarm(s) on {false_alarms + clean_passed} correct bills")


if __name__ == "__main__":
    main()
