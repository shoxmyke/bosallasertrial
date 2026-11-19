export type V = string | number | null | undefined | boolean;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DOWS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function isNum(x: unknown): x is number {
  return typeof x === "number" && isFinite(x);
}

export function num(x: V, dp = 0): string {
  if (!isNum(x)) return x == null ? "" : String(x);
  return x.toLocaleString("en-ZA", { minimumFractionDigits: dp, maximumFractionDigits: dp }).replace(/ /g, " ");
}

/** Show a value without trailing zeros, like Excel's General format. */
export function gen(x: V): string {
  if (!isNum(x)) return x == null ? "" : String(x);
  if (Number.isInteger(x)) return String(x);
  return String(Math.round(x * 1000) / 1000);
}

export function pct(x: V, dp = 0): string {
  if (!isNum(x)) return x == null ? "" : String(x);
  return `${(x * 100).toFixed(dp)}%`;
}

export function hrs(x: V, dp = 2): string {
  if (!isNum(x)) return "";
  if (Math.abs(x) < 1e-9) return "0";
  return x.toFixed(dp);
}

export function parseISO(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

export function dateShort(x: V): string {
  if (typeof x !== "string") return x == null ? "" : String(x);
  const d = parseISO(x);
  if (!d) return x;
  return `${String(d.getDate()).padStart(2, "0")} ${MONTHS[d.getMonth()]}`;
}

export function dateLong(x: V): string {
  if (typeof x !== "string") return x == null ? "" : String(x);
  const d = parseISO(x);
  if (!d) return x;
  return `${DOWS[d.getDay()]} ${String(d.getDate()).padStart(2, "0")} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** Load % colour bands used on the plan (blue > 0, green >= 50%, amber >= 86%, red > 100%). */
export function loadClass(x: V): string {
  if (!isNum(x) || x <= 0.0000001) return "";
  if (x > 1.000001) return "load-over";
  if (x >= 0.86) return "load-high";
  if (x >= 0.5) return "load-mid";
  return "load-low";
}

/** Completion colour codes: 1 green, 2 yellow, 3 red. */
export function doneClass(code: V): string {
  return code === 1 ? "done-1" : code === 2 ? "done-2" : code === 3 ? "done-3" : "";
}
