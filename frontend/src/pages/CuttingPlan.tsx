import { Fragment, useState } from "react";
import type { Day } from "../api";
import { patchDict, usePage } from "../api";
import { Cell } from "../components/Cell";
import { Loading, PageTitle, Tabs } from "../components/Layout";
import { dateShort, doneClass, gen, hrs, loadClass, pct } from "../format";

type PRow = {
  k: number;
  product: string;
  plan_qty: number;
  released: (string | number)[];
  qty: number[];
  l1: number[];
  l2: number[];
  l3: number[];
  ave: number[];
  weeks: number[];
  total: number;
  hrs_unit: number[];
  hrs_8mm: number;
  unscheduled: number | "";
  status: string;
  colour: (number | "")[];
  back_order: boolean;
};
type BRow = {
  kind: "BAL" | "RG";
  label: string;
  profiles: number;
  released: string;
  start: string;
  qty: number[];
  l1: number[];
  l2: number[];
  l3: number[];
  ave: number[];
  weeks: number[];
  total: number;
  status: string;
  colour: (number | "")[];
};
type Data = {
  headline: string;
  shifts: number;
  oee: number;
  products_count: number;
  days: Day[];
  rows: PRow[];
  balance_rows: BRow[];
  totals: { qty: number; load: number[]; capacity: number[] }[];
  week_totals: number[];
  avg_per_day: number;
  unscheduled: number;
  header_notes?: Record<string, string>;
};

/** Column letter of a day's first column on the Management Report (G for Week A Mon). */
function dayCol(d: number) {
  return colLetters(7 + 5 * d + Math.floor(d / 5));
}
function colLetters(c: number) {
  let s = "";
  let n = c;
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}
function colIndex(letters: string) {
  return letters.split("").reduce((a, ch) => a * 26 + ch.charCodeAt(0) - 64, 0);
}

