import { useRef, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { uploadFile, useMeta } from "../api";
import { dateLong } from "../format";

export const NAV: { group: string; items: { path: string; label: string }[] }[] = [
  {
    group: "Planning",
    items: [
      { path: "/jobs-released", label: "Jobs Released" },
      { path: "/back-orders", label: "Back Orders" },
      { path: "/profile-balancing", label: "Profile Balancing" },
      { path: "/rg-released-jobs", label: "RG Released Jobs" },
      { path: "/rnd", label: "R&D" },
      { path: "/cleaning", label: "Cleaning" },
    ],
  },
  {
    group: "Plan & reports",
    items: [
      { path: "/average-cutting-plan", label: "Average Cutting Plan" },
      { path: "/management-report", label: "Management Report" },
      { path: "/schedule-per-laser", label: "Schedule per Laser" },
      { path: "/output", label: "Output" },
      { path: "/jobs-completed", label: "Jobs Completed" },
    ],
  },
  {
    group: "Stock & orders",
    items: [
      { path: "/plant-40-stock", label: "Plant 40 Stock" },
      { path: "/bczb-list", label: "BCZB List" },
      { path: "/pending-containers", label: "Pending Containers" },
      { path: "/order-book", label: "Order Book" },
      { path: "/shutdown-stock", label: "Shutdown Stock Tracking" },
    ],
  },
  {
    group: "Setup",
    items: [
      { path: "/profiles-per-product", label: "Profiles per Product" },
      { path: "/data", label: "Data (settings)" },
    ],
  },
];

export function Layout({ children }: { children: ReactNode }) {
  const meta = useMeta();
  const [open, setOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState("");
  async function doImport(f: File) {
    if (!confirm(`Replace ALL planner data with the contents of ${f.name}?\n\nTip: download a backup first.`)) return;
    setBusy("Importing workbook…");
    try {
      const r = await uploadFile("/api/import", f);
      alert(`Imported ${r.jobs} released jobs and ${r.profiles} master profile rows.`);
    } catch (e) {
      alert(String((e as Error).message));
    } finally {
      setBusy("");
    }
  }
  return (
    <div className={`app ${open ? "nav-open" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="logo" aria-hidden>
            ⟋
          </span>
          <div>
            <div className="brand-name">Laser Planner</div>
            <div className="brand-sub">cutting plan &amp; schedule</div>
          </div>
        </div>
        <nav>
          {NAV.map((g) => (
            <div key={g.group} className="nav-group">
              <div className="nav-title">{g.group}</div>
              {g.items.map((it) => (
                <NavLink key={it.path} to={it.path} onClick={() => setOpen(false)}>
                  {it.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <a className="btn small ghost" href="/api/export">
            Download backup
          </a>
          <button className="btn small ghost" onClick={() => fileRef.current?.click()}>
            Import Excel planner…
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f) doImport(f);
            }}
          />
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="menu-btn" onClick={() => setOpen(!open)} aria-label="Menu">
            ☰
          </button>
          <div className="topbar-info">
            {meta && (
              <>
                <span className="chip">Planning date: {dateLong(meta.today)}</span>
                <span className="chip">Week A starts {dateLong(meta.week_a_monday)}</span>
              </>
            )}
          </div>
          {meta && (
            <div className={`headline ${/OVER|WARNING|not scheduled|no laser/i.test(meta.headline) ? "warn" : ""}`}>
              {meta.headline}
            </div>
          )}
        </header>
        {busy && <div className="busy">{busy}</div>}
        <main className="content">{children}</main>
      </div>
    </div>
  );
}

export function PageTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="page-title">
      <h1>{title}</h1>
      {children && <div className="page-help">{children}</div>}
    </div>
  );
}

export function Loading({ error }: { error?: string | null }) {
  if (error) return <div className="error-box">Could not load this page: {error}</div>;
  return <div className="loading">Calculating…</div>;
}

export function Tabs<T extends string | number>({
  items,
  value,
  onChange,
}: {
  items: { value: T; label: ReactNode; className?: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {items.map((it) => (
        <button
          key={String(it.value)}
          role="tab"
          aria-selected={it.value === value}
          className={`tab ${it.value === value ? "active" : ""} ${it.className || ""}`}
          onClick={() => onChange(it.value)}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}
