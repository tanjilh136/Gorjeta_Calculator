"""Money helpers. All amounts are integer cents; no floating point anywhere."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MAX_CENTS = 99_999_999_99  # €99.999.999,99 - far above any realistic day


class MoneyError(ValueError):
    pass


def _group_thousands(digits: str) -> str:
    parts = []
    while len(digits) > 3:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    parts.insert(0, digits)
    return ".".join(parts)


def format_amount(cents: int) -> str:
    """1234567 -> '12.345,67' (no currency symbol)."""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}{_group_thousands(str(cents // 100))},{cents % 100:02d}"


def format_euro(cents: int) -> str:
    """1234567 -> '€12.345,67'; used in both languages."""
    if cents < 0:
        return "-€" + format_amount(-cents)
    return "€" + format_amount(cents)


_ALLOWED = re.compile(r"^[0-9.,]+$")


def parse_amount(text: str) -> int:
    """Parse a user-typed euro amount into cents.

    Accepts '1.234,56', '1234,56', '1234.56', '1 234,5', '€ 12' ...
    When both separators appear, the last one is the decimal separator.
    A lone '.' followed by exactly three digits is a thousands separator
    ('1.234' = 1234 euros), otherwise it is a decimal point ('12.5').
    Empty text is 0.
    """
    s = (text or "").strip().replace("€", "").replace(" ", "").replace(" ", "")
    if s == "":
        return 0
    if not _ALLOWED.match(s):
        raise MoneyError(text)

    last_comma, last_dot = s.rfind(","), s.rfind(".")
    if last_comma >= 0 and last_dot >= 0:
        dec = "," if last_comma > last_dot else "."
    elif last_comma >= 0:
        dec = "," if s.count(",") == 1 else None
    elif last_dot >= 0:
        tail = s[last_dot + 1:]
        dec = "." if s.count(".") == 1 and len(tail) != 3 else None
    else:
        dec = None

    if dec is None:
        int_part, frac_part = s, ""
        thousands = "," if "," in s else "."
        groups = int_part.split(thousands)
        if len(groups) > 1 and (not groups[0] or any(len(g) != 3 for g in groups[1:])):
            raise MoneyError(text)
        int_part = "".join(groups)
    else:
        int_part, frac_part = s.rsplit(dec, 1)
        thousands = "." if dec == "," else ","
        if dec in int_part:
            raise MoneyError(text)
        groups = int_part.split(thousands)
        if len(groups) > 1 and (not groups[0] or any(len(g) != 3 for g in groups[1:])):
            raise MoneyError(text)
        int_part = "".join(groups)

    if not int_part:
        int_part = "0"
    if not int_part.isdigit() or (frac_part and not frac_part.isdigit()):
        raise MoneyError(text)
    if len(frac_part) > 2:
        raise MoneyError(text)
    cents = int(int_part) * 100 + int((frac_part + "00")[:2])
    if cents > MAX_CENTS:
        raise MoneyError(text)
    return cents


def split_equally(total_cents: int, present_count: int) -> int:
    """Per-person share, always rounded DOWN to the cent. No redistribution."""
    if present_count <= 0:
        return 0
    return total_cents // present_count


def parse_percent(value: str | Decimal | int) -> Decimal:
    try:
        pct = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise MoneyError(str(value)) from None
    if not pct.is_finite() or pct < 0 or pct > 100:
        raise MoneyError(str(value))
    return pct


def deduction_cents(total_cents: int, pct: Decimal) -> int:
    """Total x pct%, to the cent, rounding half up."""
    exact = Decimal(int(total_cents)) * pct / Decimal(100)
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def format_percent(pct: Decimal) -> str:
    """Decimal('11.50') -> '11,5' (comma decimal, trailing zeros removed)."""
    q = pct.quantize(Decimal("0.01"))
    text = f"{q:f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")
