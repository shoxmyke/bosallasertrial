import { patchDict, putTable, usePage } from "../api";
import { Cell } from "../components/Cell";
import { Loading, PageTitle } from "../components/Layout";
import { TableEditor, type Col, type Rec } from "../components/TableEditor";
import { dateLong, gen, hrs } from "../format";

// ------------------------------------------------------------------ Profiles per Product
export function Profiles() {
  const { data, error } = usePage<{ rows: Rec[]; products: number }>("profiles-per-product");
  if (!data) return <Loading error={error} />;
  const editKeys = ["product", "part", "gauge", "profiles", "perimeter", "notes", "operations", "laser"];
  const cols: Col[] = [
    { key: "product", label: "Product Number", width: 110 },
    { key: "part", label: "Part Number", width: 120 },
    { key: "gauge", label: "Gauge (mm)", kind: "number", width: 50 },
    { key: "profiles", label: "Profiles / Product", kind: "number", width: 50 },
    { key: "perimeter", label: "Perimeter (mm)", kind: "number", width: 64 },
    { key: "notes", label: "Profile Notes", width: 110 },
    { key: "operations", label: "Additional Operations", width: 100 },
    { key: "laser", label: "Laser Number", width: 80 },
    { key: "speed", label: "Cutting Speed", readOnly: true, kind: "number", render: (r) => gen(r.speed as number) },
    { key: "mins", label: "Time (min)", readOnly: true, kind: "number", render: (r) => hrs(r.mins as number, 3) },
    { key: "hrs", label: "Time (hrs)", readOnly: true, kind: "number", render: (r) => hrs(r.hrs as number, 4) },
  ];
  return (
    <>
      <PageTitle title="Profiles per Product (laser master data)">
        One line per part of each product. Laser Number = Laser 1, Laser 2 or Laser 3 (anything else, e.g. Pressing or
        Buy-out, is not cut on the lasers). Cutting speed comes from the speed table on the Data page; time = perimeter /
        speed x profiles / OEE. {data.products} products.
      </PageTitle>
      <TableEditor
        columns={cols}
        rows={data.rows}
        searchKeys={["product", "part", "laser"]}
        onSave={(rows) => putTable("profiles", rows.map((r) => Object.fromEntries(editKeys.map((k) => [k, r[k] ?? null]))))}
      />
    </>
  );
}

// ------------------------------------------------------------------ Data (settings)
type Settings = {
  oee: number;
  hours_mon_thu: number[];
  hours_fri: number[];
  shifts: number;
  max_qty_default: number;
  gauge_moved: number;
  trolley: number;
  trolley_40: number;
  lead_green: number;
  lead_red: number;
  light_clean_h: number;
  heavy_clean_h: number;
  containers: { name: string; received: boolean }[];
  planning_date: string | null;
  colour_due_only: boolean;
  week_a_monday: string;
  line_capacity: number;
};
type Limit = { up_to: number | null; max_per_day: number | null; label: string; used: number; check: string };
type Speed = { gauge: number; l1: number | string; l2: number | string; l3: number | string; bms_inverse: number | string | null; inv: Record<string, number | null>; bms_speed: number | null };

