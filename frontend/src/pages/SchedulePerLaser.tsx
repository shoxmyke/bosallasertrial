import { useEffect, useState } from "react";
import { patchDict, usePage } from "../api";
import { Cell } from "../components/Cell";
import { Loading, PageTitle } from "../components/Layout";
import { dateShort, gen, loadClass, pct } from "../format";

type Row = {
  key: string;
  sec: "push" | "bal" | "part" | "rnd";
  product: string;
  part: string;
  gauge: number | string;
  qty: number | string;
  stock_comment: string;
  stock_taken: number;
  taken: number | null;
  sic: number | null;
  comment: string | null;
  push_qty: number;
  done: number;
  complete: boolean;
  back_order: boolean;
};
type Laser = {
  laser: number;
  load: number;
  hours_text: string;
  products: number;
  output: number;
  stock_taken: number;
  gauges: { gauge: number; qty: number }[];
  stock_saves_h: number;
  warnings: string[];
  rows: Row[];
};
type DayT = { d: number; label: string; date: string; is_today: boolean; title: string; lasers: Laser[] };
type Data = { days: DayT[] };

const SEC_LABEL: Record<string, string> = {
  push: "Pushed in from the day before",
  bal: "Balance orders & RG jobs - cut these first",
  part: "Laser parts",
  rnd: "R&D programs",
};

export default function SchedulePerLaser() {
  const { data, error } = usePage<Data>("schedule-per-laser");
  const [day, setDay] = useState<number | null>(null);
  const [laser, setLaser] = useState<number>(0); // 0 = all three
  useEffect(() => {
    if (data && day === null) {
      const t = data.days.find((d) => d.is_today);
      setDay(t ? t.d : 0);
    }
  }, [data, day]);
  if (!data || day === null) return <Loading error={error} />;
  const dd = data.days[day];
  const lasers = laser ? dd.lasers.filter((l) => l.laser === laser) : dd.lasers;
  return (
    <>
      <PageTitle title="Schedule per Laser">
        One section per working day. Type <b>SIC Qty</b> (made) on each line; anything short is pushed to the next day.
        Type <b>Taken Qty</b> to take profiles from Plant 40 stock instead of cutting them.
        <span className="tag bal">BAL</span>
        <span className="tag rg">RG</span>
        <span className="tag rnd">R&amp;D</span>
        <span className="tag pushed">short - pushed</span>
        <span className="tag donecell">done</span>
      </PageTitle>
      <div className="day-picker">
        {[0, 1, 2, 3].map((w) => (
          <div key={w} className="week-chips">
            <span className="week-label">Week {"ABCD"[w]}</span>
            {data.days
              .filter((d) => Math.floor(d.d / 5) === w)
              .map((d) => (
                <button
                  key={d.d}
                  className={`daychip ${d.d === day ? "active" : ""} ${d.is_today ? "today" : ""}`}
                  onClick={() => setDay(d.d)}
                  title={d.title}
                >
                  {d.label.slice(7)} <span className="sub">{dateShort(d.date)}</span>
                </button>
              ))}
          </div>
        ))}
      </div>
      <div className="toolbar">
        <h2 className="day-title">
          {dd.title}
          {dd.is_today && <span className="today-badge">TODAY</span>}
        </h2>
        <div className="seg">
          {[0, 1, 2, 3].map((l) => (
            <button key={l} className={laser === l ? "active" : ""} onClick={() => setLaser(l)}>
              {l ? `Laser ${l}` : "All lasers"}
            </button>
          ))}
        </div>
      </div>
      <div className={`laser-grid n${lasers.length}`}>
        {lasers.map((l) => (
          <LaserPanel key={l.laser} l={l} />
        ))}
      </div>
    </>
  );
}

function LaserPanel({ l }: { l: Laser }) {
  const sections = ["push", "bal", "part", "rnd"] as const;
  const save = (key: string, field: string) => (v: string | number | null) => patchDict("spl", { [key]: { [field]: v } });
  return (
    <section className="card laser">
      <div className="card-head">
        <h2>LASER {l.laser}</h2>
        <span className={`load ${loadClass(l.load)}`}>{pct(l.load)}</span>
        <span className="muted">{l.hours_text}</span>
      </div>
      <div className="laser-stats">
        <span>Products: {l.products}</span>
        <span>Output: {gen(l.output)}</span>
        <span>Stock taken: {gen(l.stock_taken)}</span>
      </div>
      {l.gauges.length > 0 && (
        <div className="laser-stats small">
          By gauge:{" "}
          {l.gauges.map((g) => (
            <span key={g.gauge}>
              {g.gauge}mm: {gen(g.qty)}
            </span>
          ))}
          {l.stock_saves_h > 0 && <span>| Stock saves {l.stock_saves_h.toFixed(1)} h</span>}
        </div>
      )}
      {l.warnings.map((w) => (
        <div key={w} className="warn-line">
          {w}
        </div>
      ))}
      <div className="table-wrap">
        <table className="grid spl">
          <thead>
            <tr>
              <th>Product</th>
              <th>Part Number</th>
              <th>Gauge</th>
              <th>Qty needed</th>
              <th>Stock</th>
              <th>Stock taken</th>
              <th>Taken Qty</th>
              <th>SIC Qty</th>
              <th>Comment</th>
            </tr>
          </thead>
          <tbody>
            {sections.map((sec) => {
              const rows = l.rows.filter((r) => r.sec === sec);
              if (!rows.length) return null;
              return [
                <tr key={sec + "h"} className="section-row">
                  <td colSpan={9}>{SEC_LABEL[sec]}</td>
                </tr>,
                ...rows.map((r) => {
                  const cls = [
                    r.sec === "rnd" ? "row-rnd" : "",
                    String(r.product).startsWith("BAL ") ? "row-bal" : "",
                    String(r.product).startsWith("RG ") ? "row-rg" : "",
                    r.push_qty > 0 ? "row-short" : "",
                    r.complete ? "row-done" : "",
                  ].join(" ");
                  return (
                    <tr key={r.key} className={cls}>
                      <td className={r.back_order ? "bo" : ""}>{r.product}</td>
                      <td>{r.part}</td>
                      <td className="num">{gen(r.gauge)}</td>
                      <td className="num b">{gen(r.qty)}</td>
                      <td className={`small ${String(r.stock_comment).startsWith("Not") ? "warn-text" : ""}`}>
                        {r.stock_comment}
                      </td>
                      <td className="num">{r.stock_taken ? gen(r.stock_taken) : ""}</td>
                      <td className={r.taken != null ? "typed" : ""}>
                        {r.sec !== "rnd" && <Cell value={r.taken} kind="number" onSave={save(r.key, "taken")} width={52} />}
                      </td>
                      <td>
                        {r.sec !== "rnd" && <Cell value={r.sic} kind="number" onSave={save(r.key, "sic")} width={52} />}
                      </td>
                      <td>
                        <Cell value={r.comment} onSave={save(r.key, "comment")} width={120} />
                      </td>
                    </tr>
                  );
                }),
              ];
            })}
            {l.rows.length === 0 && (
              <tr>
                <td colSpan={9} className="muted c">
                  Nothing planned on this laser.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
