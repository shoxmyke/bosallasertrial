import { useState } from "react";
import { patchRow, usePage } from "../api";
import { Cell } from "../components/Cell";
import { Loading, PageTitle } from "../components/Layout";
import { dateLong, dateShort, doneClass, gen, hrs, pct } from "../format";

type Part = {
  t: number;
  part: string;
  gauge: number;
  laser: string;
  profiles: number;
  qty: number | null;
  total: number | "";
  hours: number | "";
  scheduled: number | "";
  first_day: string;
  note: string;
  done: number | "";
  pct: number | "";
  colour: number | "";
};
type Block = {
  slot: number;
  product: string;
  job: string | number;
  released: string;
  date_used: string;
  date_typed: string | null;
  label: string;
  profiles: number;
  hours: number;
  status: string;
  completed: number | "";
  colour: number | "";
  parts: Part[];
  typed_without_order: boolean;
  entry?: { day: number; row: number } | null;
  row?: number;
  input?: { job: string | number | null; product: string | null; released: string | null; push: string | null; start: string | null };
  check?: string;
};

function statusClass(s: string) {
  if (!s) return "";
  return s.startsWith("Scheduled") ? "ok" : s.startsWith("Partly") ? "warn-text" : "bad";
}

function PartsTable({ b, rg, onQty }: { b: Block; rg: boolean; onQty: (t: number, v: string | number | null) => Promise<void> }) {
  return (
    <div className="table-wrap">
      <table className="grid">
        <thead>
          <tr>
            <th>Part Number</th>
            <th>Gauge</th>
            <th>Laser</th>
            <th>Profiles / product</th>
            <th>{rg ? "Qty to cut (pieces)" : "Qty needed"}</th>
            {!rg && <th>Total profiles</th>}
            <th>Hours</th>
            {rg && <th>Scheduled</th>}
            {rg && <th>First day</th>}
            <th>Note</th>
            <th>Done</th>
            <th>% done</th>
          </tr>
        </thead>
        <tbody>
          {b.parts.map((p) => (
            <tr key={p.t}>
              <td className={doneClass(p.colour)}>{p.part}</td>
              <td className={`num ${doneClass(p.colour)}`}>{gen(p.gauge)}</td>
              <td className={doneClass(p.colour)}>{p.laser}</td>
              <td className={`num ${doneClass(p.colour)}`}>{gen(p.profiles)}</td>
              <td className="typed-col">
                <Cell kind="number" value={p.qty} onSave={(v) => onQty(p.t, v)} width={60} />
              </td>
              {!rg && <td className="num">{gen(p.total)}</td>}
              <td className="num">{p.hours ? hrs(p.hours as number) : ""}</td>
              {rg && <td className="num">{gen(p.scheduled)}</td>}
              {rg && <td>{p.first_day}</td>}
              <td className={`small ${statusClass(p.note)}`}>{p.note}</td>
              <td className="num">{gen(p.done)}</td>
              <td className="num">{pct(p.pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------ Profile Balancing
export function ProfileBalancing() {
  const { data, error } = usePage<{ blocks: Block[]; warnings: string[] }>("profile-balancing");
  const [open, setOpen] = useState<number | null>(null);
  if (!data) return <Loading error={error} />;
  const used = data.blocks.filter((b) => b.product);
  return (
    <>
      <PageTitle title="Profile Balancing (special orders to balance a trolley)">
        Every job marked <span className="tag bal">Balance X</span> on Jobs Released gets a block here. Type the quantity
        needed for each part that is missing; only those profiles are cut. Balance orders are cut first, from the
        balance date (empty = next working day).
      </PageTitle>
      {data.warnings.map((w) => (
        <div key={w} className="error-box">
          {w}
        </div>
      ))}
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>#</th>
              <th>Job Number</th>
              <th>Product</th>
              <th>Released</th>
              <th>Balance on</th>
              <th>Profiles to cut</th>
              <th>Laser hours</th>
              <th>Status</th>
              <th>Completed</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {used.map((b) => (
              <tr key={b.slot} className={open === b.slot ? "selected" : ""}>
                <td className="num muted">{b.slot}</td>
                <td>{b.job}</td>
                <td className="b">{b.product}</td>
                <td>{dateShort(b.released)}</td>
                <td>
                  {b.entry && (
                    <Cell
                      kind="date"
                      value={b.date_typed || ""}
                      placeholder={b.date_used}
                      title={`Used: ${dateLong(b.date_used)}`}
                      onSave={(v) => patchRow("jobs", b.entry!, { balance_date: v })}
                    />
                  )}
                </td>
                <td className="num">{gen(b.profiles)}</td>
                <td className="num">{hrs(b.hours, 1)}</td>
                <td className={statusClass(b.status)}>{b.status}</td>
                <td className={`num ${doneClass(b.colour)}`}>{pct(b.completed)}</td>
                <td>
                  <button className="btn small" onClick={() => setOpen(open === b.slot ? null : b.slot)}>
                    {open === b.slot ? "Close" : "Parts"}
                  </button>
                </td>
              </tr>
            ))}
            {!used.length && (
              <tr>
                <td colSpan={10} className="muted c">
                  No balance orders. Mark a job with Balance X on Jobs Released.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {used
        .filter((b) => b.slot === open)
        .map((b) => (
          <section key={b.slot} className="card block">
            <div className="card-head">
              <h2>
                BALANCE {b.slot} - {b.product} - Job {b.job}
              </h2>
              <span className="muted">
                released {dateLong(b.released)} - balance from {dateShort(b.date_used)}
              </span>
            </div>
            <div className="summary">
              Status: {b.status} | profiles to cut: {gen(b.profiles)} | laser hours: {hrs(b.hours, 1)}
            </div>
            <PartsTable b={b} rg={false} onQty={(t, v) => patchRow("jobs", b.entry!, { [`balance_qty.${t}`]: v })} />
          </section>
        ))}
    </>
  );
}

// ------------------------------------------------------------------ RG Released Jobs
export function RGReleasedJobs() {
  const { data, error } = usePage<{ blocks: Block[] }>("rg-released-jobs");
  const [open, setOpen] = useState<number | null>(null);
  if (!data) return <Loading error={error} />;
  const lastUsed = Math.max(-1, ...data.blocks.filter((b) => b.input && Object.values(b.input).some((x) => x)).map((b) => b.row!));
  const blocks = data.blocks.slice(0, Math.min(24, lastUsed + 4));
  const save = (row: number, f: string) => (v: string | number | null) => patchRow("rg_jobs", { row }, { [f]: v });
  return (
    <>
      <PageTitle title="RG Released Jobs (jobs planned per part number)">
        Use this page for RG jobs: type the product, then the quantity to cut per part. RG parts are planned from their
        Start Date in release order with the other jobs (Push X = first).
      </PageTitle>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>#</th>
              <th>Job Number</th>
              <th>Product</th>
              <th>Released</th>
              <th>Push</th>
              <th>Start Date</th>
              <th>Profiles to cut</th>
              <th>Laser hours</th>
              <th>Status</th>
              <th>Check</th>
              <th>Completed</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {blocks.map((b) => (
              <tr key={b.slot} className={open === b.slot ? "selected" : ""}>
                <td className="num muted">{b.row! + 1}</td>
                <td>
                  <Cell kind="number" value={b.input?.job} onSave={save(b.row!, "job")} width={70} />
                </td>
                <td>
                  <Cell value={b.input?.product} onSave={save(b.row!, "product")} width={110} />
                </td>
                <td>
                  <Cell kind="date" value={b.input?.released} onSave={save(b.row!, "released")} />
                </td>
                <td className="c">
                  <Cell kind="x" value={b.input?.push} onSave={save(b.row!, "push")} />
                </td>
                <td className={b.product && !b.input?.start ? "need" : ""}>
                  <Cell kind="date" value={b.input?.start} onSave={save(b.row!, "start")} />
                </td>
                <td className="num">{b.product ? gen(b.profiles) : ""}</td>
                <td className="num">{b.product ? hrs(b.hours, 1) : ""}</td>
                <td className={statusClass(b.status)}>{b.status}</td>
                <td className="check-msg">{b.check}</td>
                <td className={`num ${doneClass(b.colour)}`}>{pct(b.completed)}</td>
                <td>
                  {b.product && (
                    <button className="btn small" onClick={() => setOpen(open === b.slot ? null : b.slot)}>
                      {open === b.slot ? "Close" : "Parts"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {blocks
        .filter((b) => b.slot === open)
        .map((b) => (
          <section key={b.slot} className="card block">
            <div className="card-head">
              <h2>
                RG JOB {b.row! + 1} - {b.product}
                {b.job ? ` - Job ${b.job}` : ""}
              </h2>
              <span className="muted">{b.date_used ? `start ${dateShort(b.date_used)}` : "select a Start Date"}</span>
            </div>
            <div className="summary">
              Status: {b.status} | profiles to cut: {gen(b.profiles)} | laser hours: {hrs(b.hours, 1)}
            </div>
            <PartsTable b={b} rg onQty={(t, v) => patchRow("rg_jobs", { row: b.row! }, { [`qty.${t}`]: v })} />
          </section>
        ))}
    </>
  );
}
