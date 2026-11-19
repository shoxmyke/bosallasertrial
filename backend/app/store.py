"""Persistence: the planner's inputs live in SQLite, one row per section, with a change log.

The engine always works on the full state; storing each section as a JSON
document keeps the schema identical to the engine's input and makes import /
export / backup trivial. Every change is written to the history table.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import threading
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session

from .engine.calc import Plan
from .engine.state import empty_state

DB_PATH = os.environ.get("PLANNER_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "planner.db"))


class Base(DeclarativeBase):
    pass


class SectionRow(Base):
    __tablename__ = "sections"
    name = Column(String(64), primary_key=True)
    data = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class HistoryRow(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    section = Column(String(64), nullable=False, index=True)
    action = Column(String(32), nullable=False)
    detail = Column(Text, nullable=False)
    changed_at = Column(DateTime, nullable=False, index=True)


class Store:
    def __init__(self, path: str = DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.engine = create_engine(f"sqlite:///{path}", future=True)
        Base.metadata.create_all(self.engine)
        self.lock = threading.RLock()
        self.version = 0
        self._state: dict | None = None
        self._plan: tuple[int, str, Plan] | None = None

    # ---------------- state ----------------
    def state(self) -> dict:
        with self.lock:
            if self._state is None:
                st = empty_state()
                with Session(self.engine) as s:
                    for row in s.scalars(select(SectionRow)):
                        st[row.name] = json.loads(row.data)
                self._state = st
            return self._state

    def is_empty(self) -> bool:
        st = self.state()
        return not st["jobs"] and not st["profiles"]

    def _write(self, names: list[str], action: str, detail: Any) -> None:
        now = dt.datetime.now()
        with Session(self.engine) as s:
            for n in names:
                data = json.dumps(self._state[n], default=str)
                row = s.get(SectionRow, n)
                if row is None:
                    s.add(SectionRow(name=n, data=data, updated_at=now))
                else:
                    row.data = data
                    row.updated_at = now
            s.add(HistoryRow(section=",".join(names), action=action,
                             detail=json.dumps(detail, default=str)[:20000], changed_at=now))
            s.commit()
        self.version += 1
        self._plan = None

    def replace_all(self, new_state: dict, action: str = "import") -> None:
        with self.lock:
            base = empty_state()
            base.update(new_state)
            self._state = base
            self._write(list(base.keys()), action, {"sections": list(base.keys())})

    def set_section(self, name: str, data: Any) -> None:
        with self.lock:
            st = self.state()
            if name not in st:
                raise KeyError(name)
            st[name] = data
            self._write([name], "set", {"size": len(data) if hasattr(data, "__len__") else None})

    def update(self, name: str, fn, detail: Any) -> None:
        """Apply fn(section_data) in place and persist."""
        with self.lock:
            st = self.state()
            if name not in st:
                raise KeyError(name)
            fn(st[name])
            self._write([name], "update", detail)

    def history(self, limit: int = 100) -> list[dict]:
        with Session(self.engine) as s:
            rows = s.scalars(select(HistoryRow).order_by(HistoryRow.id.desc()).limit(limit))
            return [{"id": r.id, "section": r.section, "action": r.action, "detail": json.loads(r.detail),
                     "changed_at": r.changed_at.isoformat(timespec="seconds")} for r in rows]

    # ---------------- plan ----------------
    def plan(self) -> Plan:
        with self.lock:
            today = dt.date.today().isoformat()
            if self._plan and self._plan[0] == self.version and self._plan[1] == today:
                return self._plan[2]
            p = Plan(copy.deepcopy(self.state()))
            self._plan = (self.version, today, p)
            return p
