import { useState } from "react";
import { patchDict, patchRow, usePage } from "../api";
import { Cell } from "../components/Cell";
import { Loading, PageTitle, Tabs } from "../components/Layout";
import { gen } from "../format";

type Row = {
  row: number;
  product: string | null;
  qty: number | null;
  job: number | string | null;
  balance: string | null;
  push: string | null;
  start: string | null;
  plan_order: number | "";
  check: string;
  back_order: boolean;
};
type DayT = { d: number; date: string; title: string; total_qty: number; rows: Row[] };
type Week = {
  week: string;
  monday: string;
  days: DayT[];
  stats: { products: number; qty: number; balance: number; pushed: number; waiting: number };
};
type Data = { weeks: Week[]; week_a_monday: string };

export default function JobsReleased() {
  const { data, error } = usePage<Data>("jobs-released");
  const [w, setW] = useState(0);
  const [showAll, setShowAll] = useState(false);
  if (!data) return <Loading error={error} />;
  const week = data.weeks[w];
  return (
    <>
      <PageTitle title="Jobs Released">
        Enter every job released under the day it was released: Product Number, Quantity and Job Number. Pick a{" "}
        <b>Start Date</b> to plan it. <span className="tag bal">Balance X</span> = special order where only some profiles
        are missing (fill in the parts on Profile Balancing). <span className="tag push">Push X</span> = plan this job
        first. A <span className="tag bo">purple</span> product is on the Back Orders list.
      </PageTitle>
      <div className="toolbar">
        <label className="field">
          Week A commencing (Monday)
          <Cell
            kind="date"
            value={data.week_a_monday}
            onSave={(v) => patchDict("settings", { week_a_monday: v })}
          />
        </label>
        <Tabs
          value={w}
          onChange={setW}
          items={data.weeks.map((wk, i) => ({ value: i, label: `Week ${wk.week}` }))}
        />
        <label className="check">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> show all 40 rows
        </label>
      </div>
      <div className="stats">
        <Stat label="Products released" value={week.stats.products} />
        <Stat label="Total qty released" value={week.stats.qty} />
        <Stat label="Balance orders" value={week.stats.balance} />
        <Stat label="Pushed jobs" value={week.stats.pushed} />
        <Stat label="Waiting for a Start Date" value={week.stats.waiting} warn={week.stats.waiting > 0} />
      </div>
      <div className="day-grid">
        {week.days.map((day) => (
          <DayCard key={day.d} day={day} showAll={showAll} />
        ))}
      </div>
    </>
  );
}

function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className={`stat ${warn ? "warn" : ""}`}>
      <div className="stat-v">{gen(value)}</div>
      <div className="stat-l">{label}</div>
    </div>
  );
}

function DayCard({ day, showAll }: { day: DayT; showAll: boolean }) {
  const lastFilled = Math.max(-1, ...day.rows.filter((r) => r.product || r.qty || r.job || r.start).map((r) => r.row));
  const rows = showAll ? day.rows : day.rows.slice(0, Math.min(40, lastFilled + 4));
  const save = (row: number, field: string) => (v: string | number | null) =>
    patchRow("jobs", { day: day.d, row }, { [field]: v });
  return (
    <section className="card">
      <div className="card-head">
        <h2>{day.title}</h2>
        <span className="muted">Qty: {gen(day.total_qty)}</span>
      </div>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>#</th>
              <th>Product Number</th>
              <th>Qty</th>
              <th>Job Number</th>
              <th title="Balance order">Bal</th>
              <th title="Push - plan first">Push</th>
              <th>Start Date</th>
              <th title="Plan order (auto)">Order</th>
              <th>Check</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const bal = (r.balance || "").toUpperCase().trim() === "X";
              const push = (r.push || "").toUpperCase().trim() === "X";
              const cls = bal ? "row-bal" : push ? "row-push" : "";
              return (
                <tr key={r.row} className={cls}>
                  <td className="muted num">{r.row + 1}</td>
                  <td className={r.back_order ? "bo" : ""}>
                    <Cell value={r.product} onSave={save(r.row, "product")} width={120} />
                  </td>
                  <td>
                    <Cell value={r.qty} kind="number" onSave={save(r.row, "qty")} width={56} />
                  </td>
                  <td>
                    <Cell value={r.job} kind="number" onSave={save(r.row, "job")} width={68} />
                  </td>
                  <td className="c">
                    <Cell value={r.balance} kind="x" onSave={save(r.row, "balance")} />
                  </td>
                  <td className="c">
                    <Cell value={r.push} kind="x" onSave={save(r.row, "push")} />
                  </td>
                  <td className={r.product && !r.start ? "need" : ""}>
                    <Cell value={r.start} kind="date" onSave={save(r.row, "start")} />
                  </td>
                  <td className="num muted">{r.plan_order}</td>
                  <td className="check-msg">{r.check}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
