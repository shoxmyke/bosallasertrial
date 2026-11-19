"""Small helpers that reproduce Excel behaviour the planner relied on."""
from __future__ import annotations

import datetime as dt
import math
from typing import Any

DAYS = 20
WEEKS = "ABCD"
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
DOW_LONG = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]


def day_label(d: int) -> str:
    return f"Week {WEEKS[d // 5]} {DOW[d % 5]}"


def num(x: Any) -> float:
    """Excel N(): numbers stay, everything else is 0."""
    if isinstance(x, bool):
        return 0
    if isinstance(x, (int, float)):
        return x
    return 0


def isnum(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def blank(x: Any) -> bool:
    return x is None or (isinstance(x, str) and x == "")


def key(x: Any) -> str:
    """Case-insensitive match key, like Excel's MATCH / SUMIFS / COUNTIF."""
    if x is None:
        return ""
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return str(x).strip().upper()


def is_x(x: Any) -> bool:
    return isinstance(x, str) and x.strip().upper() == "X"


def _prec(x: float) -> float:
    # Excel rounds to 15 significant digits before ROUND/ROUNDUP/INT style operations.
    return float(f"{x:.15g}")


def xround(x: float, digits: int = 0) -> float:
    x = _prec(x)
    m = 10 ** digits
    return math.copysign(math.floor(abs(x) * m + 0.5) / m, x)


def xroundup(x: float) -> float:
    x = _prec(x)
    return math.copysign(math.ceil(abs(x)), x)


def to_date(x: Any) -> dt.date | None:
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    if isinstance(x, str) and len(x) >= 10:
        try:
            return dt.date.fromisoformat(x[:10])
        except ValueError:
            return None
    return None


def workday_on_or_after(d: dt.date) -> dt.date:
    """WORKDAY(d-1, 1): d itself if a weekday, else the next Monday."""
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def workday(d: dt.date, n: int) -> dt.date:
    step = 1 if n >= 0 else -1
    left = abs(n)
    while left:
        d += dt.timedelta(days=step)
        if d.weekday() < 5:
            left -= 1
    return d


def networkdays(a: dt.date, b: dt.date) -> int:
    if b < a:
        return -networkdays(b, a)
    days = (b - a).days + 1
    full, rem = divmod(days, 7)
    n = full * 5
    wd = a.weekday()
    for i in range(rem):
        if (wd + i) % 7 < 5:
            n += 1
    return n


def plan_dates(week_a_monday: dt.date) -> list[dt.date]:
    return [week_a_monday + dt.timedelta(days=7 * (d // 5) + d % 5) for d in range(DAYS)]


def day_index(dates: list[dt.date], x: dt.date) -> int:
    """COUNTIF(plan dates, "<"&WORKDAY(x-1,1)) -> 0..20."""
    w = workday_on_or_after(x)
    return sum(1 for d in dates if d < w)


def colour_code(share: Any, due_red: bool | None = None) -> Any:
    """1 green (>=99.99%), 2 yellow (>=50%), 3 red (>=10%, or always when due_red)."""
    if not isnum(share):
        return ""
    if share >= 0.9999:
        return 1
    if share >= 0.5:
        return 2
    if due_red is None:
        return 3 if share >= 0.1 else ""
    return 3 if (share > 0 or due_red) else ""


def fixed(x: float, decimals: int = 1) -> str:
    v = xround(x, decimals)
    return f"{v:,.{decimals}f}"


def fmt_num(x: Any) -> str:
    """How Excel shows a number joined into text with &."""
    if isinstance(x, float):
        if x.is_integer():
            return str(int(x))
        return f"{x:.15g}"
    return str(x)
