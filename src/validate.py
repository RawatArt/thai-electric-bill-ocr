"""Sanity checks on an extracted bill, so wrong numbers get flagged for a human.

A small vision model doesn't always say null when it can't read something — it
sometimes invents plausible numbers, or picks them from the wrong part of the
paper (e.g. last month's receipt printed below the bill). Bill numbers add up,
so we check the arithmetic instead of trusting the model:

    energy + service + Ft          = subtotal  (ส่วนลด is usually 0.00)
    subtotal x 7%                  = VAT
    subtotal + VAT                 = total     (unless arrears or a discount apply)
"""

import re

from src.schema import ElectricityBill

VAT_RATE = 0.07
TOLERANCE = 0.05  # baht; every line on the bill is rounded to 2 decimals


def check_bill(bill: ElectricityBill) -> list[str]:
    """Return human-readable problems; an empty list means the bill looks consistent."""
    issues: list[str] = []

    if bill.total_amount is None:
        issues.append("missing total_amount")
    if bill.units_kwh is None:
        issues.append("missing units_kwh")
    elif bill.units_kwh <= 0:
        issues.append(f"units_kwh is {bill.units_kwh}")

    if bill.billing_period and not re.fullmatch(r"\d{4}-\d{2}", bill.billing_period):
        issues.append(f"unrecognized billing_period '{bill.billing_period}'")
    if bill.due_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", bill.due_date):
        issues.append(f"unrecognized due_date '{bill.due_date}'")

    parts = {
        "energy_charge": bill.energy_charge,
        "service_charge": bill.service_charge,
        "ft_charge": bill.ft_charge,
        "vat": bill.vat,
    }
    missing = [name for name, value in parts.items() if value is None]
    if missing:
        issues.append(f"cannot verify charges, missing: {', '.join(missing)}")
        return issues

    subtotal = bill.energy_charge + bill.service_charge + bill.ft_charge
    expected_vat = subtotal * VAT_RATE
    if abs(bill.vat - expected_vat) > TOLERANCE:
        issues.append(
            f"vat {bill.vat:.2f} != 7% of (energy + service + Ft) = {expected_vat:.2f}"
        )

    if bill.total_amount is not None:
        diff = bill.total_amount - (subtotal + bill.vat)
        if abs(diff) > TOLERANCE:
            issues.append(
                f"total_amount differs from charges + VAT by {diff:+.2f} "
                "(arrears or a discount? check the bill)"
            )

    return issues
