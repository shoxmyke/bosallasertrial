import { useState } from "react";
import { patchRow, usePage } from "../api";
import { Cell } from "../components/Cell";
import { Loading, PageTitle } from "../components/Layout";
import { dateShort, doneClass, gen, pct } from "../format";

// ------------------------------------------------------------------ Back Orders
type BO = {
  row: number;
  date: string | null;
  product: string | null;
  qty: number | null;
  start: string | null;
  priority_qty: number | "";
  priority: number | "";
  released_qty: number | "";
  brought_forward: number | "";
  planned_qty: number | "";
  status: string;
  start_used: string | null;
  colour: number | "";
};

export function BackOrders() {
  const { data, error } = usePage<{ rows: BO[]; count: number; released: number }>("back-orders");
  const [extra, setExtra] = useState(5);
  if (!data) return <Loading error={error} />;
  const byRow = new Map(data.rows.map((r) => [r.row, r]));
  const last = Math.max(-1, ...data.rows.map((r) => r.row));
  const n = Math.min(150, last + 1 + extra);
  const save = (row: number, f: string) => (v: string | number | null) => patchRow("back_orders", { row }, { [f]: v });
  return (
    <>
      <PageTitle title="Back Orders (priority list)">
        Back orders are highlighted <span className="tag bo">purple</span> on Jobs Released, the plan and the Schedule
        per Laser. To cut one first, mark its job <b>Push X</b> on Jobs Released. Colours show how much of the brought
        forward quantity is completed.
      </PageTitle>
      <div className="stats">
        <div className="stat">
          <div className="stat-v">{data.count}</div>
          <div className="stat-l">Back orders</div>
        </div>
        <div className="stat">
          <div className="stat-v">{data.released}</div>
          <div className="stat-l">Released</div>
        </div>
      </div>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>Date</th>
              <th>Product Number</th>
              <th>Qty needed</th>
              <th>Priority qty</th>
              <th>Priority #</th>
              <th>Qty released</th>
              <th>Brought forward</th>
              <th>Planned (4 weeks)</th>
              <th>Start priority on</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: n }, (_, row) => {
              const r = byRow.get(row);
              return (
                <tr key={row}>
                  <td>
                    <Cell kind="date" value={r?.date} onSave={save(row, "date")} />
                  </td>
                  <td>
                    <Cell value={r?.product} onSave={save(row, "product")} width={120} />
                  </td>
                  <td>
                    <Cell kind="number" value={r?.qty} onSave={save(row, "qty")} width={60} />
                  </td>
                  <td className="num">{r && r.priority_qty !== 999999 ? gen(r.priority_qty) : ""}</td>
                  <td className="num">{r?.priority}</td>
                  <td className="num">{gen(r?.released_qty)}</td>
                  <td className={`num ${doneClass(r?.colour)}`}>{gen(r?.brought_forward)}</td>
                  <td className={`num ${doneClass(r?.colour)}`}>{gen(r?.planned_qty)}</td>
                  <td className={r?.product && !r?.start ? "soft-need" : ""}>
                    <Cell kind="date" value={r?.start} onSave={save(row, "start")} />
                  </td>
                  <td className={r?.status?.startsWith("Highlighted") ? "ok small" : "bad small"}>{r?.status}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {n < 150 && (
        <button className="btn small" onClick={() => setExtra(extra + 10)}>
          + more rows
        </button>
      )}
    </>
  );
}

// ------------------------------------------------------------------ R&D
type RD = {
  row: number;
  program: string | null;
  gauge: number | null;
  duration: number | null;
  laser: string | null;
  start: string | null;
  status: string;
};

export function RnD() {
  const { data, error } = usePage<{ summary: string; rows: RD[] }>("rnd");
  const [extra, setExtra] = useState(5);
  if (!data) return <Loading error={error} />;
  const last = Math.max(-1, ...data.rows.filter((r) => r.program || r.duration || r.laser || r.start).map((r) => r.row));
  const rows = data.rows.slice(0, Math.min(60, last + 1 + extra));
  const save = (row: number, f: string) => (v: string | number | null) => patchRow("rnd", { row }, { [f]: v });
  return (
    <>
      <PageTitle title="R&D (parts needed by R&D)">
        Programs for R&amp;D reserve laser hours on the day and laser you pick. They show on the Schedule per Laser and
        count in the load %.
      </PageTitle>
      <div className="summary">{data.summary}</div>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>#</th>
              <th>Program Number</th>
              <th>Gauge (mm)</th>
              <th>Duration (hours)</th>
              <th>Laser</th>
              <th>Start Date</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.row}>
                <td className="num muted">{r.row + 1}</td>
                <td>
                  <Cell value={r.program} onSave={save(r.row, "program")} width={120} />
                </td>
                <td>
                  <Cell kind="number" value={r.gauge} onSave={save(r.row, "gauge")} width={60} />
                </td>
                <td>
                  <Cell kind="number" value={r.duration} onSave={save(r.row, "duration")} width={60} />
                </td>
                <td>
                  <select
                    className="cell"
                    value={r.laser || ""}
                    onChange={(e) => save(r.row, "laser")(e.target.value || null)}
                  >
                    <option value="" />
                    <option>Laser 1</option>
                    <option>Laser 2</option>
                    <option>Laser 3</option>
                  </select>
                </td>
                <td className={r.program && !r.start ? "need" : ""}>
                  <Cell kind="date" value={r.start} onSave={save(r.row, "start")} />
                </td>
                <td className={r.status.startsWith("Scheduled") ? "ok" : "bad"}>{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length < 60 && (
        <button className="btn small" onClick={() => setExtra(extra + 10)}>
          + more rows
        </button>
      )}
    </>
  );
}

