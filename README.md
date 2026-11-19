# Laser Cutting Planner (web app)

The Excel planner (`Laser_Cutting_Planner_v35_November_2026.xlsx`) turned into a website:

- **Frontend** (`frontend/`): React + TypeScript. One page per tab you use.
- **Backend** (`backend/`): Python + FastAPI + SQLite. It holds all the data and **every calculation and
  formula** of the workbook, including the 8 hidden calculation tabs.

## Run it

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install && npm run build
cd ../backend && python -m app.cli import ../seed/Laser_Cutting_Planner_v35_November_2026.xlsx   # first time only
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000. Or run `./run.sh`, which does all of the above. It imports the workbook only if the
database is empty.

While working on the frontend: run `npm run dev` in `frontend/` (port 5173, API calls are proxied to port 8000).

## Host it on Render

1. On https://render.com, sign in (you can use your GitHub account), then go to **New → Blueprint**.
2. Pick the repository `shoxmyke/bosallasertrial`. Render reads `render.yaml`.
3. When asked for `PLANNER_PASSWORD`, type the password your team will use. Then click **Apply**.
4. When the deploy is finished, open the `…onrender.com` link. The browser asks for a user name (anything) and
   the password.
5. First time only: click **Import Excel planner…** (bottom left) and choose the v35 workbook.

The service uses the Starter plan with a 1 GB disk (about USD 7.25 a month). The free plan has no disk, so
everything typed would be lost on every restart. Change the password any time under the service's
**Environment** settings. Use **Download backup** now and then.

## Tabs → pages

| Workbook tab | In the app |
|---|---|
| Jobs Released, Back Orders, Profile Balancing, RG Released Jobs, R&D, Cleaning | Pages (Planning) - type here |
| Average Cutting Plan, Management Report, Schedule per Laser, Output, Jobs Completed | Pages (Plan & reports). On Schedule per Laser you type SIC Qty, Taken Qty and comments |
| Plant 40 Stock, BCZB List, Pending Containers, Order Book, Shutdown Stock Tracking | Pages (Stock & orders) |
| Profiles per Product, Data (+ Cutting Speed table) | Pages (Setup) |
| Priority Calc, Balance Calc, Job Schedule, Plan Calc, Laser Detail, Laser Parts, Stock Calc, Completion Calc, Cutting Speed | **Backend only** - `backend/app/engine/calc.py` |
| Lessons Learned | Data kept in the database (no page) |
| All Planning, Select Planning, Unique Parts per Product, Manu_Time_Hrs, Profiles_per_Product | Dropped (not used / broken `#REF!`) |

## Where the logic lives

- `backend/app/engine/calc.py`: the planning engine. Each stage is named after the tab it replaces
  (`calc_priority` = Priority Calc, `calc_job_schedule` = Job Schedule, …).
- `backend/app/engine/pages.py`: what each page shows (the formulas on the visible tabs: checks, statuses,
  colours, totals).
- `backend/app/importer.py`: reads the typed cells of an Excel planner (v35 layout). You can also use
  "Import Excel planner…" in the app.
- `backend/app/store.py`: SQLite storage. Every change is logged in the `history` table (`GET /api/history`).

The whole plan is recalculated on the server after every change (about 0.1 s).

## Checked against Excel

`backend/tests/verify_against_excel.py` imports a workbook, runs the engine and compares it, cell by cell,
with the values Excel calculated: about 200,000 cells across all the calculation tabs and the pages.

- Your v35 workbook: everything matches. The one difference is a text cell where Excel shows `0,0` because of
  the comma-decimal locale.
- `tests/make_scenario.py` writes changed copies of the workbook (R&D programs, cleaning, containers, pushes,
  SIC changes, 1 shift, other OEE and limits). LibreOffice recalculates them and the engine matches those too.

```bash
cd backend && python -m tests.verify_against_excel ../seed/Laser_Cutting_Planner_v35_November_2026.xlsx
```

## Deliberate differences from the workbook

1. **Typed numbers on Schedule per Laser follow their line.** In Excel, SIC / Taken Qty sit in fixed cells.
   When the plan moves, they can end up next to a different part or on an empty row. The app stores them per
   day + laser + product + part.
2. **Balance quantities follow the job.** In Excel they belong to "Balance block 3". If a new balance order is
   added above, every block shifts. The app stores them on the job itself.
3. **Jobs Released week figures are per week.** In Excel, the "Products released / Total qty / Balance / Pushed"
   counters for Weeks B-D always showed 0, and Week A counted the whole month (the hidden "Week #" column was
   always 0). The app counts each week separately.
4. Plant 40 Stock "Qty Shipped" typed over the BCZB value is kept as an explicit override (bold), and can be
   cleared to go back to the BCZB value.
