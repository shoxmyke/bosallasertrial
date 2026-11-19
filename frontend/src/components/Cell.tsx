import { useEffect, useRef, useState } from "react";
import type { V } from "../format";

type Kind = "text" | "number" | "date" | "x" | "time";

/** An editable cell. Saves when you leave the cell or press Enter; Esc cancels. */
export function Cell({
  value,
  kind = "text",
  onSave,
  placeholder,
  width,
  className = "",
  title,
  disabled,
}: {
  value: V;
  kind?: Kind;
  onSave: (v: string | number | null) => Promise<void>;
  placeholder?: string;
  width?: number | string;
  className?: string;
  title?: string;
  disabled?: boolean;
}) {
  const shown = value == null ? "" : String(value);
  const [text, setText] = useState(shown);
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  const [err, setErr] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (document.activeElement !== ref.current) setText(shown);
  }, [shown]);

  async function commit(next: string) {
    if (next === shown) return;
    setState("saving");
    try {
      let v: string | number | null = next.trim() === "" ? null : next;
      if (kind === "number" && v !== null) {
        const n = Number(String(v).replace(",", "."));
        v = isFinite(n) ? n : v;
      }
      await onSave(v);
      setState("idle");
    } catch (e) {
      setState("error");
      setErr(String((e as Error).message || e));
      setText(shown);
    }
  }

  if (kind === "x") {
    const on = shown.trim().toUpperCase() === "X";
    return (
      <button
        type="button"
        className={`xbox ${on ? "on" : ""} ${state} ${className}`}
        title={title || (on ? "Click to clear" : "Click to mark X")}
        disabled={disabled}
        onClick={() => commit(on ? "" : "X")}
      >
        {on ? "X" : ""}
      </button>
    );
  }

  return (
    <input
      ref={ref}
      className={`cell ${kind} ${state} ${className}`}
      style={width ? { width } : undefined}
      type={kind === "date" ? "date" : kind === "time" ? "time" : "text"}
      inputMode={kind === "number" ? "decimal" : undefined}
      value={text}
      placeholder={placeholder}
      title={state === "error" ? err : title}
      disabled={disabled}
      onChange={(e) => {
        setText(e.target.value);
        if (kind === "date") commit(e.target.value);
      }}
      onBlur={() => kind !== "date" && commit(text)}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") {
          setText(shown);
          setTimeout(() => (e.target as HTMLInputElement).blur());
        }
      }}
    />
  );
}
