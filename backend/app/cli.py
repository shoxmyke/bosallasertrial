"""Command line helpers.

    python -m app.cli import path/to/Laser_Cutting_Planner.xlsx   # load a workbook into the database
    python -m app.cli export backup.json                           # write a JSON backup
"""
import json
import sys

from .importer import load_workbook_state
from .store import Store


def main(argv):
    if len(argv) < 2 or argv[0] not in ("import", "export"):
        print(__doc__)
        return 1
    store = Store()
    if argv[0] == "import":
        st = load_workbook_state(argv[1])
        store.replace_all(st, action=f"import {argv[1]}")
        print(f"Imported {len(st['jobs'])} released jobs, {len(st['profiles'])} master profile rows, "
              f"{len(st['spl'])} typed Schedule per Laser lines.")
    else:
        json.dump(store.state(), open(argv[1], "w"), default=str, indent=1)
        print(f"Wrote {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
