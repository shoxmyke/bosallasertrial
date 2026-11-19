"""Compare the engine with the values the Excel workbook calculated.

Usage:  python -m tests.verify_against_excel path/to/planner.xlsx

The workbook's cached values (what Excel showed when it was last saved) are the
reference. The planning date is set to the date the workbook was calculated.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pickle
import sys
import time

import openpyxl
from openpyxl.utils import column_index_from_string as ci, get_column_letter as gl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine.calc import Plan, N_LINES  # noqa: E402
from app.engine.xl import DAYS, isnum  # noqa: E402
from app.importer import load_workbook_state  # noqa: E402

CACHE = os.environ.get("VERIFY_CACHE", "/tmp/verify_cache")


def load(path):
    os.makedirs(CACHE, exist_ok=True)
    st_p = os.path.join(CACHE, "state.json")
    v_p = os.path.join(CACHE, "values.pkl")
    if not os.path.exists(st_p):
        st = load_workbook_state(path)
        json.dump(st, open(st_p, "w"), default=str)
    if not os.path.exists(v_p):
        wb = openpyxl.load_workbook(path, data_only=True)
        V = {ws.title: {(c.row, c.column): c.value for row in ws.iter_rows() for c in row if c.value is not None}
             for ws in wb.worksheets}
        pickle.dump(V, open(v_p, "wb"))
    return json.load(open(st_p)), pickle.load(open(v_p, "rb"))


class Checker:
    def __init__(self, V):
        self.V = V
        self.fails = {}
        self.counts = {}

    def eq(self, sheet, r, c, got, label=""):
        if isinstance(c, str):
            c = ci(c)
        exp = self.V[sheet].get((r, c))
        ok = _same(exp, got)
        name = f"{sheet}:{label or gl(c)}"
        n, f = self.counts.get(name, (0, 0))
        self.counts[name] = (n + 1, f + (0 if ok else 1))
        if not ok:
            self.fails.setdefault(name, []).append(f"{gl(c)}{r}: excel={exp!r} engine={got!r}")

    def report(self):
        tot = sum(n for n, _ in self.counts.values())
        bad = sum(f for _, f in self.counts.values())
        for name, (n, f) in sorted(self.counts.items()):
            flag = "OK " if f == 0 else "BAD"
            print(f"  [{flag}] {name:55s} {n - f}/{n}")
            if f:
                for x in self.fails[name][:4]:
                    print("        ", x)
        print(f"\nTOTAL checked {tot}, mismatches {bad}")
        return bad


def _same(exp, got):
    if exp in (None, "") and got in (None, "", 0):
        return exp is None and got == 0 or got in (None, "") or exp == got or exp is None
    if isinstance(exp, dt.datetime):
        exp = exp.date()
    if isinstance(got, dt.datetime):
        got = got.date()
    if isnum(exp) and isnum(got):
        return abs(exp - got) <= 1e-6 * max(1, abs(exp))
    if isinstance(exp, str) and isinstance(got, str):
        return exp.strip() == got.strip()
    return exp == got


def main(path):
    st, V = load(path)
    calc_date = V["Data"][(22, 2)]
    t = time.time()
    p = Plan(st, today=calc_date.date())
    print(f"engine run: {time.time() - t:.2f}s")
    ck = Checker(V)
    PC = "Priority Calc"
    for e in p.pc:
        r = e["a"] + 1
        for col, k in (("B", "B"), ("C", "C"), ("E", "E"), ("L", "L"), ("O", "O"), ("Q", "Q"), ("R", "R"),
                       ("T", "T"), ("AG", "AG"), ("AH", "AH"), ("AL", "AL"), ("N", "N")):
            ck.eq(PC, r, col, e[k])
    for l in p.lines:
        ck.eq(PC, l["w"] + 1, "Z", l["Z"])
        ck.eq(PC, l["w"] + 1, "AA", l["AA"])
        ck.eq(PC, l["w"] + 1, "AB", l["AB"])
    for k in range(600):
        ck.eq(PC, k + 2, "AC", p.rank_line[k] if p.rank_line[k] is not None else "")
    # Balance Calc
    BC = "Balance Calc"
    for sl in p.slots:
        r = sl["s"] + 1
        for col in ("C", "D", "G", "H", "I", "J", "K", "M", "N", "O", "P", "Q", "LO", "LT"):
            ck.eq(BC, r, col, sl[col])
        for d in range(DAYS):
            ck.eq(BC, r, ci("GT") + 6 * d, sl["GT"][d], "GT..(day profiles)")
            ck.eq(BC, r, ci("GY") + 6 * d, sl["GY"][d], "GY..(cum movable)")
            ck.eq(BC, r, ci("MQ") + d, sl["day_codes"][d], "MQ..(day colour)")
        ck.eq(BC, r, "NL", sl["NL"])
    for pr in p.bal_parts:
        r = (pr["s"] - 1) * 40 + pr["t"] + 1
        for col in ("AB", "AC", "AE", "AI", "AJ", "LR", "NK"):
            ck.eq(BC, r, col, pr[col])
    for a in p.active:
        r = a["p"] + 1
        ck.eq(BC, r, "BC", a["BC"])
        for d in range(DAYS):
            ck.eq(BC, r, ci("BH") + 7 * d, a["q"][d], "BH..(q)")
            ck.eq(BC, r, ci("BI") + 7 * d, a["to1"][d], "BI..(to L1)")
            ck.eq(BC, r, ci("BJ") + 7 * d, a["to3"][d], "BJ..(to L3)")
    # Job Schedule
    JS = "Job Schedule"
    for r in p.js:
        rr = r["i"] + 18
        for col in ("B", "D", "E", "F", "G", "H", "J", "M"):
            ck.eq(JS, rr, col, r[col])
        for d in range(DAYS):
            ck.eq(JS, rr, ci("Q") + 14 * d, r["qty"][d], "day qty")
    for d in range(DAYS):
        c = ci("Q") + 14 * d
        ck.eq(JS, 14, c, p.js_day[d]["moved"], "row14 moved")
        ck.eq(JS, 16, c, p.js_day[d]["to1"], "row16 to L1")
    # Average Cutting Plan
    AC = "Average Cutting Plan"
    for row in p.plan:
        rr = row["k"] + 5
        ck.eq(AC, rr, "A", row["A"])
        ck.eq(AC, rr, "B", row["B"])
        ck.eq(AC, rr, "C", row["rel"][0])
        ck.eq(AC, rr, "F", row["rel4"])
        for d in range(DAYS):
            c0 = 7 + 5 * d + d // 5
            ck.eq(AC, rr, c0, row["G"][d], "day qty")
            ck.eq(AC, rr, c0 + 1, row["H"][d], "day L1 hrs")
            ck.eq(AC, rr, c0 + 2, row["I"][d], "day L2 hrs")
            ck.eq(AC, rr, c0 + 3, row["J"][d], "day L3 hrs")
        for col in ("DG", "DI", "DJ", "DK", "DM", "DN", "DO"):
            ck.eq(AC, rr, col, row[col])
    for d in range(DAYS):
        c0 = 7 + 5 * d + d // 5
        ck.eq(AC, 3, c0 + 1, p.cap[d][0], "row3 capacity")
        ck.eq(AC, 4, c0, p.day_totals[d]["qty"], "row4 qty")
        for l in range(4):
            ck.eq(AC, 4, c0 + 1 + l, p.day_totals[d]["load"][l], "row4 load %")
    ck.eq(AC, 1, "K", p.headline, "K1 headline")
    for b in p.plan_bal:
        rr = (276 if b["kind"] == "BAL" else 277) + b["slot"]
        ck.eq(AC, rr, "A", b["A"], "bal rows")
        for d in range(DAYS):
            c0 = 7 + 5 * d + d // 5
            ck.eq(AC, rr, c0, b["G"][d], "bal day qty")
            ck.eq(AC, rr, c0 + 1, b["H"][d], "bal day L1")
            ck.eq(AC, rr, c0 + 2, b["I"][d], "bal day L2")
            ck.eq(AC, rr, c0 + 3, b["J"][d], "bal day L3")
    # Laser Parts
    LP = "Laser Parts"
    for pt in p.lp:
        rr = pt["a"] + 1
        ck.eq(LP, rr, "C", pt["C"])
        ck.eq(LP, rr, "F", pt["F"])
        ck.eq(LP, rr, "L", pt["L"])
        for d in range(DAYS):
            c0 = ci("N") + 6 * d
            ck.eq(LP, rr, c0, pt["N"][d], "N.. needed")
            ck.eq(LP, rr, c0 + 1, pt["O"][d], "O.. to L1")
            ck.eq(LP, rr, c0 + 2, pt["P"][d], "P.. to L3")
            for l in range(3):
                ck.eq(LP, rr, c0 + 3 + l, pt["line"][d][l], "Q.. line counters")
            ck.eq(LP, rr, ci("EE") + d, pt["EE"][d], "EE.. towbars done")
    # Schedule per Laser
    SP = "Schedule per Laser"
    offs = {"push": 5, "bal": 17, "part": 47, "rnd": 123}
    for d in range(DAYS):
        base = 8 + 128 * d
        for l in range(3):
            c0 = 1 + 9 * l
            by_sec = {}
            for r in p.spl[d][l]:
                by_sec.setdefault(r["sec"], []).append(r)
            for sec, n in (("push", 12), ("bal", 30), ("part", 76), ("rnd", 4)):
                rows = by_sec.get(sec, [])
                for j in range(n):
                    rr = base + offs[sec] + j
                    r = rows[j] if j < len(rows) else None
                    ck.eq(SP, rr, c0, r["A"] if r else "", f"{sec} product")
                    ck.eq(SP, rr, c0 + 1, r["B"] if r else "", f"{sec} part")
                    if sec != "rnd":
                        ck.eq(SP, rr, c0 + 3, r["D"] if r else "", f"{sec} qty")
                    ck.eq(SP, rr, c0 + 5, r["F"] if r else 0, f"{sec} stock taken")
                    if sec in ("bal", "part"):
                        ck.eq(SP, rr, c0 + 4, r["E"] if r else "", f"{sec} stock comment")
                    hc = ci("AE") + 13 * l
                    ck.eq(SP, rr, hc, r["push_qty"] if r else 0, f"{sec} push qty")
                    ck.eq(SP, rr, hc + 2, r["done"] if r else 0, f"{sec} done")
    # Completion Calc
    CC = "Completion Calc"
    for i, c in enumerate(p.comp):
        rr = i + 2
        ck.eq(CC, rr, "B", c["B"])
        ck.eq(CC, rr, "W", c["W"])
        ck.eq(CC, rr, "X", c["X"])
        for d in range(DAYS):
            ck.eq(CC, rr, ci("D") + d, c["cum"][d], "cum done")
            ck.eq(CC, rr, ci("AC") + d, c["towbars"][d], "towbars")
            ck.eq(CC, rr, ci("AX") + d, c["needed"][d], "needed")
            ck.eq(CC, rr, ci("CN") + d, c["codes"][d], "colour codes")
    # Laser Detail day hours
    LD = "Laser Detail"
    for d in range(DAYS):
        for l in range(3):
            ck.eq(LD, d + 2, ci("CA") + l, p.pushed_h[d][l], "pushed hrs")
            ck.eq(LD, d + 2, ci("CE") + l, p.stock_h[d][l], "stock saves hrs")
    # Stock
    for i, r in enumerate(p.p40):
        rr = i + 6
        for col in ("A", "G", "H", "I", "J", "K"):
            ck.eq("Plant 40 Stock", rr, col, r[col])
    # ---- page formulas ----
    from app.engine import pages as pg
    jr = pg.jobs_released(p)
    for w in jr["weeks"]:
        for day in w["days"]:
            c0 = 1 + 9 * day["d"]
            for r in day["rows"]:
                ck.eq("Jobs Released", 9 + r["row"], c0 + 8, r["check"], "check (I)")
                ck.eq("Jobs Released", 9 + r["row"], c0 + 7, r["plan_order"], "plan order (H)")
            ck.eq("Jobs Released", 8, c0 + 2, day["total_qty"], "day total")
    out = pg.output(p)
    for r in out["rows"]:
        rr = 8 + r["d"]
        for col, v in (("C", r["capacity"][0]), ("D", r["products"][0]), ("F", r["products"][1]), ("I", r["qty"]),
                       ("J", r["scheduled"]), ("K", r["cut"]), ("L", r["adherence"]), ("M", r["worked"]),
                       ("N", r["towbars"]), ("O", r["hours_saved"]), ("P", r["hours_pushed"])):
            ck.eq("Output", rr, col, v, f"col {col}")
    for col, v in (("I", out["total"]["qty"]), ("J", out["total"]["scheduled"]), ("K", out["total"]["cut"]),
                   ("L", out["total"]["adherence"]), ("N", out["total"]["towbars"])):
        ck.eq("Output", 28, col, v, "totals")
    jc = pg.jobs_completed(p)
    for i, r in enumerate(jc["rows"]):
        rr = 7 + i
        for col, k in (("A", "released"), ("B", "product"), ("C", "qty"), ("E", "completed"), ("F", "lead_days"),
                       ("G", "pct"), ("H", "status"), ("O", "done_qty"), ("Q", "colour")):
            v = r[k]
            if k in ("released", "completed") and v:
                v = dt.date.fromisoformat(v)
            ck.eq("Jobs Completed", rr, col, v, f"col {col}")
    bo = pg.back_orders(p)
    for r in bo["rows"]:
        rr = 6 + r["row"]
        for col, k in (("D", "priority_qty"), ("E", "priority"), ("F", "released_qty"), ("G", "brought_forward"),
                       ("H", "planned_qty"), ("M", "status"), ("AP", "colour")):
            ck.eq("Back Orders", rr, col, r[k], f"col {col}")
    cl = pg.cleaning_page(p)
    for i, r in enumerate(cl["rows"]):
        for col, k in (("G", "kind"), ("I", "gap"), ("M", "left"), ("N", "load"), ("P", "check")):
            ck.eq("Cleaning", 9 + i, col, r[k], f"col {col}")
    for r in pg.rnd_page(p)["rows"]:
        ck.eq("R&D", 6 + r["row"], "G", r["status"], "status")
    pb = pg.profile_balancing(p)
    for b in pb["blocks"]:
        ck.eq("Profile Balancing", 5 + b["slot"], "H", b["status"], "status")
        top = 33 + 44 * (b["slot"] - 1)
        for pr in b["parts"]:
            ck.eq("Profile Balancing", top + 2 + pr["t"], "H", pr["note"], "part note")
            ck.eq("Profile Balancing", top + 2 + pr["t"], "K", pr["colour"], "part colour")
    rg = pg.rg_released_jobs(p)
    for b in rg["blocks"]:
        ck.eq("RG Released Jobs", 6 + b["row"], "I", b["status"], "status")
        ck.eq("RG Released Jobs", 6 + b["row"], "K", b["check"], "check")
        top = 33 + 44 * b["row"]
        for pr in b["parts"]:
            ck.eq("RG Released Jobs", top + 2 + pr["t"], "I", pr["note"], "part note")
            ck.eq("RG Released Jobs", top + 2 + pr["t"], "G", pr["scheduled"], "part scheduled")
    pc = pg.pending_containers(p)
    for i, r in enumerate(pc["lines"]):
        ck.eq("Pending Containers", 18 + i, "C", r["part"], "part")
        ck.eq("Pending Containers", 18 + i, "H", r["qty"], "qty")
    ck.eq("Plant 40 Stock", 3, "A", pg.plant40(p)["summary"], "summary")
    ck.eq("R&D", 3, "A", p.rnd["summary"], "summary")
    return ck.report()


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1]) else 0)
