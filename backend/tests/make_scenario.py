"""Write a modified copy of the planner (inputs changed, formulas kept) for LibreOffice to recalc."""
import sys, datetime as dt, openpyxl
src, dst, scen = sys.argv[1], sys.argv[2], sys.argv[3]
wb = openpyxl.load_workbook(src)
# fixed planning date + local cutting speed table (the workbook links to an external copy)
wb['Data']['B22'] = dt.datetime(2026, 11, 19)
wb['Jobs Completed']['B3'] = dt.datetime(2026, 11, 19)
ws = wb['Profiles per Product']
for r in range(2, ws.max_row + 1):
    v = ws.cell(row=r, column=9).value
    if isinstance(v, str) and v.startswith('='):
        ws.cell(row=r, column=9).value = v.replace("'[2]Cutting Speed'!", "'Cutting Speed'!")
if scen == 's1':
    rd = wb['R&D']
    rd['B6'], rd['C6'], rd['D6'], rd['E6'], rd['F6'] = 'RD-100', 6, 4, 'Laser 2', dt.datetime(2026, 11, 3)
    rd['B7'], rd['C7'], rd['D7'], rd['E7'], rd['F7'] = 'RD-101', 3, 2.5, 'Laser 1', dt.datetime(2026, 11, 8)
    rd['B8'], rd['C8'], rd['D8'], rd['E8'] = 'RD-102', 8, 1, 'Laser 3'
    cl = wb['Cleaning']
    cl['F10'] = 'X'; cl['E12'] = 'x'; cl['F17'] = 'X'; cl['J10'] = dt.time(6, 30)
    wb['Data']['B19'] = 'X'
    jr = wb['Jobs Released']
    jr['F12'] = 'X'          # push a Week A Monday job
    jr['AH10'] = dt.datetime(2026, 11, 10)   # move a Thursday start date
    bo = wb['Back Orders']
    bo['L6'] = dt.datetime(2026, 11, 24)
    spl = wb['Schedule per Laser']
    for r in range(55, 70):
        if isinstance(spl.cell(row=r, column=8).value, (int, float)):
            spl.cell(row=r, column=8).value = max(0, spl.cell(row=r, column=8).value - 10)
    for r in range(183, 200):
        spl.cell(row=r, column=17).value = 5
    wb['Profile Balancing']['E7'] = dt.datetime(2026, 11, 12)
    wb['Data']['C31'] = 50
if scen == 's2':
    wb['Average Cutting Plan']['B2'] = 1
    wb['Data']['B6'] = 75
    wb['Data']['B1'] = 0.65
    wb['Data']['B36'] = 'X'
    jr = wb['Jobs Released']
    jr['E9'] = 'X'           # turn the first job into a balance order
    rg = wb['RG Released Jobs']
    rg['B6'] = 29001; rg['D6'] = dt.datetime(2026, 11, 2); rg['E7'] = None; rg['F8'] = dt.datetime(2026, 11, 20)
wb.save(dst)
