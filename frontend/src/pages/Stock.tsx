import { useMemo, useState } from "react";
import { patchDict, putTable, usePage } from "../api";
import { Cell } from "../components/Cell";
import { Loading, PageTitle } from "../components/Layout";
import { TableEditor, type Col, type Rec } from "../components/TableEditor";
import { gen, num } from "../format";

// ------------------------------------------------------------------ Plant 40 Stock
type P40 = {
  bms: string;
  description: string;
  products: string;
  qty_product: number;
  consignment: string;
  qty_shipped: number | "";
  received: string;
  in_stock: number;
  taken: number;
  left: number;
  matches: string;
  override: boolean;
};

export function Plant40() {
  const { data, error } = usePage<{ summary: string; rows: P40[] }>("plant-40-stock");
  const [q, setQ] = useState("");
  const rows = useMemo(
    () => (data?.rows || []).filter((r) => !q || `${r.bms} ${r.description} ${r.products}`.toLowerCase().includes(q.toLowerCase())),
    [data, q],
  );
  if (!data) return <Loading error={error} />;
  return (
    <>
      <PageTitle title="Plant 40 Stock (profiles in stock)">
        Picks the planner's lines (Type = Profile with a BMS Part Number) from the BCZB List. Stock only counts once its
        container is marked received on the Data page. Stock is only taken when a Taken Qty is typed on the Schedule per
        Laser. You can type over <b>Qty Shipped</b> here (shown in bold); clear it to go back to the BCZB value.
      </PageTitle>
      <div className="summary">{data.summary}</div>
      <div className="toolbar">
        <input className="search" placeholder="Search part, description, product…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>BMS Part Number</th>
              <th>Description</th>
              <th>Product(s) where used</th>
              <th>Qty / Product</th>
              <th>Consignment</th>
              <th>Qty Shipped</th>
              <th>Received?</th>
              <th>Qty in stock</th>
              <th>Taken by production</th>
              <th>Stock left</th>
              <th>On the cutting list?</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.bms}>
                <td className="b">{r.bms}</td>
                <td className="small">{r.description}</td>
                <td className="small">{r.products}</td>
                <td className="num">{gen(r.qty_product)}</td>
                <td className="c">{r.consignment}</td>
                <td className={r.override ? "b" : ""}>
                  <Cell
                    kind="number"
                    value={r.qty_shipped}
                    width={64}
                    title={r.override ? "Typed here (clear to use the BCZB value)" : "From the BCZB List"}
                    onSave={(v) => patchDict("p40_qty_override", { [r.bms]: v })}
                  />
                </td>
                <td className={r.received === "Yes" ? "ok" : "warn-text small"}>{r.received}</td>
                <td className="num">{gen(r.in_stock)}</td>
                <td className={`num ${r.taken > 0 ? "done-1" : ""}`}>{gen(r.taken)}</td>
                <td className="num b">{gen(r.left)}</td>
                <td className={r.matches === "Yes" ? "" : "muted small"}>{r.matches}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ BCZB List
export function BCZB() {
  const { data, error } = usePage<{ columns: string[]; rows: Rec[]; totals: { Q: number; R: number } }>("bczb-list");
  if (!data) return <Loading error={error} />;
  const h = (i: number, fallback: string) => data.columns[i] || fallback;
  const edit = "A B C D E F G H I J K L M P".split(" ");
  const kinds: Record<string, "number"> = { F: "number", H: "number", I: "number", M: "number", P: "number" };
  const letters = "A B C D E F G H I J K L M N O P Q R".split(" ");
  const cols: Col[] = letters.map((k, i) => ({
    key: k,
    label: h(i, k),
    kind: kinds[k] || (["N", "O", "Q", "R"].includes(k) ? "number" : "text"),
    readOnly: !edit.includes(k),
    render: ["N", "O", "Q", "R"].includes(k) ? (r: Rec) => num(r[k] as number, k === "N" || k === "O" ? 2 : 2) : undefined,
  }));
  cols.push({ key: "W", label: "Status", readOnly: true, className: (r) => (String(r.W).startsWith("NOT") ? "warn-text small" : "small") });
  return (
    <>
      <PageTitle title="BCZB List (stock consignment list)">
        The stock list exactly as it comes from the consignment file (every type). Paste a new list with "Paste rows from
        Excel" (columns A to M, then Unit Cost). Months / years of stock and stock values are calculated.
      </PageTitle>
      <div className="summary">
        Stock value: EUR {num(data.totals.Q, 2)} | ZAR {num(data.totals.R, 2)} (@ 18.72)
      </div>
      <TableEditor
        columns={cols}
        rows={data.rows}
        searchKeys={["A", "B", "C", "D", "E", "G"]}
        onSave={(rows) =>
          putTable(
            "bczb",
            rows.map((r) => Object.fromEntries(edit.map((k) => [k, r[k] ?? null]))),
          )
        }
      />
    </>
  );
}

// ------------------------------------------------------------------ Pending Containers
type PL = { n: number; consignment: string; part: string; description: string; type: string; bms: string; products: string; qty: number; used: string };

export function PendingContainers() {
  const { data, error } = usePage<{
    not_received: string[];
    summary: string;
    by_type: { type: string; lines: number; pieces: number; used: string }[];
    total_lines: number;
    total_pieces: number;
    lines: PL[];
  }>("pending-containers");
  if (!data) return <Loading error={error} />;
  return (
    <>
      <PageTitle title="Pending Containers - everything still in a container that has not arrived">
        Fills itself from the BCZB List and the containers marked received on the Data page.
      </PageTitle>
      <div className="summary">
        Containers not received: {data.not_received.length ? data.not_received.join(", ") : "none - all containers received"}
        <br />
        {data.summary}
      </div>
      <div className="table-wrap narrow">
        <table className="grid">
          <thead>
            <tr>
              <th>Type</th>
              <th>Lines still to arrive</th>
              <th>Pieces still to arrive</th>
              <th>Used by the planner?</th>
            </tr>
          </thead>
          <tbody>
            {data.by_type.map((t) => (
              <tr key={t.type}>
                <td>{t.type}</td>
                <td className="num">{t.lines}</td>
                <td className="num">{gen(t.pieces)}</td>
                <td className="small">{t.used}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>Total</td>
              <td className="num">{data.total_lines}</td>
              <td className="num">{gen(data.total_pieces)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>#</th>
              <th>Consignment</th>
              <th>Part Number</th>
              <th>Description</th>
              <th>Type</th>
              <th>BMS Part Number</th>
              <th>Product Number(s)</th>
              <th>Qty Shipped</th>
              <th>Used by the planner?</th>
            </tr>
          </thead>
          <tbody>
            {data.lines.map((r) => (
              <tr key={r.n} className={r.used.startsWith("YES") ? "row-short" : ""}>
                <td className="num muted">{r.n}</td>
                <td className="c">{r.consignment}</td>
                <td>{r.part}</td>
                <td className="small">{r.description}</td>
                <td>{r.type}</td>
                <td>{r.bms}</td>
                <td className="small">{r.products}</td>
                <td className="num">{gen(r.qty)}</td>
                <td className="small">{r.used}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ Order Book / Shutdown Stock (pasted lists)
function RawList({ page, section, title, help }: { page: string; section: string; title: string; help: string }) {
  const { data, error } = usePage<{ columns: (string | null)[]; rows: unknown[][] }>(page);
  if (!data) return <Loading error={error} />;
  const cols: Col[] = data.columns.map((c, i) => ({ key: String(i), label: c || `Column ${i + 1}` }));
  const rows: Rec[] = data.rows.map((r) => Object.fromEntries(cols.map((c, i) => [c.key, r[i] ?? null])));
  return (
    <>
      <PageTitle title={title}>{help}</PageTitle>
      <TableEditor
        columns={cols}
        rows={rows}
        onSave={(rs) =>
          putTable(
            section,
            rs.map((r) =>
              cols.map((c) => {
                const v = r[c.key];
                if (typeof v === "string" && /^-?\d+(\.\d+)?$/.test(v.trim())) return Number(v);
                return v ?? null;
              }),
            ),
          )
        }
      />
    </>
  );
}

export function OrderBook() {
  return (
    <RawList
      page="order-book"
      section="order_book"
      title="Order Book"
      help="The order book as exported from the system. Paste a new export with 'Paste rows from Excel'."
    />
  );
}

export function ShutdownStock() {
  return (
    <RawList
      page="shutdown-stock"
      section="shutdown_stock"
      title="Shutdown Stock Tracking"
      help="Part stock against monthly demand during the shutdown, with the daily finished goods stock (FGS)."
    />
  );
}
