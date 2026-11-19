"""Build the data each page of the app shows (the visible tabs of the workbook).

Every function takes a computed Plan and returns plain JSON-able dicts.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from .calc import Plan, GAUGES, _fixed1, _s, _t
from .xl import (DAYS, DOW_LONG, WEEKS, blank, colour_code, is_x, isnum, key, networkdays,
                 num, to_date, xround)


def j(x: Any) -> Any:
    """Make a value JSON friendly."""
    if isinstance(x, dt.datetime):
        return x.date().isoformat()
    if isinstance(x, dt.date):
        return x.isoformat()
    if isinstance(x, float) and x.is_integer() and abs(x) < 1e15:
        return int(x)
    return x


def jl(xs):
    return [j(x) for x in xs]


def _days(p: Plan) -> list[dict]:
    return [{"d": d, "label": p.labels[d], "date": j(p.dates[d]), "week": WEEKS[d // 5],
             "dow": ["Mon", "Tue", "Wed", "Thu", "Fri"][d % 5], "is_today": p.dates[d] == p.today}
            for d in range(DAYS)]


def back_order_products(p: Plan) -> set[str]:
    return {key(b.get("product")) for b in p.st.get("back_orders", []) if not blank(b.get("product"))}


# ----------------------------------------------------------------------
def meta(p: Plan) -> dict:
    return {"today": j(p.today), "first_planning_day": j(p.first_planning_day),
            "week_a_monday": j(p.week_a), "days": _days(p), "headline": p.headline}


# ----------------------------------------------------------------------
def jobs_released(p: Plan) -> dict:
    bo = back_order_products(p)
    master_count = p.m_by_prod
    job_counts = defaultdict(int)
    for e in p.pc:
        if e["D"] != "":
            job_counts[key(e["D"])] += 1
    for r in p.st.get("rg_jobs", []):
        if not blank(r.get("job")):
            job_counts[key(r.get("job"))] += 1
    too_many_bal = len(p.bal_entries) > 24
    weeks = []
    for w in range(4):
        days = []
        stats = {"products": set(), "qty": 0, "balance": 0, "pushed": 0, "waiting": 0}
        for dd in range(5):
            d = w * 5 + dd
            rows = []
            for i in range(40):
                e = p.pc[d * 40 + i]
                inp = e["input"]
                prod, qty, job, bal, push, start = (inp.get(k) for k in ("product", "qty", "job", "balance", "push", "start"))
                check = ""
                if not all(blank(v) for v in (prod, qty, job, bal, push, start)):
                    msgs = []
                    if blank(prod) and not all(blank(v) for v in (qty, job, bal, push)):
                        msgs.append("Product missing.")
                    if not blank(prod) and key(prod) not in master_count:
                        msgs.append("Not in laser master data (0 hrs).")
                    if not blank(prod) and blank(qty) and not is_x(bal):
                        msgs.append("Quantity missing.")
                    if not blank(prod) and blank(job):
                        msgs.append("Job number missing.")
                    if not blank(job) and job_counts[key(job)] > 1:
                        msgs.append("Job number used twice.")
                    if not blank(bal) and not is_x(bal):
                        msgs.append("Balance: type X only.")
                    if not blank(push) and not is_x(push):
                        msgs.append("Push: type X only.")
                    if is_x(bal) and is_x(push):
                        msgs.append("Balance order - Push is ignored.")
                    if is_x(bal) and too_many_bal:
                        msgs.append("More balance orders than Profile Balancing holds.")
                    if not blank(prod) and to_date(start) is None:
                        msgs.append("Start Date missing - not planned yet.")
                    check = " ".join(msgs)
                if not blank(prod) and to_date(start) is None:
                    stats["waiting"] += 1
                if e["B"] != "":
                    stats["products"].add(key(e["B"]))
                    stats["qty"] += e["C"]
                    stats["pushed"] += e["AG"]
                stats["balance"] += e["T"]
                rows.append({"row": i, "product": prod, "qty": qty, "job": job, "balance": bal, "push": push,
                             "start": start, "plan_order": e["O"] if not blank(prod) else "",
                             "check": check, "back_order": key(prod) in bo if not blank(prod) else False})
            days.append({"d": d, "date": j(p.dates[d]),
                         "title": p.dates[d].strftime("%A, %d %b %Y"),
                         "total_qty": j(sum(num(r["qty"]) for r in rows)), "rows": rows})
        stats["products"] = len(stats["products"])
        weeks.append({"week": WEEKS[w], "monday": j(p.dates[w * 5]), "days": days, "stats": {k: j(v) for k, v in stats.items()}})
    return {"weeks": weeks, "week_a_monday": j(p.week_a)}


# ----------------------------------------------------------------------
def average_cutting_plan(p: Plan) -> dict:
    bo = back_order_products(p)
    rows = []
    for i, r in enumerate(p.plan):
        c = p.comp[i]
        rows.append({"k": r["k"], "product": r["A"], "plan_qty": j(r["B"]),
                     "released": jl(r["rel"]) + [j(r["rel4"])],
                     "qty": jl(r["G"]), "l1": r["H"], "l2": r["I"], "l3": r["J"], "ave": r["K"],
                     "weeks": jl(r["weeks"]), "total": j(r["DG"]),
                     "hrs_unit": [r["DI"], r["DJ"], r["DK"], r["DL"]], "hrs_8mm": r["DM"],
                     "unscheduled": j(r["DN"]), "status": r["DO"],
                     "colour": c["codes"], "back_order": key(r["A"]) in bo})
    bal = []
    for b in p.plan_bal:
        sl = p.slots[b["slot"] - 1]
        bal.append({"kind": b["kind"], "label": b["A"], "profiles": j(b["B"]), "released": j(b["released"]),
                    "start": j(b["start"]), "qty": jl(b["G"]), "l1": b["H"], "l2": b["I"], "l3": b["J"],
                    "ave": b["K"], "weeks": jl(b["weeks"]), "total": j(b["DG"]), "status": b["DO"],
                    "colour": sl["day_codes"]})
    totals = [{"qty": j(t["qty"]), "load": t["load"], "capacity": p.cap[d]} for d, t in enumerate(p.day_totals)]
    return {"headline": p.headline, "shifts": p.s.get("shifts"), "oee": p.oee,
            "products_count": len(p.plan), "days": _days(p), "rows": rows, "balance_rows": bal,
            "totals": totals, "week_totals": jl(p.week_totals),
            "avg_per_day": (sum(p.week_totals)) / 20, "unscheduled": j(p.unscheduled)}


def management_report(p: Plan) -> dict:
    out = average_cutting_plan(p)
    out["header_notes"] = p.st.get("mgmt_report", {}).get("header_notes", {})
    return out


# ----------------------------------------------------------------------
def schedule_per_laser(p: Plan) -> dict:
    bo = back_order_products(p)
    days = []
    for d in range(DAYS):
        lasers = []
        for l in range(3):
            rows = p.spl[d][l]
            list_rows = [r for r in rows if r["sec"] in ("part", "rnd")]
            prods = {key(r["A"]) for r in list_rows if not blank(r["A"])}
            out_qty = sum(num(r["D"]) for r in rows if r["sec"] in ("part", "rnd", "bal"))
            stock = sum(num(r["F"]) for r in rows if r["sec"] != "push")
            gauges = []
            for g in GAUGES:
                v = sum(num(r["D"]) for r in list_rows if isnum(r["C"]) and float(r["C"]) == g)
                if v > 0:
                    gauges.append({"gauge": g, "qty": j(v)})
            warn = []
            if p.lp_line_max[d][l] > 76:
                warn.append("More than 76 lines - list cut off")
            if any(str(r["A"]).startswith("BAL ") for r in rows if r["sec"] == "bal"):
                warn.append("BALANCE order - cut these lines first so the trolley can be balanced")
            if any(str(r["A"]).startswith("RG ") for r in rows if r["sec"] == "bal"):
                warn.append("RG job lines (RG ...) - planned from their Start Date")
            load = p.day_totals[d]["load"][l]
            cap = p.cap[d][l]
            lasers.append({
                "laser": l + 1, "load": load,
                "hours_text": f"{_fixed1(load * cap)}/{_fixed1(cap)}h",
                "products": len(prods), "output": j(out_qty), "stock_taken": j(stock),
                "gauges": gauges, "stock_saves_h": p.stock_h[d][l], "warnings": warn,
                "rows": [{"key": r["key"], "sec": r["sec"], "product": r["A"], "part": r["B"], "gauge": j(r["C"]),
                          "qty": j(r["D"]), "stock_comment": r["E"], "stock_taken": j(r["F"]),
                          "taken": r["G"], "sic": r["Hs"], "comment": r["I"],
                          "push_qty": j(r["push_qty"]), "done": j(r["done"]), "hrs_piece": r["AD"],
                          "complete": num(r["D"]) > 0 and (num(r["F"]) >= num(r["D"]) or (isnum(r["Hs"]) and r["Hs"] + num(r["F"]) >= num(r["D"]))),
                          "back_order": key(r["A"]) in bo}
                         for r in rows],
            })
        days.append({"d": d, "label": p.labels[d], "date": j(p.dates[d]), "is_today": p.dates[d] == p.today,
                     "title": f"WEEK {WEEKS[d // 5]}   -   {DOW_LONG[d % 5]}   {p.dates[d].strftime('%d %b %Y')}",
                     "lasers": lasers})
    return {"days": days}


# ----------------------------------------------------------------------
def output(p: Plan) -> dict:
    rows = []
    plan_keys = {key(r["A"]) for r in p.plan}
    for d in range(DAYS):
        sched = 0.0
        cut = 0.0
        sic_typed = 0
        worked = set()
        for l in range(3):
            for r in p.spl[d][l]:
                sched += num(r["D"]) - num(r["F"])
                cut += num(r["cut"])
                if isnum(r["Hs"]):
                    sic_typed += 1
                if num(r["cut"]) > 0 and key(r["A"]) in plan_keys:
                    worked.add(key(r["A"]))
        tb = sum(c["towbars"][d] for c in p.comp) - (sum(c["towbars"][d - 1] for c in p.comp) if d else 0)
        adherence = cut / sched if (sched > 0 and sic_typed > 0) else ""
        rows.append({"d": d, "week": WEEKS[d // 5], "day": ["Mon", "Tue", "Wed", "Thu", "Fri"][d % 5],
                     "capacity": p.day_totals[d]["load"][:3],
                     "products": [sum(1 for r in p.plan if r[c][d] > 1e-9) for c in ("H", "I", "J")],
                     "qty": j(p.day_totals[d]["qty"]), "scheduled": j(sched), "cut": j(cut),
                     "adherence": adherence, "worked": len(worked), "towbars": j(tb),
                     "hours_saved": sum(p.stock_h[d]), "hours_pushed": sum(p.pushed_h[d])})
    num_adh = [r for r in rows if isnum(r["adherence"])]
    tot = {"qty": j(sum(r["qty"] for r in rows)), "scheduled": j(sum(r["scheduled"] for r in rows)),
           "cut": j(sum(r["cut"] for r in rows)),
           "adherence": (sum(r["cut"] for r in num_adh) / sum(r["scheduled"] for r in num_adh)) if num_adh and sum(r["scheduled"] for r in num_adh) else "",
           "towbars": j(sum(r["towbars"] for r in rows)),
           "hours_saved": sum(r["hours_saved"] for r in rows), "hours_pushed": sum(r["hours_pushed"] for r in rows)}
    return {"rows": rows, "total": tot}


# ----------------------------------------------------------------------
def jobs_completed(p: Plan) -> dict:
    report = to_date(p.st.get("jobs_completed", {}).get("report_date")) or p.today
    s = p.s
    green, red = num(s.get("lead_green")), num(s.get("lead_red"))
    due_only = bool(s.get("colour_due_only"))
    plan_row = {key(r["A"]): i for i, r in enumerate(p.plan)}
    rows = []
    earlier = defaultdict(float)
    for e in sorted((e for e in p.pc if e["R"] != ""), key=lambda e: e["R"]):
        i = plan_row.get(key(e["B"]))
        M = earlier[key(e["B"])]
        earlier[key(e["B"])] += e["C"]
        c = p.comp[i] if i is not None else None
        N = c["X"] if c else 0
        O = min(e["C"], max(0, N - M))
        if c is None or c["B"] == 0:
            G = "n/a"
        else:
            G = 0 if e["C"] == 0 else O / e["C"]
        E = ""
        if isnum(G) and G >= 0.999999:
            target = (M + e["C"]) * c["B"] - 0.000001
            n = sum(1 for v in c["cum"] if v < target)
            E = p.dates[min(20, n + 1) - 1]
        F = max(0, networkdays(e["G"], E if isinstance(E, dt.date) else report) - 1)
        if not isnum(G):
            H = "No laser parts - not tracked"
        elif F < green:
            H = "Completed" if E != "" else "OK - in the queue"
        elif F <= red:
            H = "Completed (slow)" if E != "" else "ALERT - check why it is not completed"
        else:
            H = "Completed (overdue)" if E != "" else "OVERDUE - investigate"
        Q = colour_code(G, due_red=(not due_only) or (e["G"] <= p.today)) if isnum(G) else ""
        rows.append({"n": e["R"], "released": j(e["G"]), "product": e["B"], "qty": j(e["C"]), "job": e["D"],
                     "completed": j(E), "lead_days": F, "pct": G, "status": H, "colour": Q,
                     "done_qty": j(O)})
    return {"report_date": j(report), "report_date_typed": p.st.get("jobs_completed", {}).get("report_date"),
            "lead_green": green, "lead_red": red, "rows": rows}


# ----------------------------------------------------------------------
def back_orders(p: Plan) -> dict:
    master = p.m_by_prod
    rel_qty = defaultdict(float)
    for e in p.pc:
        if e["B"] != "":
            rel_qty[key(e["B"])] += e["C"]
    plan_idx = {key(r["A"]): i for i, r in enumerate(p.plan)}
    step = num(p.s.get("trolley"))
    rows_in = sorted(p.st.get("back_orders", []), key=lambda r: r.get("row", 0))
    seen = set()
    out = []
    for r in rows_in:
        prod = r.get("product")
        pk = key(prod)
        dup = not blank(prod) and pk in seen
        if not blank(prod):
            seen.add(pk)
        sort_ok = not blank(prod) and not dup
        qty = r.get("qty")
        D = "" if not sort_ok else (999999 if blank(qty) else (qty if step <= 0 else _ceiling(num(qty), step)))
        F = rel_qty.get(pk, 0) if not blank(prod) else ""
        G = "" if not sort_ok else (F if D >= 999999 else min(D, F))
        i = plan_idx.get(pk)
        H = p.plan[i]["DG"] if (i is not None and not blank(prod)) else (0 if not blank(prod) else "")
        if blank(prod):
            M = ""
        elif dup:
            M = "Duplicate - ignored (already listed above)"
        elif pk not in master:
            M = "Not in laser master data - check the number"
        elif F == 0:
            M = "Not on Jobs Released yet"
        else:
            M = "Highlighted (purple) on Jobs Released, Schedule per Laser and the plan - push it with Push (X) on Jobs Released"
        AO = ""
        if sort_ok and num(G) > 0 and i is not None:
            AO = min(1, p.comp[i]["X"] / G)
        start = to_date(r.get("start")) or (p.first_planning_day if not blank(prod) else None)
        AP = colour_code(AO, due_red=(not p.s.get("colour_due_only")) or (start is not None and start <= p.today)) if isnum(AO) else ""
        out.append({**r, "priority_qty": j(D), "released_qty": j(F), "brought_forward": j(G), "planned_qty": j(H),
                    "status": M, "start_used": j(start), "share_done": AO, "colour": AP, "dup": dup,
                    "sort": (to_date(r.get("date")) or dt.date(2200, 1, 1), r.get("row", 0)) if sort_ok else None})
    ranked = sorted((x for x in out if x["sort"] is not None), key=lambda x: x["sort"])
    for n, x in enumerate(ranked):
        x["priority"] = n + 1
    for x in out:
        x.setdefault("priority", "")
        x.pop("sort", None)
    return {"rows": out, "count": len(ranked), "released": sum(1 for x in out if num(x["released_qty"]) > 0)}


def _ceiling(x: float, step: float) -> float:
    import math
    return math.ceil(x / step - 1e-12) * step if step else x


# ----------------------------------------------------------------------
def _slot_block(p: Plan, sl: dict) -> dict:
    parts = []
    for pr in sl["parts"]:
        if pr["V"] is None:
            continue
        a = next((a for a in p.active if a["part"] is pr), None)
        sched = a["BC"] if a else ""
        first = p.labels[a["BD"]] if (a and isnum(a["BD"])) else ""
        last = p.labels[a["BE"]] if (a and isnum(a["BE"])) else ""
        note = ""
        typed = num(pr["typed"])
        if typed > 0 and pr["AE"] == 0:
            note = "Not laser cut - quantity ignored"
        elif typed > 0 and pr["Z"] == 0:
            note = "No profiles per product in the master data"
        elif typed > 0 and pr["AC"] == 0:
            note = "No cutting time in the master data - not scheduled"
        elif a is not None:
            if sl["s"] > 24 and sl["LN"] == 99:
                note = "Select a Start Date - not planned yet"
            elif a["BC"] == 0:
                note = "Not scheduled - no capacity in the 4 weeks"
            elif a["BC"] < pr["AB"]:
                note = f"Partly scheduled {_t(a['BC'])} of {_t(pr['AB'])} from {first}"
            else:
                note = f"Scheduled {first}" + (f" to {last}" if a["BE"] > a["BD"] else "")
        elif pr["AE"] == 0:
            note = "Not laser cut"
        parts.append({"t": pr["t"], "part": pr["W"], "gauge": j(pr["X"]), "laser": pr["Y"], "profiles": j(pr["Z"]),
                      "qty": pr["typed"], "total": j(pr["AB"]) if pr["AB"] else "", "hours": pr["AD"] or "",
                      "scheduled": j(sched), "first_day": first, "note": note,
                      "done": j(pr["LR"]) if num(pr["AB"]) > 0 else "", "pct": pr.get("LS", ""), "colour": pr.get("NK", "")})
    return {"slot": sl["s"], "product": sl["C"], "job": j(sl["D"]), "released": j(sl["F"]),
            "date_used": j(sl["LM"]), "date_typed": sl["date_in"], "label": sl["P"],
            "profiles": j(sl["H"]), "hours": sl["I"] + sl["J"] + sl["K"], "status": sl["O"],
            "completed": sl.get("LU", ""), "colour": sl.get("NL", ""), "parts": parts,
            "typed_without_order": sl["B"] == "" and sl["Q"] > 0}


def profile_balancing(p: Plan) -> dict:
    blocks = []
    for sl in p.slots[:24]:
        b = _slot_block(p, sl)
        e = sl.get("entry")
        b["entry"] = {"day": e["day"], "row": e["row"]} if e else None
        blocks.append(b)
    warn = []
    if len(p.bal_entries) > 24:
        warn.append("WARNING: more than 24 balance orders - Profile Balancing holds 24, the rest are not planned.")
    if p.n_active_bal > 300:
        warn.append("WARNING: more than 300 balance parts - the last ones are not scheduled.")
    return {"blocks": blocks, "warnings": warn}


def rg_released_jobs(p: Plan) -> dict:
    rg_in = {r["row"]: r for r in p.st.get("rg_jobs", [])}
    job_counts = defaultdict(int)
    for e in p.pc:
        if e["D"] != "":
            job_counts[key(e["D"])] += 1
    for r in rg_in.values():
        if not blank(r.get("job")):
            job_counts[key(r.get("job"))] += 1
    blocks = []
    for sl in p.slots[24:]:
        i = sl["s"] - 25
        r = rg_in.get(i, {})
        b = _slot_block(p, sl)
        job, prod, rel, push, start = (r.get(k) for k in ("job", "product", "released", "push", "start"))
        msgs = []
        if not all(blank(v) for v in (job, prod, rel, push, start)):
            if blank(prod) and not all(blank(v) for v in (job, rel, push, start)):
                msgs.append("Product missing.")
            if not blank(prod) and key(prod) not in p.m_by_prod:
                msgs.append("Not in laser master data (0 hrs).")
            if not blank(prod) and blank(job):
                msgs.append("Job number missing.")
            if not blank(job) and job_counts[key(job)] > 1:
                msgs.append("Job number used twice.")
            if not blank(prod) and to_date(rel) is None:
                msgs.append("Released date missing.")
            if not blank(push) and not is_x(push):
                msgs.append("Push: type X only.")
            if to_date(start) and to_date(rel) and to_date(start) < to_date(rel):
                msgs.append("Start Date is before Released - planned from the release day.")
        b.update({"row": i, "input": {"job": job, "product": prod, "released": rel, "push": push, "start": start},
                  "check": " ".join(msgs)})
        blocks.append(b)
    return {"blocks": blocks}


# ----------------------------------------------------------------------
def rnd_page(p: Plan) -> dict:
    by_row = {r.get("row"): r for r in p.rnd["rows"]}
    rows = []
    for i in range(60):
        r = by_row.get(i, {})
        rows.append({"row": i, **{k: r.get(k) for k in ("program", "gauge", "duration", "laser", "start")},
                     "status": r.get("status", ""), "day": r.get("day", ""), "laser_no": r.get("laser_no", "")})
    return {"summary": p.rnd["summary"], "rows": rows}


def cleaning_page(p: Plan) -> dict:
    rows = []
    for c in p.cleaning:
        w, l = c["week"], c["laser"]
        d = w * 5 + 4
        inp = c["row"]
        gap = c["gap"]
        L = p.fri_hours
        load = p.day_totals[d]["load"][l - 1]
        st = inp.get("start_time")
        end = ""
        if st and gap > 0:
            try:
                hh, mm = map(int, str(st).split(":")[:2])
                tot = (hh * 60 + mm + int(round(gap * 60))) % (24 * 60)
                end = f"{tot // 60:02d}:{tot % 60:02d}"
            except ValueError:
                end = ""
        check = ""
        if gap > L:
            check = "Cleaning is longer than the Friday shift - this laser does not cut that day"
        elif gap > 0 and load > 1.0001:
            check = f"Planned load is {xround(load * 100, 0):.0f}% of the reduced hours - this laser is overloaded while it is being cleaned"
        rows.append({"week": WEEKS[w], "w": w, "laser": l, "date": j(p.dates[d]), "light": inp.get("light"),
                     "heavy": inp.get("heavy"), "kind": c["kind"],
                     "what": {"Heavy": "Change slats + clean inside the laser", "Light": "Change slats only"}.get(c["kind"], "-"),
                     "gap": gap, "start_time": st, "end_time": end, "hours": L, "left": max(0, L - gap),
                     "load": load, "comment": inp.get("comment"), "check": check})
    return {"rows": rows, "light_h": p.s.get("light_clean_h"), "heavy_h": p.s.get("heavy_clean_h")}


# ----------------------------------------------------------------------
def plant40(p: Plan) -> dict:
    rows = [{"bms": r["A"], "description": r["B"], "products": r["C"], "qty_product": j(r["D"]),
             "consignment": r["E"], "qty_shipped": j(r["F"]), "received": r["G"], "in_stock": j(r["H"]),
             "taken": j(r["I"]), "left": j(r["J"]), "matches": r["K"],
             "override": r["A"] in p.st.get("p40_qty_override", {})} for r in p.p40]
    notrecv_all = sum(1 for r in p.bczb_rows if str(r.get("W", "")).startswith("NOT"))
    summary = (f"Stock lines used by the planner: {sum(1 for r in p.p40 if r['A'])}   |   in stock (containers received): "
               f"{xround(sum(num(r['H']) for r in p.p40), 0):,.0f} pcs   |   still in containers not received: "
               f"{xround(sum(num(r['F']) for r in p.p40) - sum(num(r['H']) for r in p.p40), 0):,.0f} pcs   |   taken by the plan: "
               f"{xround(sum(num(r['I']) for r in p.p40), 0):,.0f} pcs   |   not received, all types: {notrecv_all} lines (see Pending Containers)")
    if sum(r["T"] for r in p.bczb_rows) > 250:
        summary += "   WARNING: more than 250 profile lines - the extra lines are not shown here"
    return {"summary": summary, "rows": rows}


def bczb(p: Plan) -> dict:
    cols = p.st.get("bczb_columns") or []
    rows = []
    for r in p.bczb_rows:
        rows.append({k: j(r.get(k)) for k in "A B C D E F G H I J K L M N O P Q R T V W".split()})
    return {"columns": cols, "rows": rows,
            "totals": {"Q": sum(num(r.get("Q")) for r in p.bczb_rows), "R": sum(num(r.get("R")) for r in p.bczb_rows)}}


def pending_containers(p: Plan) -> dict:
    cont = p.s.get("containers", [])
    not_recv = [c["name"] for c in cont if not c.get("received")]
    nr = [r for r in p.bczb_rows if r.get("V") == "No"]
    types = ["Profile", "Ball Neck", "Cross Beam", "Weld Assy", "Fastener Kit", "Fitting Instructions"]
    by_type = []
    for t in types:
        rs = [r for r in nr if key(r.get("C")) == key(t)]
        by_type.append({"type": t, "lines": len(rs), "pieces": j(sum(num(r.get("H")) for r in rs)),
                        "used": "Yes - only lines with a BMS Part Number" if t == "Profile" else "No - for information"})
    other = [r for r in nr if key(r.get("C")) not in {key(t) for t in types}]
    by_type.append({"type": "Other", "lines": len(other), "pieces": j(sum(num(r.get("H")) for r in other)), "used": ""})
    lines = [{"n": i + 1, "consignment": _s(r.get("G")), "part": _s(r.get("A")), "description": _s(r.get("B")),
              "type": _s(r.get("C")), "bms": _s(r.get("E")), "products": _s(r.get("D")), "qty": j(r.get("H")),
              "used": "YES - Profile used by the planner" if r.get("T") == 1 else "No - for information"}
             for i, r in enumerate(nr[:400])]
    return {"not_received": not_recv,
            "summary": f"Lines still to arrive: {sum(1 for r in p.bczb_rows if str(r.get('W','')).startswith('NOT'))}   |   pieces: "
                       f"{xround(sum(num(r.get('H')) for r in nr), 0):,.0f}   |   Profile lines the planner is waiting for: "
                       f"{sum(1 for r in nr if r.get('T') == 1)}",
            "by_type": by_type, "total_lines": len(nr), "total_pieces": j(sum(num(r.get("H")) for r in nr)), "lines": lines}


# ----------------------------------------------------------------------
def profiles(p: Plan) -> dict:
    rows = [{"i": i, **{k: j(r.get(k)) for k in ("product", "part", "gauge", "profiles", "perimeter", "notes", "operations", "laser")},
             "speed": j(r["speed"]), "oee": r["oee"], "mins": r["mins"], "hrs": r["hrs"]}
            for i, r in enumerate(p.master)]
    return {"rows": rows, "products": len(p.m_by_prod)}


def settings(p: Plan) -> dict:
    s = p.s
    limits = []
    default = num(s.get("max_qty_default"))
    tro = num(s.get("trolley"))
    lims = s.get("job_size_limits") or []
    for i, r in enumerate(lims):
        used = r.get("max_per_day") if isnum(r.get("max_per_day")) else default
        label = (f"Job released as {_t(r.get('up_to'))} or less" if i < len(lims) - 1
                 else f"More than {_t(lims[i - 1].get('up_to')) if i else ''}  (a bigger job)")
        limits.append({**r, "label": label, "used": used,
                       "check": f"Less than one trolley ({_t(tro)}) - jobs of this size will NOT be scheduled" if used < tro else ""})
    cs = []
    for r in p.st.get("cutting_speed", []):
        inv = {}
        for l in ("l1", "l2", "l3"):
            v = r.get(l)
            inv[l] = 1 / v / 10 if isnum(v) and v else None
        b = r.get("bms_inverse")
        cs.append({**r, "inv": inv, "bms_speed": 1 / (b * 10) if isnum(b) and b else None})
    return {"settings": s, "today": j(p.today), "first_planning_day": j(p.first_planning_day),
            "limits": limits, "cutting_speed": cs, "factor_l1": p.f1, "factor_l3": p.f3}


def raw_table(p: Plan, cols_key: str, rows_key: str) -> dict:
    return {"columns": p.st.get(cols_key) or [], "rows": p.st.get(rows_key) or []}


PAGES = {
    "jobs-released": jobs_released,
    "average-cutting-plan": average_cutting_plan,
    "management-report": management_report,
    "schedule-per-laser": schedule_per_laser,
    "output": output,
    "jobs-completed": jobs_completed,
    "back-orders": back_orders,
    "profile-balancing": profile_balancing,
    "rg-released-jobs": rg_released_jobs,
    "rnd": rnd_page,
    "cleaning": cleaning_page,
    "plant-40-stock": plant40,
    "bczb-list": bczb,
    "pending-containers": pending_containers,
    "profiles-per-product": profiles,
    "data": settings,
    "order-book": lambda p: raw_table(p, "order_book_columns", "order_book"),
    "shutdown-stock": lambda p: raw_table(p, "shutdown_columns", "shutdown_stock"),
}
