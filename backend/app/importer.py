"""Import the input data of the Excel planner (v35 layout) into the app's state.

Only cells a planner types into are read. Everything that was a formula in the
workbook is recalculated by the engine instead.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

import openpyxl
from openpyxl.utils import column_index_from_string as ci

from .engine.state import empty_state


def _v(x: Any) -> Any:
    """Normalise a cell value for JSON storage."""
    if isinstance(x, dt.datetime):
        return x.date().isoformat()
    if isinstance(x, dt.date):
        return x.isoformat()
    if isinstance(x, dt.time):
        return x.strftime("%H:%M")
    if isinstance(x, str):
        s = x.strip()
        if s.startswith("#"):  # Excel error values
            return None
        return x if s else None
    return x


def _blank(*vals: Any) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in vals)


def load_workbook_state(path: str) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True)
    st = empty_state()

    def cell(sheet: str, ref_or_row, col=None):
        ws = wb[sheet]
        if col is None:
            return _v(ws[ref_or_row].value)
        return _v(ws.cell(row=ref_or_row, column=col).value)

    # ---------------- Data (settings) ----------------
    s = st["settings"]
    s["oee"] = cell("Data", "B1")
    s["hours_mon_thu"] = [cell("Data", "B3"), cell("Data", "C3")]
    s["hours_fri"] = [cell("Data", "B4"), cell("Data", "C4")]
    s["shifts"] = cell("Average Cutting Plan", "B2") or 2
    s["max_qty_default"] = cell("Data", "B6")
    s["gauge_moved"] = cell("Data", "B7")
    s["trolley"] = cell("Data", "B8")
    s["trolley_40"] = cell("Data", "B9")
    s["lead_green"] = cell("Data", "B11")
    s["lead_red"] = cell("Data", "B12")
    s["light_clean_h"] = cell("Data", "B13")
    s["heavy_clean_h"] = cell("Data", "B14")
    conts = []
    for r in range(18, 20):
        name = cell("Data", r, 1)
        if name is not None:
            conts.append({"name": str(name), "received": str(cell("Data", r, 2) or "").strip().upper() == "X"})
    s["containers"] = conts
    s["planning_date"] = None  # follows today (=TODAY() in the workbook)
    limits = []
    for r in range(28, 33):
        limits.append({"up_to": cell("Data", r, 2), "max_per_day": cell("Data", r, 3)})
    s["job_size_limits"] = limits
    s["colour_due_only"] = str(cell("Data", "B36") or "").strip().upper() == "X"
    s["week_a_monday"] = cell("Jobs Released", "D3")
    s["line_capacity"] = cell("Priority Calc", "AF2") or 600

    # ---------------- Cutting speed ----------------
    for r in range(3, 14):
        g = cell("Cutting Speed", r, 1)
        if g is None:
            continue
        st["cutting_speed"].append({
            "gauge": g,
            "l1": cell("Cutting Speed", r, 2), "l2": cell("Cutting Speed", r, 3), "l3": cell("Cutting Speed", r, 4),
            "bms_inverse": cell("Cutting Speed", r, 9),
        })

    # ---------------- Profiles per Product (master) ----------------
    ws = wb["Profiles per Product"]
    for r in range(2, ws.max_row + 1):
        vals = [_v(ws.cell(row=r, column=c).value) for c in range(1, 9)]
        if _blank(*vals):
            continue
        st["profiles"].append(dict(zip(
            ["product", "part", "gauge", "profiles", "perimeter", "notes", "operations", "laser"], vals)))

    # ---------------- Jobs Released ----------------
    ws = wb["Jobs Released"]
    entries = []  # (day, row, dict) in entry order
    for d in range(20):
        c0 = 1 + 9 * d
        for i in range(40):
            r = 9 + i
            prod, qty, job, bal, push, start = (_v(ws.cell(row=r, column=c0 + k).value) for k in range(1, 7))
            if _blank(prod, qty, job, bal, push, start):
                continue
            e = {"day": d, "row": i, "product": prod, "qty": qty, "job": job,
                 "balance": bal, "push": push, "start": start,
                 "balance_date": None, "balance_qty": {}}
            entries.append(e)
    st["jobs"] = entries

    # Balance orders: slot k = k-th job marked X that has a product and a start date.
    def is_x(v):
        return str(v or "").strip().upper() == "X"

    def has_start(e):
        return isinstance(e["start"], str) and len(e["start"]) == 10

    bal_entries = [e for e in entries if e["product"] not in (None, "") and has_start(e) and is_x(e["balance"])]
    for k, e in enumerate(bal_entries[:24]):
        e["balance_date"] = cell("Profile Balancing", 6 + k, 5)
        top = 33 + 44 * k
        for t in range(1, 41):
            q = cell("Profile Balancing", top + 2 + t, 5)
            if q is not None:
                e["balance_qty"][str(t)] = q

    # ---------------- RG Released Jobs ----------------
    for i in range(24):
        r = 6 + i
        job, prod, rel, push, start = (cell("RG Released Jobs", r, c) for c in range(2, 7))
        qty = {}
        top = 33 + 44 * i
        for t in range(1, 41):
            q = cell("RG Released Jobs", top + 2 + t, 5)
            if q is not None:
                qty[str(t)] = q
        if _blank(job, prod, rel, push, start) and not qty:
            continue
        st["rg_jobs"].append({"row": i, "job": job, "product": prod, "released": rel,
                              "push": push, "start": start, "qty": qty})

    # ---------------- R&D ----------------
    for i in range(60):
        r = 6 + i
        vals = [cell("R&D", r, c) for c in range(2, 7)]
        if _blank(*vals):
            continue
        st["rnd"].append(dict(zip(["program", "gauge", "duration", "laser", "start"], vals), row=i))

    # ---------------- Cleaning ----------------
    for i in range(12):
        r = 9 + i
        st["cleaning"].append({
            "week": i // 3, "laser": i % 3 + 1,
            "light": cell("Cleaning", r, 5), "heavy": cell("Cleaning", r, 6),
            "start_time": cell("Cleaning", r, 10), "comment": cell("Cleaning", r, 15),
        })

    # ---------------- Back Orders ----------------
    for i in range(150):
        r = 6 + i
        date, prod, qty, start = cell("Back Orders", r, 1), cell("Back Orders", r, 2), cell("Back Orders", r, 3), cell("Back Orders", r, 12)
        if _blank(prod, qty, start):
            continue
        st["back_orders"].append({"row": i, "date": date, "product": prod, "qty": qty, "start": start})

    # ---------------- Schedule per Laser typed cells ----------------
    ws = wb["Schedule per Laser"]
    sections = [("push", 5, 12), ("bal", 17, 30), ("part", 47, 76), ("rnd", 123, 4)]
    spl = {}
    for d in range(20):
        base = 8 + 128 * d
        for l in range(3):
            c0 = 1 + 9 * l
            for sec, off, n in sections:
                occ: dict = defaultdict(int)
                for j in range(n):
                    r = base + off + j
                    prod = _v(ws.cell(row=r, column=c0).value)
                    part = _v(ws.cell(row=r, column=c0 + 1).value)
                    taken = _v(ws.cell(row=r, column=c0 + 6).value)
                    sic = _v(ws.cell(row=r, column=c0 + 7).value)
                    com = _v(ws.cell(row=r, column=c0 + 8).value)
                    if prod is None:
                        continue
                    k0 = (d, l + 1, sec, str(prod), str(part))
                    n_occ = occ[k0]
                    occ[k0] += 1
                    if _blank(taken, sic, com):
                        continue
                    key = "|".join(map(str, k0 + (n_occ,)))
                    spl[key] = {"taken": taken, "sic": sic, "comment": com}
    st["spl"] = spl

    # ---------------- Stock lists ----------------
    ws = wb["BCZB List"]
    st["bczb_columns"] = [_v(ws.cell(row=1, column=c).value) for c in range(1, 19)]
    for r in range(2, ws.max_row + 1):
        vals = [_v(ws.cell(row=r, column=c).value) for c in range(1, 19)]
        if _blank(*vals[:13]):
            continue
        row = {k: vals[ci(k) - 1] for k in "A B C D E F G H I J K L M P".split()}
        st["bczb"].append(row)

    # Plant 40 Stock: "Qty Shipped" typed over the BCZB value on some lines.
    planner_rows = [r for r in st["bczb"]
                    if str(r.get("C") or "").strip().upper() == "PROFILE" and r.get("E") not in (None, "")
                    and "OBSOLETE" not in str(r.get("E")).upper() and "NOT USED" not in str(r.get("E")).upper()]
    overrides = {}
    for i, br in enumerate(planner_rows[:250]):
        shown = cell("Plant 40 Stock", 6 + i, 6)
        if shown != br.get("H") and not (shown in (None, "") and br.get("H") in (None, "")):
            overrides[str(br.get("E"))] = shown
    st["p40_qty_override"] = overrides

    ws = wb["Order Book"]
    st["order_book_columns"] = [_v(ws.cell(row=1, column=c).value) for c in range(1, 16)]
    for r in range(2, ws.max_row + 1):
        vals = [_v(ws.cell(row=r, column=c).value) for c in range(1, 16)]
        if _blank(*vals):
            continue
        st["order_book"].append(vals)

    ws = wb["Shutdown Stock Tracking"]
    st["shutdown_columns"] = [_v(ws.cell(row=1, column=c).value) for c in range(1, ws.max_column + 1)]
    for r in range(2, ws.max_row + 1):
        vals = [_v(ws.cell(row=r, column=c).value) for c in range(1, ws.max_column + 1)]
        if _blank(*vals):
            continue
        st["shutdown_stock"].append(vals)

    ws = wb["Lessons Learned"]
    for r in range(6, ws.max_row + 1):
        vals = [_v(ws.cell(row=r, column=c).value) for c in range(1, 6)]
        if _blank(*vals):
            continue
        st["lessons"].append(dict(zip(["number", "topic", "problem", "investigation", "solution"], vals)))

    # ---------------- Management Report typed header notes ----------------
    ws = wb["Management Report"]
    notes = {}
    for c in range(7, ws.max_column + 1):
        v = _v(ws.cell(row=1, column=c).value)
        if v is not None:
            notes[openpyxl.utils.get_column_letter(c)] = v
    st["mgmt_report"]["header_notes"] = notes
    return st
