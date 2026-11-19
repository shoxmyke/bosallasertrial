import { Fragment, useMemo, useState } from "react";
import { patchDict, usePage } from "../api";
import { Cell } from "../components/Cell";
import { Loading, PageTitle } from "../components/Layout";
import { dateShort, doneClass, gen, hrs, isNum, loadClass, pct } from "../format";

type ORow = {
  d: number;
  week: string;
  day: string;
  capacity: number[];
  products: number[];
  qty: number;
  scheduled: number;
  cut: number;
  adherence: number | "";
  worked: number;
  towbars: number;
  hours_saved: number;
  hours_pushed: number;
};

function adhClass(x: number | "") {
  if (!isNum(x)) return "";
  return x >= 0.75 ? "adh-good" : x >= 0.5 ? "adh-mid" : "adh-bad";
}

export function Output() {
  const { data, error } = usePage<{ rows: ORow[]; total: Omit<ORow, "d" | "week" | "day" | "capacity" | "products" | "worked"> }>(
    "output",
  );
  if (!data) return <Loading error={error} />;
  return (
    <>
      <PageTitle title="Output - month overview">
        Read only: fills itself from the plan and the Schedule per Laser. <b>Adherence to schedule</b> = profiles cut that
        day / profiles scheduled to cut that day (everything listed for the day, including pushed lines, less stock taken).
        It shows once SIC Qty has been typed for that day.
        <span className="tag adh-good">75%+</span>
        <span className="tag adh-mid">50-75%</span>
        <span className="tag adh-bad">below 50%</span>
      </PageTitle>
      <div className="table-wrap">
        <table className="grid report">
          <thead>
            <tr>
              <th rowSpan={2}>Week</th>
              <th rowSpan={2}>Day</th>
              <th colSpan={2}>Laser 1</th>
              <th colSpan={2}>Laser 2</th>
              <th colSpan={2}>Laser 3</th>
              <th>Qty</th>
              <th colSpan={5}>SIC (made that day)</th>
              <th>Stock</th>
              <th>Pushed</th>
            </tr>
            <tr>
              <th>Capacity</th>
              <th>Products</th>
              <th>Capacity</th>
              <th>Products</th>
              <th>Capacity</th>
              <th>Products</th>
              <th>Towbars</th>
              <th>Profiles scheduled</th>
              <th>Profiles cut</th>
              <th>Adherence</th>
              <th>Products</th>
              <th>Complete towbars</th>
              <th>Laser hours saved</th>
              <th>Laser hours pushed in</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.d} className={r.d % 5 === 0 ? "week-start" : ""}>
                <td className="c b">{r.week}</td>
                <td>{r.day}</td>
                {[0, 1, 2].map((l) => (
                  <Fragment key={l}>
                    <td className={`num ${loadClass(r.capacity[l])}`}>{pct(r.capacity[l])}</td>
                    <td className="num">{r.products[l]}</td>
                  </Fragment>
                ))}
                <td className="num">{gen(r.qty)}</td>
                <td className="num">{gen(r.scheduled)}</td>
                <td className="num">{gen(r.cut)}</td>
                <td className={`num ${adhClass(r.adherence)}`}>{pct(r.adherence, 1)}</td>
                <td className="num">{r.worked}</td>
                <td className="num">{gen(r.towbars)}</td>
                <td className="num">{hrs(r.hours_saved, 1)}</td>
                <td className="num">{hrs(r.hours_pushed, 1)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2}>Month total</td>
              <td colSpan={6} />
              <td className="num">{gen(data.total.qty)}</td>
              <td className="num">{gen(data.total.scheduled)}</td>
              <td className="num">{gen(data.total.cut)}</td>
              <td className={`num ${adhClass(data.total.adherence)}`}>{pct(data.total.adherence, 1)}</td>
              <td />
              <td className="num">{gen(data.total.towbars)}</td>
              <td className="num">{hrs(data.total.hours_saved, 1)}</td>
              <td className="num">{hrs(data.total.hours_pushed, 1)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="muted small">
        Profiles cut = pieces cut (SIC Qty typed, stock not counted). Products = different products worked on. Complete
        towbars = towbars whose laser parts are ALL done (SIC + stock taken).
      </p>
    </>
  );
}

type JRow = {
  n: number;
  released: string;
  product: string;
  qty: number;
  job: number | string;
  completed: string;
  lead_days: number;
  pct: number | "n/a";
  status: string;
  colour: number | "";
  done_qty: number;
};

export function JobsCompleted() {
  const { data, error } = usePage<{
    report_date: string;
    report_date_typed: string | null;
    lead_green: number;
    lead_red: number;
    rows: JRow[];
  }>("jobs-completed");
  const [q, setQ] = useState("");
  const [onlyOpen, setOnlyOpen] = useState(false);
  const rows = useMemo(
    () =>
      (data?.rows || []).filter(
        (r) =>
          (!q || `${r.product} ${r.job}`.toLowerCase().includes(q.toLowerCase())) &&
          (!onlyOpen || !r.completed),
      ),
    [data, q, onlyOpen],
  );
  if (!data) return <Loading error={error} />;
  return (
    <>
      <PageTitle title="Jobs Completed (first in - first out)">
        Every released job in release order. A job is completed once all its laser parts are done (SIC + stock).
        Lead time: <span className="tag adh-good">under {data.lead_green} days</span>
        <span className="tag adh-mid">
          {data.lead_green} to {data.lead_red} days
        </span>
        <span className="tag adh-bad">over {data.lead_red} days</span>
      </PageTitle>
      <div className="toolbar">
        <label className="field">
          Report date
          <Cell
            kind="date"
            value={data.report_date_typed || data.report_date}
            onSave={(v) => patchDict("jobs_completed", { report_date: v })}
          />
        </label>
        {data.report_date_typed && (
          <button className="btn small" onClick={() => patchDict("jobs_completed", { report_date: null })}>
            Back to today
          </button>
        )}
        <input className="search" placeholder="Search product or job…" value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="check">
          <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} /> only not completed
        </label>
      </div>
      <div className="table-wrap">
        <table className="grid report">
          <thead>
            <tr>
              <th>#</th>
              <th>Date released</th>
              <th>Product Number</th>
              <th>Quantity</th>
              <th>Job Number</th>
              <th>Date completed</th>
              <th>Lead time (days)</th>
              <th>% Complete</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.n}>
                <td className="num muted">{r.n}</td>
                <td className={doneClass(r.colour)}>{dateShort(r.released)}</td>
                <td className={doneClass(r.colour)}>{r.product}</td>
                <td className={`num ${doneClass(r.colour)}`}>{gen(r.qty)}</td>
                <td className={doneClass(r.colour)}>{r.job}</td>
                <td className={doneClass(r.colour)}>{dateShort(r.completed)}</td>
                <td className="num">{r.lead_days}</td>
                <td className={`num ${doneClass(r.colour)}`}>
                  {isNum(r.pct) ? (
                    <div className="bar">
                      <span style={{ width: `${Math.min(100, r.pct * 100)}%` }} />
                      <em>{pct(r.pct)}</em>
                    </div>
                  ) : (
                    r.pct
                  )}
                </td>
                <td className={/OVERDUE|ALERT/.test(r.status) ? "bad" : /slow|overdue/.test(r.status) ? "warn-text" : ""}>
                  {r.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
