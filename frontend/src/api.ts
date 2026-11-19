import { useCallback, useEffect, useRef, useState } from "react";

export type Day = { d: number; label: string; date: string; week: string; dow: string; is_today: boolean };
export type Meta = { today: string; first_planning_day: string; week_a_monday: string; days: Day[]; headline: string };

async function req(url: string, init?: RequestInit) {
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* not json */
    }
    throw new Error(msg);
  }
  return r.json();
}

// Every edit bumps this so open pages refresh their (server-calculated) data.
const listeners = new Set<() => void>();
export function onChange(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
function changed() {
  listeners.forEach((f) => f());
}

export async function patchRow(section: string, match: Record<string, unknown>, values: Record<string, unknown>) {
  await req(`/api/rows/${section}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ match, values }),
  });
  changed();
}

export async function patchDict(section: string, values: Record<string, unknown>) {
  await req(`/api/dict/${section}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ values }),
  });
  changed();
}

export async function putTable(section: string, rows: unknown[]) {
  await req(`/api/table/${section}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(rows),
  });
  changed();
}

export async function getState<T = unknown>(section: string): Promise<T> {
  return req(`/api/state/${section}`);
}

export async function uploadFile(url: string, file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await req(url, { method: "POST", body: fd });
  changed();
  return r;
}

export function usePage<T>(page: string) {
  const [data, setData] = useState<T | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const load = useCallback(async () => {
    const n = ++seq.current;
    try {
      const j = await req(`/api/pages/${page}`);
      if (n !== seq.current) return;
      setData(j.data);
      setMeta(j.meta);
      setError(null);
    } catch (e) {
      if (n === seq.current) setError(String((e as Error).message || e));
    } finally {
      if (n === seq.current) setLoading(false);
    }
  }, [page]);
  useEffect(() => {
    setLoading(true);
    load();
    const off = onChange(load);
    return () => {
      off();
    };
  }, [load]);
  return { data, meta, error, loading, reload: load };
}

export function useMeta() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    const load = () => req("/api/meta").then(setMeta).catch(() => undefined);
    load();
    const off = onChange(load);
    return () => {
      off();
    };
  }, []);
  return meta;
}