export default function CuttingPlan({ management = false }: { management?: boolean }) {
  const { data, error } = usePage<Data>(management ? "management-report" : "average-cutting-plan");
  const [week, setWeek] = useState<number>(-1);
  const [showHrs, setShowHrs] = useState(true);
  if (!data) return <Loading error={error} />;
  const days = data.days.filter((d) => week < 0 || Math.floor(d.d / 5) === week);
  const notes = data.header_notes || {};
  // notes typed above a day block on the Management Report (cells in row 1)
  const notesFor = (d: number) => {
    const c0 = colIndex(dayCol(d));
    return Object.entries(notes)
      .filter(([col]) => colIndex(col) >= c0 && colIndex(col) < c0 + 5)
      .map(([col, v]) => ({ col, v }));
  };
  const span = showHrs ? 5 : 1;
  return (
    <>
      <PageTitle title={management ? "Management Report" : "Average Cutting Plan"}>
        Daily / weekly laser cutting plan per product. Hours per laser include 8 mm work moved off Laser 2. Load %:
        <span className="tag load-low">&gt;0</span>
        <span className="tag load-mid">50%+</span>
        <span className="tag load-high">86%+</span>
        <span className="tag load-over">over 100%</span>. Qty colours show how much of the day is done:
        <span className="tag done-1">100%</span>
        <span className="tag done-2">50-99%</span>
        <span className="tag done-3">10-49%</span>.
      </PageTitle>
      <div className="toolbar">
        <Tabs
          value={week}
          onChange={setWeek}
          items={[{ value: -1, label: "All weeks" }, ...[0, 1, 2, 3].map((w) => ({ value: w, label: `Week ${"ABCD"[w]}` }))]}
        />
        <label className="check">
          <input type="checkbox" checked={showHrs} onChange={(e) => setShowHrs(e.target.checked)} /> show laser hours
        </label>
        <span className="chip">Shifts: {data.shifts}</span>
        <span className="chip">OEE: {pct(data.oee)}</span>
        <span className="chip">Products: {data.products_count}</span>
        <span className="chip">Unscheduled qty: {gen(data.unscheduled)}</span>
      </div>
      <div className="table-wrap plan-wrap">
        <table className="grid plan">
          <thead>
            {management && (
              <tr className="notes-row">
                <th className="sticky" colSpan={3}>
                  Notes
                </th>
                {days.map((d) => (
                  <th key={d.d} colSpan={span} className="day-start">
                    <NoteCells d={d.d} notes={notesFor(d.d)} />
                  </th>
                ))}
                <th colSpan={week < 0 ? 7 : 4} />
              </tr>
            )}
            <tr>
              <th className="sticky" rowSpan={3}>
                Product
              </th>
              <th rowSpan={3}>Plan qty</th>
              <th rowSpan={3}>Released</th>
              {days.map((d) => (
                <th key={d.d} colSpan={span} className={`day-start ${d.is_today ? "today" : ""}`}>
                  {d.label}
                  <div className="sub">{dateShort(d.date)}</div>
                </th>
              ))}
              {week < 0 && <th rowSpan={3}>A</th>}
              {week < 0 && <th rowSpan={3}>B</th>}
              {week < 0 && <th rowSpan={3}>C</th>}
              {week < 0 && <th rowSpan={3}>D</th>}
              {week >= 0 && <th rowSpan={3}>Week</th>}
              <th rowSpan={3}>Total</th>
              <th rowSpan={3}>Unsched.</th>
              <th rowSpan={3}>Status</th>
            </tr>
            <tr>
              {days.map((d) => (
                <Fragment key={d.d}>
                  <th className="day-start sub">{gen(data.totals[d.d].qty)}</th>
                  {showHrs &&
                    data.totals[d.d].load.map((l, i) => (
                      <th key={i} className={`sub ${loadClass(l)}`} title={`${hrs(data.totals[d.d].capacity[i], 1)} h available`}>
                        {pct(l)}
                      </th>
                    ))}
                </Fragment>
              ))}
            </tr>
            <tr>
              {days.map((d) => (
                <Fragment key={d.d}>
                  <th className="day-start sub">Qty</th>
                  {showHrs && (
                    <>
                      <th className="sub">L1</th>
                      <th className="sub">L2</th>
                      <th className="sub">L3</th>
                      <th className="sub">Ave</th>
                    </>
                  )}
                </Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.k}>
                <td className={`sticky prod ${r.back_order ? "bo" : ""}`}>{r.product}</td>
                <td className="num">{gen(r.plan_qty)}</td>
                <td className="small">
                  {r.released.filter((x) => x !== "" && x != null).map((x, i) => (
                    <span key={i} className="rel">
                      {typeof x === "string" && /^\d{4}-/.test(x) ? dateShort(x) : String(x)}
                    </span>
                  ))}
                </td>
                {days.map((d) => (
                  <Fragment key={d.d}>
                    <td className={`num day-start ${doneClass(r.colour[d.d])} ${r.qty[d.d] ? "" : "zero"}`}>
                      {r.qty[d.d] ? gen(r.qty[d.d]) : ""}
                    </td>
                    {showHrs && (
                      <>
                        <td className="num h">{hrsCell(r.l1[d.d])}</td>
                        <td className="num h">{hrsCell(r.l2[d.d])}</td>
                        <td className="num h">{hrsCell(r.l3[d.d])}</td>
                        <td className="num h ave">{hrsCell(r.ave[d.d])}</td>
                      </>
                    )}
                  </Fragment>
                ))}
                {week < 0 ? (
                  r.weeks.map((x, i) => (
                    <td key={i} className="num wk">
                      {x ? gen(x) : ""}
                    </td>
                  ))
                ) : (
                  <td className="num wk">{r.weeks[week] ? gen(r.weeks[week]) : ""}</td>
                )}
                <td className="num b">{gen(r.total)}</td>
                <td className={`num ${Number(r.unscheduled) > 0 ? "neg" : ""}`}>{gen(r.unscheduled)}</td>
                <td className={r.status === "OK" ? "ok small" : "bad small"}>{r.status}</td>
              </tr>
            ))}
            {data.balance_rows.length > 0 && (
              <tr className="section-row">
                <td className="sticky" colSpan={3}>
                  Balance orders &amp; RG jobs (profiles) - scheduled first
                </td>
                <td colSpan={days.length * span + (week < 0 ? 7 : 4)} />
              </tr>
            )}
            {data.balance_rows.map((b, i) => (
              <tr key={i} className={b.kind === "BAL" ? "row-bal" : "row-rg"}>
                <td className="sticky prod">{b.label}</td>
                <td className="num">{gen(b.profiles)}</td>
                <td className="small">
                  {b.released ? dateShort(b.released) : ""}
                  {b.start ? ` → ${dateShort(b.start)}` : ""}
                </td>
                {days.map((d) => (
                  <Fragment key={d.d}>
                    <td className={`num day-start ${doneClass(b.colour[d.d])}`}>{b.qty[d.d] ? gen(b.qty[d.d]) : ""}</td>
                    {showHrs && (
                      <>
                        <td className="num h">{hrsCell(b.l1[d.d])}</td>
                        <td className="num h">{hrsCell(b.l2[d.d])}</td>
                        <td className="num h">{hrsCell(b.l3[d.d])}</td>
                        <td className="num h ave">{hrsCell(b.ave[d.d])}</td>
                      </>
                    )}
                  </Fragment>
                ))}
                {week < 0 ? (
                  b.weeks.map((x, i2) => (
                    <td key={i2} className="num wk">
                      {x ? gen(x) : ""}
                    </td>
                  ))
                ) : (
                  <td className="num wk">{b.weeks[week] ? gen(b.weeks[week]) : ""}</td>
                )}
                <td className="num b">{gen(b.total)}</td>
                <td />
                <td className="small">{b.status}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className="sticky">Week totals</td>
              <td colSpan={2 + days.length * span} className="small muted">
                Average per day over 4 weeks: {gen(Math.round(data.avg_per_day * 10) / 10)}
              </td>
              {(week < 0 ? data.week_totals : [data.week_totals[week]]).map((x, i) => (
                <td key={i} className="num b">
                  {gen(x)}
                </td>
              ))}
              <td className="num b">{gen(data.week_totals.reduce((a, b) => a + b, 0))}</td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}

function hrsCell(x: number) {
  if (!x || Math.abs(x) < 1e-9) return "";
  return hrs(x, 2);
}

function NoteCells({ d, notes }: { d: number; notes: { col: string; v: string }[] }) {
  const first = dayCol(d);
  const c2 = colLetters(colIndex(first) + 2);
  const val = (c: string) => notes.find((n) => n.col === c)?.v ?? "";
  const save = (c: string) => (v: string | number | null) =>
    getNotes().then((all) => {
      const next = { ...all };
      if (v == null) delete next[c];
      else next[c] = String(v);
      return patchDict("mgmt_report", { header_notes: next });
    });
  return (
    <div className="notes">
      <Cell value={val(first)} onSave={save(first)} placeholder="L:" width={70} />
      <Cell value={val(c2)} onSave={save(c2)} placeholder="EX:" width={70} />
    </div>
  );
}

async function getNotes(): Promise<Record<string, string>> {
  const r = await fetch("/api/state/mgmt_report");
  const j = await r.json();
  return j.header_notes || {};
}
