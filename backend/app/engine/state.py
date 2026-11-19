"""Shape of the planner's stored input state (everything a person types)."""
from __future__ import annotations


def empty_state() -> dict:
    return {
        "settings": {
            "oee": 0.7,
            "hours_mon_thu": [8, 22],   # 1 shift, 2 shifts
            "hours_fri": [8, 8],
            "shifts": 2,
            "max_qty_default": 100,
            "gauge_moved": 8,
            "trolley": 25,
            "trolley_40": 20,
            "lead_green": 2,
            "lead_red": 4,
            "light_clean_h": 1,
            "heavy_clean_h": 3,
            "containers": [{"name": "A", "received": True}, {"name": "B", "received": False}],
            "planning_date": None,        # None = follow today's date
            "job_size_limits": [
                {"up_to": 50, "max_per_day": None},
                {"up_to": 100, "max_per_day": None},
                {"up_to": 150, "max_per_day": None},
                {"up_to": 200, "max_per_day": None},
                {"up_to": None, "max_per_day": None},
            ],
            "colour_due_only": False,
            "week_a_monday": None,
            "line_capacity": 600,
        },
        "cutting_speed": [],
        "profiles": [],
        "jobs": [],
        "rg_jobs": [],
        "rnd": [],
        "cleaning": [],
        "spl": {},
        "back_orders": [],
        "bczb_columns": [],
        "bczb": [],
        "p40_qty_override": {},
        "order_book_columns": [],
        "order_book": [],
        "shutdown_columns": [],
        "shutdown_stock": [],
        "lessons": [],
        "mgmt_report": {"header_notes": {}},
        "jobs_completed": {"report_date": None},
    }
