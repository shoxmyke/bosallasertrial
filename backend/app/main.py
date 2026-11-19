"""HTTP API for the laser cutting planner."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import pages
from .engine.state import empty_state
from .store import Store

app = FastAPI(title="Laser Cutting Planner", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Team password: when PLANNER_PASSWORD is set, the browser asks for it (any user name works).
PASSWORD = os.environ.get("PLANNER_PASSWORD", "")


@app.middleware("http")
async def team_password(request, call_next):
    import base64
    import hmac
    if PASSWORD and request.url.path != "/api/health":
        ok = False
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("basic "):
            try:
                _, _, pw = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
                ok = hmac.compare_digest(pw, PASSWORD)
            except Exception:  # noqa: BLE001
                ok = False
        if not ok:
            return Response("Password required", status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="Laser Planner"'})
    return await call_next(request)
store = Store()

# Sections made of rows identified by key fields (one row = one line on a page)
ROW_SECTIONS = {
    "jobs": ("day", "row"),
    "rg_jobs": ("row",),
    "rnd": ("row",),
    "cleaning": ("week", "laser"),
    "back_orders": ("row",),
}
# Sections that are a dictionary of values
DICT_SECTIONS = {"settings", "spl", "p40_qty_override", "mgmt_report", "jobs_completed"}
# Sections replaced as a whole table (master data and pasted lists)
TABLE_SECTIONS = {"profiles", "cutting_speed", "bczb", "bczb_columns", "order_book", "order_book_columns",
                  "shutdown_stock", "shutdown_columns", "lessons"}

NUMERIC_FIELDS = {"qty", "job", "gauge", "duration", "taken", "sic", "profiles", "perimeter", "l1", "l2", "l3",
                  "bms_inverse", "oee", "max_qty_default", "gauge_moved", "trolley", "trolley_40", "lead_green",
                  "lead_red", "light_clean_h", "heavy_clean_h", "shifts", "line_capacity", "up_to", "max_per_day",
                  "H", "F", "I", "M", "P"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")


def coerce(field: str, v: Any) -> Any:
    """Turn what the browser sent into what the engine expects."""
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return None
        base = field.split(".")[0]
        if base in NUMERIC_FIELDS and NUM_RE.match(s.replace(",", ".")):
            x = float(s.replace(",", "."))
            return int(x) if x.is_integer() else x
        if DATE_RE.match(s):
            return s
        return v
    return v


@app.on_event("startup")
def seed() -> None:
    path = os.environ.get("PLANNER_SEED_XLSX")
    if path and os.path.exists(path) and store.is_empty():
        from .importer import load_workbook_state
        store.replace_all(load_workbook_state(path), action="seed import")


# ---------------------------------------------------------------- reading
@app.get("/api/health")
def health():
    return {"ok": True, "version": store.version}


@app.get("/api/meta")
def meta():
    return pages.meta(store.plan())


@app.get("/api/pages/{page}")
def page(page: str):
    fn = pages.PAGES.get(page)
    if fn is None:
        raise HTTPException(404, f"Unknown page {page}")
    p = store.plan()
    data = fn(p)
    return JSONResponse(json.loads(json.dumps({"meta": pages.meta(p), "data": data}, default=_json_default)))


def _json_default(o):
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()[:10]
    if isinstance(o, set):
        return list(o)
    return str(o)


@app.get("/api/state/{section}")
def get_section(section: str):
    st = store.state()
    if section not in st:
        raise HTTPException(404)
    return st[section]


@app.get("/api/history")
def history(limit: int = 100):
    return store.history(limit)


# ---------------------------------------------------------------- editing
class RowPatch(BaseModel):
    match: dict
    values: dict


@app.patch("/api/rows/{section}")
def patch_row(section: str, body: RowPatch):
    if section not in ROW_SECTIONS:
        raise HTTPException(404, f"{section} is not a row section")
    keys = ROW_SECTIONS[section]
    match = {k: body.match.get(k) for k in keys}
    if any(v is None for v in match.values()):
        raise HTTPException(400, f"match needs {keys}")

    def apply(rows: list):
        row = next((r for r in rows if all(r.get(k) == v for k, v in match.items())), None)
        if row is None:
            row = dict(match)
            if section == "jobs":
                row.update(balance_qty={}, balance_date=None)
            if section == "rg_jobs":
                row.update(qty={})
            rows.append(row)
        for f, v in body.values.items():
            v = coerce(f, v)
            if "." in f:   # nested, e.g. balance_qty.3 or qty.12
                top, sub = f.split(".", 1)
                d = row.setdefault(top, {})
                if v is None:
                    d.pop(sub, None)
                else:
                    d[sub] = v
            else:
                row[f] = v
        rows.sort(key=lambda r: tuple(r.get(k) for k in keys))
        empty = all(v in (None, "", {}) for k, v in row.items() if k not in keys)
        if empty and section != "cleaning":
            rows.remove(row)

    store.update(section, apply, {"match": match, "values": body.values})
    return {"ok": True, "version": store.version}


class DictPatch(BaseModel):
    values: dict


@app.patch("/api/dict/{section}")
def patch_dict(section: str, body: DictPatch):
    if section not in DICT_SECTIONS:
        raise HTTPException(404, f"{section} is not a dictionary section")

    def apply(d: dict):
        for k, v in body.values.items():
            if section == "spl":
                cur = dict(d.get(k) or {})
                for f, x in (v or {}).items():
                    cur[f] = coerce(f, x)
                if all(x in (None, "") for x in cur.values()):
                    d.pop(k, None)
                else:
                    d[k] = cur
            elif section == "p40_qty_override":
                if v is None or v == "":
                    d.pop(k, None)
                else:
                    d[k] = coerce("qty", v)
            else:
                d[k] = coerce(k, v) if not isinstance(v, (list, dict)) else v

    store.update(section, apply, body.values)
    return {"ok": True, "version": store.version}


@app.put("/api/table/{section}")
def put_table(section: str, rows: list):
    if section not in TABLE_SECTIONS:
        raise HTTPException(404, f"{section} is not a table section")
    store.set_section(section, rows)
    return {"ok": True, "version": store.version}


# ---------------------------------------------------------------- import / export
@app.post("/api/import")
async def import_xlsx(file: UploadFile = File(...)):
    from .importer import load_workbook_state
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(await file.read())
        tmp = f.name
    try:
        st = load_workbook_state(tmp)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not read the workbook: {e}")
    finally:
        os.unlink(tmp)
    store.replace_all(st, action=f"import {file.filename}")
    return {"ok": True, "jobs": len(st["jobs"]), "profiles": len(st["profiles"])}


@app.get("/api/export")
def export():
    body = json.dumps(store.state(), default=str, indent=1)
    name = f"laser-planner-backup-{dt.date.today().isoformat()}.json"
    return Response(body, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/restore")
async def restore(file: UploadFile = File(...)):
    data = json.loads(await file.read())
    base = empty_state()
    unknown = set(data) - set(base)
    if unknown:
        raise HTTPException(400, f"Not a planner backup (unknown sections {sorted(unknown)[:5]})")
    store.replace_all(data, action=f"restore {file.filename}")
    return {"ok": True}


# ---------------------------------------------------------------- frontend
DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = os.path.join(DIST, path)
        if path and os.path.isfile(f):
            return FileResponse(f)
        return FileResponse(os.path.join(DIST, "index.html"))
