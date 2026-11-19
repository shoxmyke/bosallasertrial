import { useEffect, useMemo, useState, type ReactNode } from "react";

export type Col = {
  key: string;
  label: string;
  kind?: "text" | "number";
  readOnly?: boolean;
  width?: number;
  render?: (row: Rec, i: number) => ReactNode;
  className?: (row: Rec, i: number) => string;
};
export type Rec = Record<string, unknown>;

const PAGE = 100;

/**
 * Edit a whole table locally, then save it in one go.
 * Paste from Excel: copy the rows (without the header) and use "Paste rows from Excel".
 */
export function TableEditor({
  columns,
  rows,
  onSave,
  editable = true,
  searchKeys,
  note,
}: {
  columns: Col[];
  rows: Rec[];
  onSave?: (rows: Rec[]) => Promise<void>;
  editable?: boolean;
  searchKeys?: string[];
  note?: ReactNode;
}) {
  const [draft, setDraft] = useState<Rec[]>(rows);
  const [dirty, setDirty] = useState(false);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [saving, setSaving] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  useEffect(() => {
    if (!dirty) setDraft(rows);
  }, [rows, dirty]);

  const editCols = columns.filter((c) => !c.readOnly);
  const filtered = useMemo(() => {
    const idx = draft.map((r, i) => ({ r, i }));
    if (!q) return idx;
    const ql = q.toLowerCase();
    const keys = searchKeys || columns.map((c) => c.key);
    return idx.filter(({ r }) => keys.some((k) => String(r[k] ?? "").toLowerCase().includes(ql)));
  }, [draft, q, columns, searchKeys]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const view = filtered.slice(page * PAGE, page * PAGE + PAGE);

  function set(i: number, key: string, v: string, kind?: string) {
    const next = draft.slice();
    let val: unknown = v === "" ? null : v;
    if (kind === "number" && v !== "") {
      const n = Number(v.replace(",", "."));
      if (isFinite(n)) val = n;
    }
    next[i] = { ...next[i], [key]: val };
    setDraft(next);
    setDirty(true);
  }

  function applyPaste(replace: boolean) {
    const lines = pasteText.replace(/\r/g, "").split("\n").filter((l) => l.trim() !== "");
    const recs = lines.map((l) => {
      const cells = l.split("\t");
      const rec: Rec = {};
      editCols.forEach((c, j) => {
        const v = (cells[j] ?? "").trim();
        if (v === "") rec[c.key] = null;
        else if (c.kind === "number" && isFinite(Number(v.replace(",", ".")))) rec[c.key] = Number(v.replace(",", "."));
        else rec[c.key] = v;
      });
      return rec;
    });
    setDraft(replace ? recs : [...draft, ...recs]);
    setDirty(true);
    setPasteOpen(false);
    setPasteText("");
  }

  async function save() {
    if (!onSave) return;
    setSaving(true);
    try {
      await onSave(draft);
      setDirty(false);
    } catch (e) {
      alert(String((e as Error).message));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="table-editor">
      <div className="toolbar">
        <input
          className="search"
          placeholder="Search…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(0);
          }}
        />
        <span className="muted">{filtered.length} rows</span>
        {editable && (
          <>
            <button
              className="btn small"
              onClick={() => {
                setDraft([...draft, {}]);
                setDirty(true);
                setQ("");
                setPage(Math.floor(draft.length / PAGE));
              }}
            >
              + Add row
            </button>
            <button className="btn small" onClick={() => setPasteOpen(!pasteOpen)}>
              Paste rows from Excel…
            </button>
            {dirty && (
              <>
                <button className="btn primary small" disabled={saving} onClick={save}>
                  {saving ? "Saving…" : "Save changes"}
                </button>
                <button
                  className="btn small ghost"
                  onClick={() => {
                    setDraft(rows);
                    setDirty(false);
                  }}
                >
                  Discard
                </button>
                <span className="dirty">Unsaved changes - the plan recalculates when you save</span>
              </>
            )}
          </>
        )}
      </div>
      {note && <div className="muted small">{note}</div>}
      {pasteOpen && (
        <div className="paste-box">
          <div className="small">
            Copy the rows in Excel (columns in this order: {editCols.map((c) => c.label).join(", ")}) and paste them
            here, without the header row.
          </div>
          <textarea value={pasteText} onChange={(e) => setPasteText(e.target.value)} rows={6} />
          <div>
            <button className="btn small primary" onClick={() => applyPaste(true)} disabled={!pasteText.trim()}>
              Replace all rows
            </button>
            <button className="btn small" onClick={() => applyPaste(false)} disabled={!pasteText.trim()}>
              Add to the end
            </button>
          </div>
        </div>
      )}
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th>#</th>
              {columns.map((c) => (
                <th key={c.key} className={c.readOnly ? "ro" : ""}>
                  {c.label}
                </th>
              ))}
              {editable && <th />}
            </tr>
          </thead>
          <tbody>
            {view.map(({ r, i }) => (
              <tr key={i}>
                <td className="num muted">{i + 1}</td>
                {columns.map((c) => (
                  <td key={c.key} className={`${c.kind === "number" ? "num" : ""} ${c.className ? c.className(r, i) : ""}`}>
                    {c.render ? (
                      c.render(r, i)
                    ) : editable && !c.readOnly ? (
                      <input
                        className={`cell ${c.kind || ""}`}
                        style={c.width ? { width: c.width } : undefined}
                        value={r[c.key] == null ? "" : String(r[c.key])}
                        onChange={(e) => set(i, c.key, e.target.value, c.kind)}
                      />
                    ) : (
                      String(r[c.key] ?? "")
                    )}
                  </td>
                ))}
                {editable && (
                  <td>
                    <button
                      className="icon-btn"
                      title="Delete row"
                      onClick={() => {
                        setDraft(draft.filter((_, k) => k !== i));
                        setDirty(true);
                      }}
                    >
                      ✕
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="pager">
          <button className="btn small" disabled={page === 0} onClick={() => setPage(page - 1)}>
            ‹ Prev
          </button>
          <span>
            Page {page + 1} of {pages}
          </span>
          <button className="btn small" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>
            Next ›
          </button>
        </div>
      )}
    </div>
  );
}