export function DataPage() {
  const { data, error } = usePage<{
    settings: Settings;
    today: string;
    first_planning_day: string;
    limits: Limit[];
    cutting_speed: Speed[];
    factor_l1: number;
    factor_l3: number;
  }>("data");
  if (!data) return <Loading error={error} />;
  const s = data.settings;
  const set = (k: string) => (v: string | number | null) => patchDict("settings", { [k]: v });
  const setPair = (k: "hours_mon_thu" | "hours_fri", i: number) => (v: string | number | null) => {
    const next = [...s[k]];
    next[i] = Number(v ?? 0);
    return patchDict("settings", { [k]: next });
  };
  const setLimit = (i: number, f: "up_to" | "max_per_day") => (v: string | number | null) => {
    const next = data.limits.map(({ up_to, max_per_day }) => ({ up_to, max_per_day }));
    next[i] = { ...next[i], [f]: v == null ? null : Number(v) };
    return patchDict("settings", { job_size_limits: next });
  };
  const speedCols: Col[] = [
    { key: "gauge", label: "Gauge (mm)", kind: "number", width: 60 },
    { key: "l1", label: "Laser 1 (m/min)", kind: "number", width: 60 },
    { key: "l2", label: "Laser 2 (m/min)", kind: "number", width: 60 },
    { key: "l3", label: "Laser 3 (m/min)", kind: "number", width: 60 },
    { key: "bms_inverse", label: "BMS inverse speed (min/100mm)", kind: "number", width: 60 },
    { key: "inv1", label: "L1 inverse (min/100mm)", readOnly: true, render: (r) => hrs((r.inv as Record<string, number>)?.l1, 4) },
    { key: "inv2", label: "L2 inverse", readOnly: true, render: (r) => hrs((r.inv as Record<string, number>)?.l2, 4) },
    { key: "inv3", label: "L3 inverse", readOnly: true, render: (r) => hrs((r.inv as Record<string, number>)?.l3, 4) },
    { key: "bms", label: "BMS speed (m/min)", readOnly: true, render: (r) => hrs(r.bms_speed as number, 2) },
  ];
  return (
    <>
      <PageTitle title="Data (settings)">Working time, planning rules and stock settings used by every page.</PageTitle>
      <div className="settings-grid">
        <section className="card">
          <h2>Working time</h2>
          <div className="form">
            <label>
              OEE %
              <Cell kind="number" value={s.oee} onSave={set("oee")} width={70} />
            </label>
            <label>
              Shifts
              <select className="cell" value={s.shifts} onChange={(e) => set("shifts")(Number(e.target.value))}>
                <option value={1}>1 shift</option>
                <option value={2}>2 shifts</option>
              </select>
            </label>
            <div className="form-table">
              <span />
              <b>1 shift</b>
              <b>2 shifts</b>
              <span>Mon - Thu (hours)</span>
              <Cell kind="number" value={s.hours_mon_thu[0]} onSave={setPair("hours_mon_thu", 0)} width={60} />
              <Cell kind="number" value={s.hours_mon_thu[1]} onSave={setPair("hours_mon_thu", 1)} width={60} />
              <span>Fri (hours)</span>
              <Cell kind="number" value={s.hours_fri[0]} onSave={setPair("hours_fri", 0)} width={60} />
              <Cell kind="number" value={s.hours_fri[1]} onSave={setPair("hours_fri", 1)} width={60} />
            </div>
          </div>
        </section>
        <section className="card">
          <h2>Planning date</h2>
          <div className="form">
            <label>
              Today (planning date)
              <Cell kind="date" value={s.planning_date} onSave={set("planning_date")} />
            </label>
            <div className="muted small">
              {s.planning_date ? "Typed date in use - clear it to follow the real date." : "Follows the real date."} Using{" "}
              {dateLong(data.today)}.
            </div>
            <div>
              First planning day (next working day): <b>{dateLong(data.first_planning_day)}</b>
            </div>
            <div className="muted small">
              Back orders and balance orders with no start date start on this day.
            </div>
            <label>
              Week A commencing (Monday)
              <Cell kind="date" value={s.week_a_monday} onSave={set("week_a_monday")} />
            </label>
          </div>
        </section>
        <section className="card">
          <h2>Planning limits &amp; trolleys</h2>
          <div className="form">
            <label>
              Max qty per product per day (default)
              <Cell kind="number" value={s.max_qty_default} onSave={set("max_qty_default")} width={70} />
            </label>
            <label>
              Gauge moved off Laser 2 (mm)
              <Cell kind="number" value={s.gauge_moved} onSave={set("gauge_moved")} width={70} />
            </label>
            <div className="muted small">
              Hours factor Laser 1 vs Laser 2: {data.factor_l1.toFixed(3)} · Laser 3 vs Laser 2: {data.factor_l3.toFixed(3)}
            </div>
            <label>
              Trolley size (qty per trolley)
              <Cell kind="number" value={s.trolley} onSave={set("trolley")} width={70} />
            </label>
            <label>
              Trolley size for jobs released as {2 * (s.trolley_40 || 0)}
              <Cell kind="number" value={s.trolley_40} onSave={set("trolley_40")} width={70} />
            </label>
            <label>
              Job lines the scheduler holds
              <Cell kind="number" value={s.line_capacity} onSave={set("line_capacity")} width={70} />
            </label>
          </div>
        </section>
        <section className="card">
          <h2>Lead time, cleaning &amp; colours</h2>
          <div className="form">
            <label>
              Lead time GREEN when under (days)
              <Cell kind="number" value={s.lead_green} onSave={set("lead_green")} width={60} />
            </label>
            <label>
              Lead time RED when above (days)
              <Cell kind="number" value={s.lead_red} onSave={set("lead_red")} width={60} />
            </label>
            <label>
              Light cleaning - change slats only (hours)
              <Cell kind="number" value={s.light_clean_h} onSave={set("light_clean_h")} width={60} />
            </label>
            <label>
              Heavy cleaning - slats + clean inside (hours)
              <Cell kind="number" value={s.heavy_clean_h} onSave={set("heavy_clean_h")} width={60} />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={!!s.colour_due_only}
                onChange={(e) => patchDict("settings", { colour_due_only: e.target.checked })}
              />
              Only colour work that is due (days up to today)
            </label>
          </div>
        </section>
        <section className="card">
          <h2>Max qty per day by job size</h2>
          <table className="grid">
            <thead>
              <tr>
                <th>Job released quantity</th>
                <th>Up to</th>
                <th>Max qty per day</th>
                <th>Used</th>
                <th>Check</th>
              </tr>
            </thead>
            <tbody>
              {data.limits.map((l, i) => (
                <tr key={i}>
                  <td>{l.label}</td>
                  <td>
                    {i < data.limits.length - 1 ? (
                      <Cell kind="number" value={l.up_to} onSave={setLimit(i, "up_to")} width={60} />
                    ) : (
                      ""
                    )}
                  </td>
                  <td>
                    <Cell kind="number" value={l.max_per_day} onSave={setLimit(i, "max_per_day")} width={60} placeholder="default" />
                  </td>
                  <td className="num">{gen(l.used)}</td>
                  <td className="bad small">{l.check}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="muted small">
            Every job is limited to the max qty per day of the row its released quantity fits in. Empty = the default
            above. Use whole trolleys.
          </div>
        </section>
        <section className="card">
          <h2>Shipped containers</h2>
          <table className="grid">
            <thead>
              <tr>
                <th>Shipping consignment</th>
                <th>Received</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {s.containers.map((c, i) => (
                <tr key={i}>
                  <td>
                    <Cell
                      value={c.name}
                      onSave={(v) => {
                        const next = s.containers.map((x) => ({ ...x }));
                        next[i].name = String(v ?? "");
                        return patchDict("settings", { containers: next });
                      }}
                      width={60}
                    />
                  </td>
                  <td className="c">
                    <input
                      type="checkbox"
                      checked={c.received}
                      onChange={(e) => {
                        const next = s.containers.map((x) => ({ ...x }));
                        next[i].received = e.target.checked;
                        patchDict("settings", { containers: next });
                      }}
                    />
                  </td>
                  <td>
                    <button
                      className="icon-btn"
                      title="Remove"
                      onClick={() => patchDict("settings", { containers: s.containers.filter((_, k) => k !== i) })}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            className="btn small"
            onClick={() => patchDict("settings", { containers: [...s.containers, { name: "", received: false }] })}
          >
            + Add container
          </button>
          <div className="muted small">
            Tick a container when it has arrived - only then is its stock used on Plant 40 Stock and the Schedule per Laser.
          </div>
        </section>
      </div>
      <section className="card">
        <h2>Cutting speed (m/min per gauge and laser)</h2>
        <TableEditor
          columns={speedCols}
          rows={data.cutting_speed as unknown as Rec[]}
          onSave={(rows) =>
            putTable(
              "cutting_speed",
              rows.map((r) => ({ gauge: r.gauge, l1: r.l1, l2: r.l2, l3: r.l3, bms_inverse: r.bms_inverse })),
            )
          }
        />
      </section>
    </>
  );
}
