"""The planning engine.

This module replaces the calculation tabs of the Excel planner (Priority Calc,
Balance Calc, Job Schedule, Plan Calc, Laser Detail, Laser Parts, Stock Calc,
Completion Calc) plus the formulas behind the visible tabs. Each stage is named
after the tab it replaces so the logic can be traced back to the workbook.

Input:  the stored state (see state.py) - only what people type.
Output: a Plan object with every computed table.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from .xl import (DAYS, blank, colour_code, day_index, day_label, is_x, isnum, key,
                 num, plan_dates, to_date, workday, xround, xroundup)

N_ENTRIES = 800          # Jobs Released: 20 days x 40 rows
N_LINES = 1600           # two lines per entry (priority / normal)
N_BAL_LINES = 300        # balance + RG part lines
N_SLOTS = 48             # 24 balance slots + 24 RG jobs
PLAN_ROWS = 270          # products on the Average Cutting Plan
MAX_LASER_PARTS = 2520
SPL_SECTIONS = (("push", 12), ("bal", 30), ("part", 76), ("rnd", 4))
GAUGES = [1.6, 2, 3, 3.5, 4, 6, 8, 10, 12]
BIG = 1_000_000_000


class Plan:
    def __init__(self, state: dict, today: dt.date | None = None):
        self.st = state
        s = state["settings"]
        self.s = s
        self.today = to_date(s.get("planning_date")) or today or dt.date.today()
        self.first_planning_day = workday(self.today, 1)
        self.week_a = to_date(s.get("week_a_monday")) or (self.today - dt.timedelta(days=self.today.weekday()))
        self.dates = plan_dates(self.week_a)
        self.labels = [day_label(d) for d in range(DAYS)]
        self.trolley = num(s.get("trolley")) or 25
        self.trolley40 = num(s.get("trolley_40"))
        self.gauge_moved = s.get("gauge_moved")
        self.oee = num(s.get("oee"))
        self.line_capacity = int(num(s.get("line_capacity")) or 600)
        self.run()

    # ------------------------------------------------------------------
    def idx(self, x: Any) -> int | None:
        d = to_date(x)
        return None if d is None else day_index(self.dates, d)

    def run(self) -> None:
        self.calc_capacity()
        self.calc_master()
        self.calc_priority()
        self.calc_balance_static()
        self.calc_lines()
        self.calc_job_schedule()
        self.calc_balance_dynamic()
        self.calc_plan()
        self.calc_laser_detail()
        self.calc_laser_parts()
        self.calc_stock_lists()
        self.calc_schedule_per_laser()
        self.calc_day_hours()
        self.calc_plan_totals()
        self.calc_completion()
        self.calc_balance_done()

    # ------------------------------------------------------------------
    # Data + Cleaning -> laser hours per day (Average Cutting Plan row 3)
    def calc_capacity(self) -> None:
        s = self.s
        two = num(s.get("shifts")) == 2
        mon_thu = num(s["hours_mon_thu"][1] if two else s["hours_mon_thu"][0])
        fri = num(s["hours_fri"][1] if two else s["hours_fri"][0])
        self.fri_hours = fri
        clean = {(c["week"], c["laser"]): c for c in self.st.get("cleaning", [])}
        self.cleaning = []
        for w in range(4):
            for l in (1, 2, 3):
                c = clean.get((w, l), {})
                kind = "Heavy" if is_x(c.get("heavy")) else ("Light" if is_x(c.get("light")) else "None")
                gap = num(s.get("heavy_clean_h")) if kind == "Heavy" else (num(s.get("light_clean_h")) if kind == "Light" else 0)
                self.cleaning.append({"week": w, "laser": l, "kind": kind, "gap": gap, "row": c})
        self.cap = []  # per day: [L1, L2, L3, avg]
        for d in range(DAYS):
            if d % 5 == 4:
                w = d // 5
                ls = [max(0, fri - self.cleaning[w * 3 + l]["gap"]) for l in range(3)]
                self.cap.append(ls + [sum(ls) / 3])
            else:
                self.cap.append([mon_thu] * 4)

    # ------------------------------------------------------------------
    # Profiles per Product + Cutting Speed
    def calc_master(self) -> None:
        speeds = {}
        for r in self.st.get("cutting_speed", []):
            speeds[key(r.get("gauge"))] = r
        self.speeds = speeds
        rows = []
        for i, p in enumerate(self.st.get("profiles", [])):
            laser = p.get("laser")
            lkey = key(laser)
            speed = None
            sp = speeds.get(key(p.get("gauge")))
            col = {"LASER 1": "l1", "LASER 2": "l2", "LASER 3": "l3"}.get(lkey)
            if sp is not None and col is not None:
                speed = sp.get(col)
            hrs_min = 0.0
            if isnum(speed) and speed != 0 and self.oee:
                try:
                    hrs_min = ((1 / speed) * (num(p.get("perimeter")) / 1000) * num(p.get("profiles"))) / self.oee
                except ZeroDivisionError:
                    hrs_min = 0.0
            rows.append({**p, "speed": speed if isnum(speed) else None, "oee": self.oee,
                         "mins": hrs_min, "hrs": hrs_min / 60 if hrs_min else 0.0,
                         "is_laser": lkey.startswith("LASER"), "laser_no": _laser_no(laser)})
        self.master = rows
        self.m_by_prod: dict[str, list[int]] = defaultdict(list)
        self.m_laser_by_prod: dict[str, list[int]] = defaultdict(list)
        self.hrs_l = defaultdict(lambda: [0.0, 0.0, 0.0])
        self.hrs_8 = defaultdict(float)
        self.prof_laser = defaultdict(float)
        gm = self.gauge_moved
        for i, r in enumerate(rows):
            pk = key(r.get("product"))
            if pk == "":
                continue
            self.m_by_prod[pk].append(i)
            if r["is_laser"]:
                self.m_laser_by_prod[pk].append(i)
                self.prof_laser[pk] += num(r.get("profiles"))
            lk = key(r.get("laser"))
            if lk in ("LASER 1", "LASER 2", "LASER 3"):
                self.hrs_l[pk][int(lk[-1]) - 1] += num(r["hrs"])
                if lk == "LASER 2" and _eq_num(r.get("gauge"), gm):
                    self.hrs_8[pk] += num(r["hrs"])
        self.master_parts = {key(r.get("part")) for r in rows if not blank(r.get("part"))}
        # Job Schedule B5 / B6: hour factors when 8 mm work moves off Laser 2
        sp = speeds.get(key(gm))
        f1 = 1.0
        try:
            f1 = max(1, sp["l2"] / sp["l1"])
        except Exception:
            f1 = 1.0
        try:
            f3 = max(f1, sp["l2"] / sp["l3"])
        except Exception:
            f3 = f1
        self.f1, self.f3 = f1, f3

    def known_product(self, p: Any) -> bool:
        return key(p) in self.m_by_prod

    # ------------------------------------------------------------------
    # Priority Calc
    def calc_priority(self) -> None:
        jobs = {(j["day"], j["row"]): j for j in self.st.get("jobs", [])}
        self.job_input = jobs
        limits = self.s.get("job_size_limits") or []
        default_max = num(self.s.get("max_qty_default"))

        def lim(i):
            r = limits[i] if i < len(limits) else {}
            return r.get("max_per_day") if isnum(r.get("max_per_day")) else default_max

        def up(i):
            r = limits[i] if i < len(limits) else {}
            return num(r.get("up_to"))

        E = []
        counts = defaultdict(int)
        cum_qty = defaultdict(float)
        seq = 0
        slot = 0
        for a in range(N_ENTRIES):
            d, i = divmod(a, 40)
            j = jobs.get((d, i), {})
            prod, start = j.get("product"), j.get("start")
            start_d = to_date(start)
            S = prod if (not blank(prod) and start_d is not None) else ""
            T = 1 if (S != "" and is_x(j.get("balance"))) else 0
            B = S if (S != "" and T == 0) else ""
            C = num(j.get("qty")) if B != "" else 0
            D = (j.get("job") if not blank(j.get("job")) else "") if S != "" else ""
            Eday = max(d, self.idx(start_d) if start_d is not None else 0)
            pk = key(B)
            Jq = cum_qty[pk] if B != "" else 0
            M = 0
            AI = 0
            if B != "":
                counts[pk] += 1
                AI = counts[pk]
                M = 1 if AI == 1 else 0
                cum_qty[pk] += C
                seq += 1
            U = ""
            if T == 1:
                slot += 1
                U = slot
            if C <= 0:
                AL = 0
            elif C <= up(0):
                AL = lim(0)
            elif C <= up(1):
                AL = lim(1)
            elif C <= up(2):
                AL = lim(2)
            elif C <= up(3):
                AL = lim(3)
            else:
                AL = lim(4)
            E.append({
                "a": a + 1, "day": d, "row": i, "S": S, "T": T, "B": B, "C": C, "D": D,
                "E": Eday, "G": self.dates[d], "J": Jq, "K": 0, "L": C, "M": M,
                "AG": 1 if (B != "" and is_x(j.get("push"))) else 0,
                "AI": AI, "AJ": f"{B}|{AI}" if B != "" else "", "AL": AL,
                "Q": self.trolley40 if C == 2 * self.trolley40 else self.trolley,
                "R": seq if B != "" else "", "U": U, "AK": 0, "input": j,
            })
        pushed = {key(e["B"]) for e in E if e["AG"] == 1}
        for e in E:
            e["AH"] = 1 if (e["B"] != "" and key(e["B"]) in pushed) else 0
            e["N"] = (1000 + e["a"] if e["AH"] == 1 else 10000 + e["a"]) if e["M"] == 1 else ""
        firsts = sorted((e["N"], e["a"]) for e in E if e["M"] == 1)
        order = {a: n + 1 for n, (_, a) in enumerate(firsts)}
        for e in E:
            e["O"] = order.get(e["a"], "") if e["M"] == 1 else ""
        self.pc = E
        self.bal_entries = [e for e in E if e["T"] == 1]          # slot k -> entry (Priority V)
        self.products = [E[a - 1]["B"] for _, a in firsts][:PLAN_ROWS]

    # ------------------------------------------------------------------
    # Balance Calc (static part: slots, parts, active part list)
    def calc_balance_static(self) -> None:
        rg = {r["row"]: r for r in self.st.get("rg_jobs", [])}
        slots = []
        for s in range(1, N_SLOTS + 1):
            if s <= 24:
                e = self.bal_entries[s - 1] if s <= len(self.bal_entries) else None
                if e is not None:
                    inp = e["input"]
                    sl = {"s": s, "B": e["a"], "C": e["S"], "D": e["D"], "E": e["E"], "F": e["G"],
                          "qty_in": inp.get("balance_qty") or {}, "date_in": inp.get("balance_date"),
                          "entry": e}
                else:
                    sl = {"s": s, "B": "", "C": "", "D": "", "E": "", "F": "", "qty_in": {}, "date_in": None, "entry": None}
            else:
                r = rg.get(s - 25, {})
                prod = r.get("product")
                prod_t = str(prod).strip() if not blank(prod) else ""
                Bv = 1 if prod_t != "" else ""
                rel = to_date(r.get("released"))
                sl = {"s": s, "B": Bv, "C": prod_t if Bv != "" else "",
                      "D": (r.get("job") if not blank(r.get("job")) else "") if Bv != "" else "",
                      "E": (self.idx(rel) if (Bv != "" and rel is not None) else 0),
                      "F": rel if (Bv != "" and rel is not None) else "",
                      "qty_in": r.get("qty") or {}, "date_in": r.get("start"), "rg": r}
            sl["G"] = len(self.m_by_prod.get(key(sl["C"]), [])) if sl["C"] != "" else 0
            # label (P), dates (LM, LN, LO), push (LP)
            if s <= 24:
                sl["P"] = f"BAL-{sl['D']} {sl['C']}" if sl["B"] != "" else ""
                if sl["B"] != "":
                    lm = to_date(sl["date_in"]) or self.first_planning_day
                    sl["LM"] = lm
                    sl["LN"] = self.idx(lm)
                    sl["LO"] = sl["LN"]
                else:
                    sl["LM"] = sl["LN"] = sl["LO"] = ""
                sl["LP"] = 0
            else:
                i = s - 24
                if sl["B"] != "":
                    sl["P"] = (f"RG{i}" if sl["D"] == "" else f"RG-{sl['D']}") + f" {sl['C']}"
                    lm = to_date(sl["date_in"])
                    sl["LM"] = lm if lm is not None else ""
                    sl["LN"] = self.idx(lm) if lm is not None else 99
                    sl["LO"] = 99 if sl["LN"] == 99 else max(num(sl["E"]), sl["LN"])
                    sl["LP"] = 1 if is_x(sl["rg"].get("push")) else 0
                else:
                    sl["P"] = ""
                    sl["LM"] = sl["LN"] = sl["LO"] = ""
                    sl["LP"] = 0
            slots.append(sl)
        # part rows: 40 per slot
        parts = []
        active = []
        gm = self.gauge_moved
        for sl in slots:
            mrows = self.m_by_prod.get(key(sl["C"]), []) if sl["C"] != "" else []
            sl["parts"] = []
            for t in range(1, 41):
                U = sl["C"]
                V = mrows[t - 1] if (U != "" and t <= sl["G"]) else None
                m = self.master[V] if V is not None else {}
                Y = (m.get("laser") if not blank(m.get("laser")) else "") if V is not None else ""
                Z = num(m.get("profiles")) if V is not None else 0
                AA = num(m.get("hrs")) if V is not None else 0
                typed = sl["qty_in"].get(str(t))
                # Balance: qty typed per product (x profiles). RG: pieces typed directly.
                if U == "":
                    AB = 0
                elif sl["s"] <= 24:
                    AB = num(typed) * Z
                else:
                    AB = num(typed)
                AC = AA / Z if (V is not None and Z > 0) else 0
                AE = _laser_no(Y) if (V is not None and key(Y)[:5] == "LASER") else 0
                pr = {"s": sl["s"], "t": t, "U": U, "V": V,
                      "W": m.get("part") if V is not None else "",
                      "X": m.get("gauge") if V is not None else "",
                      "Y": Y, "Z": Z, "AA": AA, "typed": typed, "AB": AB, "AC": AC, "AD": AB * AC, "AE": AE,
                      "AI": 1 if (AE == 2 and V is not None and _eq_num(m.get("gauge"), gm)) else 0}
                pr["AJ"] = 1 if (AB > 0 and AE > 0 and AC > 0) else 0
                if pr["AJ"]:
                    active.append(pr)
                    pr["AK"] = len(active)
                else:
                    pr["AK"] = ""
                sl["parts"].append(pr)
                parts.append(pr)
            sl["H"] = sum(p["AB"] for p in sl["parts"] if p["AJ"] == 1)
            sl["I"] = sum(p["AD"] for p in sl["parts"] if p["AE"] == 1)
            sl["J"] = sum(p["AD"] for p in sl["parts"] if p["AE"] == 2)
            sl["K"] = sum(p["AD"] for p in sl["parts"] if p["AE"] == 3)
            sl["L"] = 1 if (sl["B"] != "" and sl["H"] > 0) else 0
            sl["Q"] = sum(1 for p in sl["parts"] if isnum(p["typed"]) and p["typed"] > 0)
        self.slots = slots
        self.bal_parts = parts
        self.n_active_bal = len(active)
        act = []
        for p in active[:N_BAL_LINES]:
            sl = slots[p["s"] - 1]
            act.append({"p": len(act) + 1, "AR": p["s"], "AS": num(sl["B"]) if isnum(sl["B"]) else 0,
                        "AT": sl["P"], "AU": p["U"], "AV": p["W"], "AW": p["X"], "AX": p["AE"],
                        "AY": p["AC"], "AZ": p["AI"], "BA": p["AB"], "part": p})
        self.active = act

    # ------------------------------------------------------------------
    # Priority Calc: job lines and their processing rank
    def calc_lines(self) -> None:
        lines = []
        for w in range(1, N_LINES + 1):
            X = (w - 1) // 2 + 1
            Y = (w - 1) % 2
            e = self.pc[X - 1]
            Z = e["K"] if Y == 0 else e["L"]
            if Z <= 0:
                AA = BIG
            elif Y == 0:
                AA = 0 * 10000 + X
            elif e["AG"] == 1:
                AA = 5_000_000 + X * 1000
            else:
                AA = 10_000_000 + X * 1000
            lines.append({"w": w, "X": X, "Y": Y, "Z": Z, "AA": AA})
        for j in range(1, N_BAL_LINES + 1):
            a = self.active[j - 1] if j <= len(self.active) else None
            AS = a["AS"] if a else 0
            X = AS if AS != 0 else 1
            Z = num(a["BA"]) if a else 0
            if Z <= 0:
                AA = BIG
            elif a["AR"] <= 24:
                AA = j
            else:
                sl = self.slots[a["AR"] - 1]
                AA = (5_000_000 if sl["LP"] == 1 else 10_000_000) + num(sl["LO"]) * 40000 + 500 + j
            lines.append({"w": N_LINES + j, "X": X, "Y": 2, "Z": Z, "AA": AA})
        keys = sorted(l["AA"] for l in lines)
        import bisect
        first_by_rank = {}
        for l in lines:
            if l["Z"] <= 0:
                l["AB"] = ""
                continue
            l["AB"] = bisect.bisect_left(keys, l["AA"]) + 1
            first_by_rank.setdefault(l["AB"], l["w"])
        self.lines = lines
        self.lines_in_use = sum(1 for l in lines if l["AB"] != "")
        self.rank_line = [first_by_rank.get(k) for k in range(1, self.line_capacity + 1)]

    # ------------------------------------------------------------------
    # Job Schedule
    def calc_job_schedule(self) -> None:
        rows = []
        for i, w in enumerate(self.rank_line):
            r = {"i": i + 1, "N": w}
            if w is None:
                r.update(B="", C="", D=0, E=0, F=0, G=0, H=0, I=0, L=self.trolley, M="", P="", O="")
                rows.append(r)
                continue
            ln = self.lines[w - 1]
            O = ln["X"]
            r["O"] = O
            if w > N_LINES:
                a = self.active[w - N_LINES - 1]
                sl = self.slots[a["AR"] - 1]
                B = a["AT"]
                r["C"] = sl["D"] if B != "" else ""
                hp = [a["AY"] if a["AX"] == k else 0 for k in (1, 2, 3)]
                H8 = a["AY"] if a["AZ"] == 1 else 0
                L = 1
                M = sl["LO"]
                r["bal"] = a
            else:
                e = self.pc[O - 1]
                B = e["B"]
                r["C"] = e["D"] if B != "" else ""
                hp = list(self.hrs_l[key(B)]) if B != "" else [0, 0, 0]
                H8 = self.hrs_8[key(B)] if B != "" else 0
                L = e["Q"]
                M = max(e["E"], e["AK"]) if w % 2 == 1 else e["E"]
            r["B"] = B
            if B == "":
                hp, H8, L, M = [0, 0, 0], 0, self.trolley, ""
            r["D"] = ln["Z"] if B != "" else 0
            r["E"], r["F"], r["G"] = hp
            r["H"] = H8
            r["I"] = hp[0] + hp[1] + hp[2]
            r["L"] = L
            r["M"] = M
            r["P"] = "" if B == "" else (2 if w > N_LINES else (1 if w % 2 == 1 else 0))
            r["qty"] = [0] * DAYS
            rows.append(r)
        f1, f3 = self.f1, self.f3
        self.js_day = []
        for d in range(DAYS):
            c1, c2, c3 = self.cap[d][0], self.cap[d][1], self.cap[d][2]
            ctot = c1 + c2 + c3 + 1e-9
            R1 = R2 = R3 = U8 = 0.0
            used = defaultdict(float)   # same product already placed today (earlier rows)
            for r in rows:
                if r["N"] is None:
                    continue
                prev = sum(r["qty"][:d])
                remaining = r["D"] - prev
                if r["B"] == "" or r["I"] <= 0 or d < num(r["M"]) or r["M"] == "":
                    maxq = 0
                else:
                    cap_p = 255 if r["N"] > N_LINES else self.pc[r["O"] - 1]["AL"] - used[key(r["B"])]
                    maxq = max(0, min(cap_p, remaining))
                E_, F_, G_, H_, I_ = r["E"], r["F"], r["G"], r["H"], r["I"]
                fit = 0
                for step in (128, 64, 32, 16, 8, 4, 2, 1):
                    q = fit + step
                    if q > maxq:
                        continue
                    over2 = max(0.0, R2 + q * F_ - c2)
                    mv = min(over2, U8 + q * H_)
                    tot = (R1 + R2 + R3 + q * I_ + (f1 - 1) * mv
                           + (f3 - f1) * max(0.0, mv - max(0.0, (c1 - R1 - q * E_) / f1)))
                    if tot <= ctot:
                        fit = q
                if fit >= remaining:
                    qty = remaining
                else:
                    x = remaining - xroundup((remaining - fit) / r["L"]) * r["L"]
                    qty = x if x >= r["L"] else 0
                r["qty"][d] = qty
                R1 += qty * E_
                R2 += qty * F_
                R3 += qty * G_
                U8 += qty * H_
                if r["B"] != "":
                    used[key(r["B"])] += qty
            moved = min(max(0.0, R2 - c2), U8)
            to3 = max(0.0, moved - max(0.0, (c1 - R1) / f1))
            self.js_day.append({"L1": R1, "L2": R2, "L3": R3, "H8": U8, "moved": moved, "to3": to3, "to1": moved - to3})
        for r in rows:
            q = r.get("qty", [0] * DAYS)
            r["qty"] = q
            r["J"] = sum(q)
            r["K"] = (r["D"] - r["J"]) if r["B"] != "" else ""
        self.js = rows
        self.js_by_line = {r["N"]: r for r in rows if r["N"] is not None}

    # ------------------------------------------------------------------
    # Balance Calc (scheduled part: per-day profiles, moves to L1/L3, slot totals)
    def calc_balance_dynamic(self) -> None:
        f1, f3 = self.f1, self.f3
        for a in self.active:
            jr = self.js_by_line.get(N_LINES + a["p"])
            a["q"] = list(jr["qty"]) if jr else [0] * DAYS
            a["to1"] = [0] * DAYS
            a["to3"] = [0] * DAYS
            a["line"] = [[0, 0, 0] for _ in range(DAYS)]
        cnt = [[0, 0, 0] for _ in range(DAYS)]
        BN = [0.0] * DAYS
        for a in self.active:
            for d in range(DAYS):
                q = a["q"][d]
                AY, AZ = a["AY"], a["AZ"]
                to1 = to3 = 0
                if AZ != 0 and q != 0:
                    T16 = self.js_day[d]["to1"]
                    T14 = self.js_day[d]["moved"]
                    to1 = xround(q * max(0, min(BN[d] + q * AY, T16) - min(BN[d], T16)) / (q * AY), 0)
                    to3 = min(q - to1, xround(q * max(0, min(BN[d] + q * AY, T14) - max(BN[d], T16)) / (q * AY), 0))
                a["to1"][d], a["to3"][d] = to1, to3
                if (a["AX"] == 1) * q + to1 > 0:
                    cnt[d][0] += 1
                if (a["AX"] == 2) * (q - to1 - to3) > 0:
                    cnt[d][1] += 1
                if (a["AX"] == 3) * q + to3 > 0:
                    cnt[d][2] += 1
                a["line"][d] = list(cnt[d])
                BN[d] += q * AY * AZ
            a["BC"] = sum(a["q"])
            nz = [d for d in range(DAYS) if a["q"][d] > 0]
            a["BD"] = nz[0] if nz else ""
            a["BE"] = nz[-1] if nz else ""
        self.bal_line_max = [max([a["line"][d][l] for a in self.active] or [0]) for d in range(DAYS) for l in range(3)]
        by_slot = defaultdict(list)
        for a in self.active:
            by_slot[a["AR"]].append(a)
        GY = [0.0] * DAYS
        for sl in self.slots:
            acts = by_slot.get(sl["s"], [])
            sl["GT"] = [sum(a["q"][d] for a in acts) for d in range(DAYS)]
            sl["pre"] = [[sum(a["q"][d] * a["AY"] for a in acts if a["AX"] == k) for k in (1, 2, 3)] for d in range(DAYS)]
            sl["GX"] = [sum(a["q"][d] * a["AY"] for a in acts if a["AZ"] == 1) for d in range(DAYS)]
            sl["GY_prev"] = list(GY)
            GY = [GY[d] + sl["GX"][d] for d in range(DAYS)]
            sl["GY"] = list(GY)
            sl["M"] = sum(a["BC"] for a in acts)
            nz = [d for d in range(DAYS) if sl["GT"][d] > 0]
            sl["N"] = nz[0] if (sl["M"] != 0 and nz) else ""
            sl["LL"] = nz[-1] if (sl["M"] != 0 and nz) else ""
            sl["O"] = self._slot_status(sl)
        self.GY49 = GY

    def _slot_status(self, sl: dict) -> str:
        if sl["B"] == "":
            return ""
        if sl["G"] == 0:
            return "Not in laser master data"
        if sl["H"] == 0:
            return "No laser parts to cut" if sl["Q"] > 0 else "Waiting for quantities"
        if sl["s"] > 24 and sl["LN"] == 99:
            return "Select a Start Date - not planned yet"
        if num(sl["LN"]) > 19:
            return ("Balance date is after the 4 weeks - not scheduled" if sl["s"] <= 24
                    else "Start date is after the 4 weeks - not scheduled")
        if sl["M"] == 0:
            return "Not scheduled - no capacity in the 4 weeks"
        if sl["M"] < sl["H"]:
            return f"Partly scheduled - {_t(sl['M'])} of {_t(sl['H'])} profiles (from {self.labels[sl['N']]})"
        return f"Scheduled - {self.labels[sl['N']]}" + (f" to {self.labels[sl['LL']]}" if sl["LL"] > sl["N"] else "")

    # ------------------------------------------------------------------
    # Average Cutting Plan (rows 6-325) + Plan Calc
    def calc_plan(self) -> None:
        f1, f3 = self.f1, self.f3
        by_prod_entries = defaultdict(list)
        for e in self.pc:
            if e["B"] != "":
                by_prod_entries[key(e["B"])].append(e)
        js_qty = defaultdict(lambda: [0] * DAYS)
        for r in self.js:
            if r["B"] != "":
                k = key(r["B"])
                for d in range(DAYS):
                    js_qty[k][d] += r["qty"][d]
        rows = []
        prev_pc = list(self.GY49)
        for k, prod in enumerate(self.products):
            pk = key(prod)
            ents = by_prod_entries[pk]
            hl = self.hrs_l[pk]
            row = {"k": k + 1, "A": prod, "B": sum(e["C"] for e in ents)}
            rel = [e["G"] for e in ents]
            row["rel"] = rel[:3] + ([""] * (3 - len(rel[:3])))
            if len(rel) > 4:
                row["rel4"] = f"{rel[3].strftime('%d %b')} +{len(rel) - 4}"
            elif len(rel) == 4:
                row["rel4"] = rel[3]
            else:
                row["rel4"] = ""
            row["DI"], row["DJ"], row["DK"] = hl
            row["DL"] = sum(hl) / 3
            row["DM"] = self.hrs_8[pk]
            G = list(js_qty[pk])
            row["G"] = G
            H, I, J = [], [], []
            pcs = []
            for d in range(DAYS):
                T14 = self.js_day[d]["moved"]
                T16 = self.js_day[d]["to1"]
                cur = prev_pc[d] + G[d] * row["DM"]
                pcs.append(cur)
                m14 = min(cur, T14) - min(prev_pc[d], T14)
                m16 = min(cur, T16) - min(prev_pc[d], T16)
                H.append(G[d] * row["DI"] + f1 * m16)
                I.append(G[d] * row["DJ"] - m14)
                J.append(G[d] * row["DK"] + f3 * (m14 - m16))
            prev_pc = pcs
            row["PC"] = pcs
            row["H"], row["I"], row["J"] = H, I, J
            row["K"] = [(H[d] + I[d] + J[d]) / 3 for d in range(DAYS)]
            row["DG"] = sum(G)
            row["weeks"] = [sum(G[w * 5:(w + 1) * 5]) for w in range(4)]
            row["DN"] = row["B"] - row["DG"] if row["DL"] > 0 else ""
            row["DO"] = "No laser hours - check master data" if row["DL"] <= 0 else ("Not fully scheduled" if num(row["DN"]) > 0 else "OK")
            rows.append(row)
        self.plan = rows
        # balance / RG rows (277-300 and 302-325)
        brows = []
        for sl in self.slots:
            if sl["P"] == "":
                continue
            H, I, J = [], [], []
            for d in range(DAYS):
                T14 = self.js_day[d]["moved"]
                T16 = self.js_day[d]["to1"]
                gy, gp = sl["GY"][d], sl["GY_prev"][d]
                m14 = min(gy, T14) - min(gp, T14)
                m16 = min(gy, T16) - min(gp, T16)
                pre = sl["pre"][d]
                H.append(pre[0] + f1 * m16)
                I.append(pre[1] - m14)
                J.append(pre[2] + f3 * (m14 - m16))
            brows.append({"slot": sl["s"], "kind": "BAL" if sl["s"] <= 24 else "RG", "A": sl["P"], "B": sl["H"],
                          "released": sl["F"], "start": sl["LM"] if sl["s"] > 24 else "",
                          "G": sl["GT"], "H": H, "I": I, "J": J,
                          "K": [(H[d] + I[d] + J[d]) / 3 for d in range(DAYS)], "DO": sl["O"],
                          "weeks": [sum(sl["GT"][w * 5:(w + 1) * 5]) for w in range(4)], "DG": sum(sl["GT"])})
        self.plan_bal = brows

    # ------------------------------------------------------------------
    # Laser Detail
    def calc_laser_detail(self) -> None:
        ld = []
        first = 1
        for row in self.plan:
            pk = key(row["A"])
            C = len(self.m_laser_by_prod.get(pk, []))
            F = row["G"]
            G = [max(0, (row["H"][d] - F[d] * row["DI"]) / self.f1) if F[d] != 0 else 0 for d in range(DAYS)]
            H = [max(0, (row["J"][d] - F[d] * row["DK"]) / self.f3) if F[d] != 0 else 0 for d in range(DAYS)]
            ld.append({"B": row["A"], "C": C, "D": first, "F": F, "G": G, "H": H})
            first += C
        self.ld = ld
        self.total_laser_parts = sum(x["C"] for x in ld)

    # ------------------------------------------------------------------
    # Laser Parts
    def calc_laser_parts(self) -> None:
        parts = []
        n = min(self.total_laser_parts, MAX_LASER_PARTS)
        gm = self.gauge_moved
        pos = 0
        for k, ldr in enumerate(self.ld):
            if ldr["C"] == 0:
                continue
            pk = key(ldr["B"])
            mv_before = 0.0
            for t, mi in enumerate(self.m_laser_by_prod[pk]):
                if pos >= n:
                    break
                pos += 1
                m = self.master[mi]
                I = m["laser_no"]
                H = num(m.get("profiles"))
                J = num(m.get("hrs"))
                K = 1 if (I == 2 and _eq_num(m.get("gauge"), gm)) else 0
                L = mv_before if K == 1 else 0
                if K == 1:
                    mv_before += J
                p = {"a": pos, "B": k + 1, "C": ldr["B"], "D": t + 1, "E": mi, "F": m.get("part"),
                     "G": m.get("gauge"), "H": H, "I": I, "J": J, "K": K, "L": L,
                     "N": [0] * DAYS, "O": [0] * DAYS, "P": [0] * DAYS}
                for d in range(DAYS):
                    Fq = ldr["F"][d]
                    N = Fq * H
                    p["N"][d] = N
                    if K == 0 or N == 0 or J == 0:
                        continue
                    g, h = ldr["G"][d], ldr["H"][d]
                    O = xround(H * max(0, min(Fq * (L + J), g) - min(Fq * L, g)) / J, 0)
                    P = min(N - O, xround(H * max(0, min(Fq * (L + J), g + h) - max(Fq * L, g)) / J, 0))
                    p["O"][d], p["P"][d] = O, P
                parts.append(p)
        cnt = [[0, 0, 0] for _ in range(DAYS)]
        for p in parts:
            p["line"] = []
            for d in range(DAYS):
                N, O, P = p["N"][d], p["O"][d], p["P"][d]
                if (p["I"] == 1) * N + O > 0:
                    cnt[d][0] += 1
                if (p["I"] == 2) * (N - O - P) > 0:
                    cnt[d][1] += 1
                if (p["I"] == 3) * N + P > 0:
                    cnt[d][2] += 1
                p["line"].append(list(cnt[d]))
        self.lp = parts
        self.lp_line_max = [[cnt[d][l] for l in range(3)] for d in range(DAYS)]

    # ------------------------------------------------------------------
    # BCZB List -> Plant 40 Stock -> Stock Calc (pools)
    def calc_stock_lists(self) -> None:
        cont = {key(c["name"]): bool(c.get("received")) for c in self.s.get("containers", [])}
        bz = []
        p40 = []
        not_recv = 0
        for i, r in enumerate(self.st.get("bczb", [])):
            typ = r.get("C")
            bms = r.get("E")
            bms_s = "" if blank(bms) else str(bms)
            T = 1 if (key(typ) == "PROFILE" and bms_s.strip() != "" and "OBSOLETE" not in bms_s.upper()
                      and "NOT USED" not in bms_s.upper()) else 0
            recv = "" if blank(typ) else ("Yes" if cont.get(key(r.get("G"))) else "No")
            row = dict(r)
            H, M, F, P = num(r.get("H")), num(r.get("M")), num(r.get("F")), num(r.get("P"))
            try:
                row["N"] = r.get("H") / (r.get("M") / 12) / r.get("F") if (isnum(r.get("H")) and M and F) else None
            except Exception:
                row["N"] = None
            row["O"] = row["N"] / 12 if isnum(row["N"]) else None
            row["Q"] = P * H if isnum(r.get("P")) else None
            row["R"] = row["Q"] * 18.72 if isnum(row["Q"]) else None
            row["T"] = T
            row["V"] = recv
            row["W"] = "" if recv == "" else (f"In stock (container {_s(r.get('G'))} received)" if recv == "Yes"
                                              else f"NOT received yet - container {_s(r.get('G'))}")
            if recv == "No":
                not_recv += 1
                row["X"] = not_recv
            else:
                row["X"] = ""
            bz.append(row)
            if T == 1 and len(p40) < 250:
                A = bms_s
                E = _s(r.get("G"))
                Fv = r.get("H") if not blank(r.get("H")) else ""
                ov = self.st.get("p40_qty_override", {})
                if A in ov:   # Qty Shipped typed on the Plant 40 Stock page
                    Fv = ov[A] if not blank(ov[A]) else ""
                G = "Yes" if cont.get(key(E)) else f"No - container {E} not received"
                Hs = num(Fv) if G == "Yes" else 0
                Ln = A.strip()
                for ch in "&/(),":
                    Ln = Ln.replace(ch, "|")
                toks = [t.strip() for t in Ln.split("|")]
                keys5 = (toks + [""] * 5)[:5]
                p40.append({"A": A, "B": _s(r.get("B")), "C": _s(r.get("D")), "D": r.get("F") if not blank(r.get("F")) else "",
                            "E": E, "F": Fv, "G": G, "H": Hs, "L": Ln, "keys": keys5,
                            "R": 1 if "/" in A else 0,
                            "K": "Yes" if any(k != "" and key(k) in self.master_parts for k in keys5)
                            else "No - not on the cutting list (master part list)"})
        self.bczb_rows = bz
        self.p40 = p40
        sc = []
        for ri, r in enumerate(p40):
            for c in range(1, 6):
                D = r["keys"][c - 1]
                E = r["R"]
                F = "" if D == "" else (r["keys"][0] if E == 1 else D)
                G = 0 if D == "" else (0 if (E == 1 and c > 1) else num(r["H"]))
                Hp = 0 if D == "" else (0 if (E == 1 and c > 1) else num(r["F"]) - num(r["H"]))
                sc.append({"r": ri, "c": c, "D": D, "E": E, "F": F, "G": G, "H": Hp})
        self.sc = sc
        self.pool_of_part = {}
        self.pool_stock = defaultdict(float)
        self.pool_pending = defaultdict(float)
        for x in sc:
            if x["D"] != "":
                self.pool_of_part.setdefault(key(x["D"]), x["F"])
            if x["F"] != "":
                self.pool_stock[key(x["F"])] += x["G"]
                self.pool_pending[key(x["F"])] += x["H"]

    # ------------------------------------------------------------------
    # Schedule per Laser
    def calc_schedule_per_laser(self) -> None:
        spl_in = self.st.get("spl", {})
        rnd = self.calc_rnd()
        f1, f3 = self.f1, self.f3
        days = []
        taken_by_pool = defaultdict(float)
        prev_rows = None
        # first balance line / laser part reaching counter k on (day, laser): MATCH(k, counter, 0)
        first_bal = {}
        for a in self.active:
            for d in range(DAYS):
                for l in range(3):
                    first_bal.setdefault((d, l + 1, a["line"][d][l]), a)
        first_part = {}
        for p in self.lp:
            for d in range(DAYS):
                for l in range(3):
                    first_part.setdefault((d, l + 1, p["line"][d][l]), p)
        for d in range(DAYS):
            lasers = []
            for l in (1, 2, 3):
                rows = []
                # 1) pushed in from the day before
                if d > 0:
                    for pr in prev_rows[l - 1]:
                        if pr["push_qty"] > 0 and sum(1 for r in rows if r["sec"] == "push") < 12:
                            rows.append(self._spl_row("push", pr["A"], pr["B"], pr["C"], pr["push_qty"], pr["AD"], ""))
                # 2) balance / RG parts
                for k in range(1, 31):
                    a = first_bal.get((d, l, k))
                    if a is None:
                        continue
                    q = a["q"][d]
                    if l == 1:
                        D = (q if a["AX"] == 1 else 0) + a["to1"][d]
                        AD = a["AY"] * (f1 if a["AZ"] == 1 else 1)
                    elif l == 2:
                        D = (q - a["to1"][d] - a["to3"][d]) if a["AX"] == 2 else 0
                        AD = a["AY"]
                    else:
                        D = (q if a["AX"] == 3 else 0) + a["to3"][d]
                        AD = a["AY"] * (f3 if a["AZ"] == 1 else 1)
                    sl = self.slots[a["AR"] - 1]
                    if a["AR"] <= 24:
                        lab = f"BAL {a['AU']}"
                    elif sl["D"] == "":
                        lab = f"RG #{a['AR'] - 24}"
                    else:
                        lab = f"RG {sl['D']}"
                    rows.append(self._spl_row("bal", lab, a["AV"], a["AW"], D, AD,
                                              self.pool_of_part.get(key(_s(a["AV"])), "")))
                # 3) laser parts of the plan
                for k in range(1, 77):
                    p = first_part.get((d, l, k))
                    if p is None:
                        continue
                    N, O, P = p["N"][d], p["O"][d], p["P"][d]
                    base = p["J"] / p["H"] if p["H"] else 0
                    if l == 1:
                        D = (N if p["I"] == 1 else 0) + O
                        AD = base * (f1 if p["K"] == 1 else 1)
                    elif l == 2:
                        D = (N - O - P) if p["I"] == 2 else 0
                        AD = base
                    else:
                        D = (N if p["I"] == 3 else 0) + P
                        AD = base * (f3 if p["K"] == 1 else 1)
                    rows.append(self._spl_row("part", p["C"], p["F"], p["G"], D, AD,
                                              self.pool_of_part.get(key(_s(p["F"])), "")))
                # 4) R&D programs
                for k in range(1, 5):
                    rr = rnd["by_key"].get((d, l, k))
                    if rr is None:
                        continue
                    row = self._spl_row("rnd", "R&D", rr["program"], rr["gauge"], "", 0, "")
                    row["E"] = f"R&D program - {_fixed1(num(rr['duration']))} h reserved on this laser"
                    rows.append(row)
                # typed inputs + per-line results (stock pool is used in order day -> laser -> line)
                occ = defaultdict(int)
                for r in rows:
                    k0 = (d, l, r["sec"], _s(r["A"]), _s(r["B"]))
                    r["key"] = "|".join(map(str, k0 + (occ[k0],)))
                    occ[k0] += 1
                    inp = spl_in.get(r["key"], {})
                    r["G"], r["Hs"], r["I"] = inp.get("taken"), inp.get("sic"), inp.get("comment")
                    D = r["D"]
                    pool = r["pool"]
                    if pool != "":
                        pk = key(pool)
                        r["AI"] = self.pool_stock.get(pk, 0)
                        r["AK"] = self.pool_pending.get(pk, 0)
                        if isnum(r["G"]) and num(D) > 0:
                            r["F"] = max(0, min(r["G"], max(0, D - num(r["Hs"])), max(0, r["AI"] - taken_by_pool[pk])))
                        taken_by_pool[pk] += r["F"]
                    Dn = num(D)
                    if blank(D) or Dn == 0:
                        r["push_qty"] = 0
                        r["done"] = 0
                        r["cut"] = 0
                    elif isnum(r["Hs"]):
                        r["push_qty"] = max(0, Dn - r["F"] - r["Hs"])
                        r["done"] = min(Dn, r["Hs"] + r["F"])
                        r["cut"] = min(r["Hs"], max(0, Dn - r["F"]))
                    else:
                        r["push_qty"] = 0
                        r["done"] = Dn if r["F"] >= Dn else 0
                        r["cut"] = 0
                lasers.append(rows)
            days.append(lasers)
            prev_rows = lasers
        # stock comments need the total taken per pool (all days)
        for lasers in days:
            for rows in lasers:
                for r in rows:
                    if r["sec"] == "push" or r["sec"] == "rnd":
                        continue
                    r["AO"] = taken_by_pool.get(key(r["pool"]), 0) if r["pool"] != "" else 0
                    r["E"] = self._stock_comment(r)
        self.spl = days
        self.taken_by_pool = taken_by_pool
        for x in self.sc:
            x["I"] = taken_by_pool.get(key(x["F"]), 0) if x["F"] != "" else 0
        # Plant 40 Stock: taken / left
        seen_h = defaultdict(float)
        for ri, r in enumerate(self.p40):
            mx = max(self.sc[ri * 5 + c]["I"] for c in range(5))
            r["I"] = min(r["H"], max(0, mx - seen_h[r["L"]]))
            r["J"] = r["H"] - r["I"]
            seen_h[r["L"]] += r["H"]

    def _spl_row(self, sec, A, B, C, D, AD, pool) -> dict:
        return {"sec": sec, "A": A, "B": B, "C": C, "D": D, "AD": AD, "pool": pool,
                "F": 0, "AI": 0, "AK": 0, "AO": 0, "E": ""}

    @staticmethod
    def _stock_comment(r: dict) -> str:
        G = r["G"]
        if r["pool"] == "":
            return "Taken Qty ignored - part not in Plant 40 stock" if (isnum(G) and G > 0) else ""
        if r["AI"] > 0:
            s = f"In stock: {_t(r['AI'])}"
            if r["AO"] > 0:
                s += f"  ({_t(max(0, r['AI'] - r['AO']))} free)"
            if isnum(G):
                s += f" - taking {_t(r['F'])}" + (f" (asked {_t(G)})" if G > r["F"] else "")
            return s
        if r["AK"] > 0:
            return f"Not received yet: {_t(r['AK'])}" + (" - Taken Qty ignored" if (isnum(G) and G > 0) else "")
        return ""

    # ------------------------------------------------------------------
    # R&D tab
    def calc_rnd(self) -> dict:
        out = []
        counts = defaultdict(int)
        by_key = {}
        lo, hi = min(self.dates), max(self.dates)
        for r in sorted(self.st.get("rnd", []), key=lambda x: x.get("row", 0)):
            prog, gauge, dur, laser, start = (r.get(k) for k in ("program", "gauge", "duration", "laser", "start"))
            sd = to_date(start)
            I = ""
            if not blank(prog) and sd is not None:
                w = workday(sd - dt.timedelta(days=1), 1)
                if lo <= w <= hi:
                    I = self.idx(sd)
            J = ""
            if not blank(laser):
                try:
                    v = int(str(laser).strip()[-1])
                    J = v if 1 <= v <= 3 else ""
                except ValueError:
                    J = ""
            M = 1 if (not blank(prog) and isnum(I) and isnum(J) and num(dur) > 0) else 0
            K = ""
            if M == 1:
                counts[(I, J)] += 1
                K = counts[(I, J)]
                by_key[(I, J, K)] = r
            if all(blank(v) for v in (prog, gauge, dur, laser, start)):
                status = ""
            elif blank(prog):
                status = "Program Number missing"
            elif num(dur) <= 0:
                status = "Duration missing"
            elif blank(laser):
                status = "Laser missing"
            elif not isnum(J):
                status = "Laser must be Laser 1, Laser 2 or Laser 3"
            elif sd is None:
                status = "Select a Start Date - not scheduled yet"
            elif not isnum(I):
                status = "Start date is outside the 4 weeks - not scheduled"
            else:
                status = (f"Scheduled - {self.labels[I]} on Laser {J} ({_fixed1(num(dur))} h)"
                          + ("  - only the first 4 programs of this laser and day are listed on the Schedule per Laser (the hours still count)" if K > 4 else ""))
            out.append({**r, "status": status, "day": I, "laser_no": J, "rank": K, "valid": M})
        hrs = [[sum(num(x.get("duration")) for x in out if x["valid"] == 1 and x["day"] == d and x["laser_no"] == l)
                for l in (1, 2, 3)] for d in range(DAYS)]
        waiting = sum(1 for x in out if not blank(x.get("program")) and to_date(x.get("start")) is None)
        self.rnd = {"rows": out, "by_key": by_key, "hrs": hrs,
                    "summary": f"Scheduled: {sum(x['valid'] for x in out)} program(s), "
                               f"{_fixed1(sum(num(x.get('duration')) for x in out if x['valid'] == 1))} laser-hours reserved   |   Waiting for a Start Date: {waiting}"}
        return self.rnd

    # ------------------------------------------------------------------
    # Laser Detail CA..CK: pushed hours, stock savings, R&D hours per day/laser
    def calc_day_hours(self) -> None:
        self.pushed_h = [[0.0] * 3 for _ in range(DAYS)]
        self.stock_h = [[0.0] * 3 for _ in range(DAYS)]
        for d in range(DAYS):
            for l in range(3):
                rows = self.spl[d][l]
                self.stock_h[d][l] = sum(num(r["F"]) * num(r["AD"]) for r in rows)
                if d > 0:
                    self.pushed_h[d][l] = sum(num(r["push_qty"]) * num(r["AD"]) for r in self.spl[d - 1][l])
        self.rnd_h = self.rnd["hrs"]

    # ------------------------------------------------------------------
    # Average Cutting Plan row 4 (load %) + headline
    def calc_plan_totals(self) -> None:
        tot = []
        for d in range(DAYS):
            G4 = sum(r["G"][d] for r in self.plan)
            sums = [sum(r[c][d] for r in self.plan) + sum(r[c][d] for r in self.plan_bal) for c in ("H", "I", "J")]
            sK = sum(r["K"][d] for r in self.plan) + sum(r["K"][d] for r in self.plan_bal)
            loads = []
            for l in range(3):
                cap = self.cap[d][l]
                v = max(0, sums[l] + self.pushed_h[d][l] + self.rnd_h[d][l] - self.stock_h[d][l])
                loads.append(v / cap if cap else 0)
            capk = self.cap[d][3]
            extra = (sum(self.pushed_h[d]) + sum(self.rnd_h[d]) - sum(self.stock_h[d])) / 3
            loads.append(max(0, sK + extra) / capk if capk else 0)
            tot.append({"qty": G4, "load": loads, "hours": [sums[l] for l in range(3)]})
        self.day_totals = tot
        self.week_totals = [sum(r["weeks"][w] for r in self.plan) for w in range(4)]
        self.unscheduled = sum(num(r["DN"]) for r in self.plan)
        peak_ave = max(t["load"][3] for t in tot)
        peak_l2 = max(t["load"][1] for t in tot)
        if not self.plan:
            msg = "Enter released jobs on the Jobs Released tab."
        else:
            msg = (f"Peak Laser Ave.: {xround(peak_ave * 100, 1):.1f}%"
                   + (" - OVER 100% (pushed pieces)" if xround(peak_ave, 6) > 1 else " - OK (max 100%)")
                   + f"  |  Peak Laser 2: {xround(peak_l2 * 100, 0):.0f}%")
            if self.total_laser_parts > MAX_LASER_PARTS:
                msg += f"  |  WARNING: this plan has {self.total_laser_parts} laser parts but the Laser Parts table holds {MAX_LASER_PARTS} - parts are missing on Schedule per Laser"
            if self.lines_in_use > self.line_capacity:
                msg += "  |  WARNING: more job lines than the scheduler holds - the lowest priority lines are not scheduled"
            ph = sum(sum(x) for x in self.pushed_h)
            sh = sum(sum(x) for x in self.stock_h)
            rh = sum(sum(x) for x in self.rnd_h)
            if ph > 0:
                msg += f"  |  Pushed pieces add {_fixed1(ph)} laser-h to the days they were pushed to (plan unchanged)"
            if sh > 0:
                msg += f"  |  Stock saves {_fixed1(sh)} laser-h (shown in the %)"
            if rh > 0:
                msg += f"  |  R&D reserves {_fixed1(rh)} laser-h (shown in the %)"
            if self.unscheduled > 0:
                msg += f"  |  {xround(self.unscheduled, 0):,.0f} qty not scheduled (over the 4 weeks)"
            nl = sum(1 for r in self.plan if str(r["DO"]).startswith("No laser"))
            if nl > 0:
                msg += f"  |  {nl} product(s) with no laser hours"
        self.headline = msg

    # ------------------------------------------------------------------
    # Laser Parts EE..EX + Completion Calc
    def calc_completion(self) -> None:
        done_pp = defaultdict(lambda: [0.0] * DAYS)    # (product, part) -> done that day
        done_p = defaultdict(lambda: [0.0] * DAYS)     # product -> done that day
        done_lab = defaultdict(float)                  # (label, part) -> done in total
        for d in range(DAYS):
            for l in range(3):
                for r in self.spl[d][l]:
                    v = num(r["done"])
                    if v == 0:
                        continue
                    done_pp[(key(r["A"]), key(r["B"]))][d] += v
                    done_p[key(r["A"])][d] += v
                    done_lab[(key(r["A"]), key(r["B"]))] += v
        self.done_lab = done_lab
        for p in self.lp:
            cum = 0.0
            p["EE"] = []
            for d in range(DAYS):
                if p["H"] <= 0:
                    p["EE"].append(BIG)
                    continue
                cum += done_pp[(key(p["C"]), key(p["F"]))][d] / p["H"]
                p["EE"].append(cum)
        lp_by_prod = defaultdict(list)
        for p in self.lp:
            lp_by_prod[key(p["C"])].append(p)
        comp = []
        for k, row in enumerate(self.plan):
            pk = key(row["A"])
            B = self.prof_laser[pk]
            C = num(row["B"])
            cum = []
            c = 0.0
            for d in range(DAYS):
                c += done_p[pk][d]
                cum.append(c)
            W = cum[-1]
            X = W / B if B > 0 else 0
            ldr = self.ld[k]
            towbars = []
            parts = lp_by_prod.get(pk, [])
            for d in range(DAYS):
                if ldr["C"] == 0 or ldr["D"] > MAX_LASER_PARTS or not parts:
                    towbars.append(0)
                    continue
                m = min(p["EE"][d] for p in parts)
                towbars.append(0 if m >= 100_000_000 else min(C, int(m + 1e-9)))
            needed = [sum(p["N"][d] for p in parts) for d in range(DAYS)]
            share, codes = [], []
            before = 0.0
            for d in range(DAYS):
                if needed[d] <= 0:
                    share.append("")
                else:
                    share.append(min(needed[d], max(0, W - before)) / needed[d])
                before += needed[d]
                codes.append(colour_code(share[-1]))
            comp.append({"A": row["A"], "B": B, "C": C, "cum": cum, "W": W, "X": X, "towbars": towbars,
                         "needed": needed, "share": share, "codes": codes})
        self.comp = comp
        self.comp_by_prod = {key(c["A"]): (i, c) for i, c in enumerate(comp)}

    def calc_balance_done(self) -> None:
        due_only = bool(self.s.get("colour_due_only"))
        for sl in self.slots:
            for p in sl["parts"]:
                if p["U"] == "" or num(p["AB"]) <= 0:
                    p["LR"] = 0
                    p["LS"] = ""
                    continue
                if sl["s"] <= 24:
                    lab = f"BAL {p['U']}"
                elif sl["D"] == "":
                    lab = f"RG #{sl['s'] - 24}"
                else:
                    lab = f"RG {sl['D']}"
                p["LR"] = min(p["AB"], self.done_lab.get((key(lab), key(_s(p["W"]))), 0))
                p["LS"] = p["LR"] / p["AB"]
            sl["LT"] = sum(p["LR"] for p in sl["parts"])
            sl["LU"] = min(1, sl["LT"] / sl["H"]) if num(sl["H"]) > 0 else ""
            shares = []
            before = 0.0
            for d in range(DAYS):
                g = sl["GT"][d]
                if num(sl["H"]) <= 0 or g <= 0:
                    shares.append("")
                else:
                    shares.append(min(g, max(0, sl["LT"] - before)) / g)
                before += g
            sl["day_share"] = shares
            sl["day_codes"] = [colour_code(x) for x in shares]
            if num(sl["H"]) <= 0 or num(sl["M"]) == 0:
                MP = 0
            elif not due_only:
                MP = 1
            elif isnum(sl["N"]):
                MP = 1 if self.dates[sl["N"]] <= self.today else 0
            else:
                MP = 0
            sl["MP"] = MP
            for p in sl["parts"]:
                p["NK"] = colour_code(p["LS"], due_red=(MP == 1))
            sl["NL"] = colour_code(sl["LU"], due_red=(MP == 1))


# ----------------------------------------------------------------------
def _laser_no(x: Any) -> int:
    if blank(x):
        return 0
    s = str(x).strip()
    try:
        return int(s[-1])
    except ValueError:
        return 0


def _eq_num(a: Any, b: Any) -> bool:
    if isnum(a) and isnum(b):
        return float(a) == float(b)
    return key(a) == key(b) and key(a) != ""


def _s(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def _t(x: Any) -> str:
    """Number joined into text the way Excel's & operator prints it."""
    if isinstance(x, float):
        if x.is_integer():
            return str(int(x))
        return f"{x:.15g}"
    return str(x)


def _fixed1(x: float) -> str:
    return f"{xround(x, 1):,.1f}"