// ------------------------------------------------------------------ Cleaning
type CL = {
  week: string;
  w: number;
  laser: number;
  date: string;
  light: string | null;
  heavy: string | null;
  kind: string;
  what: string;
  gap: number;
  start_time: string | null;
  end_time: string;
  hours: number;
  left: number;
  load: number;
  comment: string | null;
  check: string;
};

export function Cleaning() {
  const { data, error } = usePage<{ rows: CL[]; light_h: number; heavy_h: number }>("cleaning");
  if (!data) return <Loading error={error} />;
  const save = (r: CL, f: string) => (v: string | number | null) =>
    patchRow("cleaning", { week: r.w, laser: r.laser }, { [f]: v });
  return (
    <>
      <PageTitle title="Cleaning schedule (Fridays, per laser)">
        Cleaning is done on Fridays. Mark <b>Light</b> (change the slats only, {data.light_h} h) or <b>Heavy</b> (slats +
        clean inside the laser, {data.heavy_h} h). The time is taken off that laser's Friday hours and the plan moves work
        to the other lasers. Change the hours on the Data page.
      </PageTitle>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>Week</th>
              <th>Laser</th>
              <th>Date</th>
              <th>Light (X)</th>
              <th>Heavy (X)</th>
              <th>Cleaning</th>
              <th>What is done</th>
              <th>Time gap (h)</th>
              <th>Start time</th>
              <th>End time</th>
              <th>Friday hours</th>
              <th>Hours left</th>
              <th>Planned load</th>
              <th>Comments</th>
              <th>Check</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr
                key={`${r.w}-${r.laser}`}
                className={`${r.kind === "Light" ? "row-light" : r.kind === "Heavy" ? "row-heavy" : ""} ${r.laser === 1 ? "week-start" : ""}`}
              >
                <td className="b">Week {r.week}</td>
                <td>Laser {r.laser}</td>
                <td>{dateShort(r.date)}</td>
                <td className="c">
                  <Cell kind="x" value={r.light} onSave={save(r, "light")} />
                </td>
                <td className="c">
                  <Cell kind="x" value={r.heavy} onSave={save(r, "heavy")} />
                </td>
                <td>{r.kind}</td>
                <td>{r.what}</td>
                <td className="num">{gen(r.gap)}</td>
                <td>
                  <Cell kind="time" value={r.start_time} onSave={save(r, "start_time")} />
                </td>
                <td>{r.end_time}</td>
                <td className="num">{gen(r.hours)}</td>
                <td className="num">{gen(r.left)}</td>
                <td className={`num ${r.gap > 0 && r.load > 1.0001 ? "bad" : ""}`}>{pct(r.load)}</td>
                <td>
                  <Cell value={r.comment} onSave={save(r, "comment")} width={140} />
                </td>
                <td className="bad small">{r.check}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
