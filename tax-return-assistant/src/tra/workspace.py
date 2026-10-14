"""Where one client's files live for one income year.

    TRA_HOME/Clients/<code>/FY<year>/<Category>/   filed source documents + index.csv
    TRA_HOME/Work/<code>/FY<year>/                 figures.csv, state.json, Output/ ...
    TRA_HOME/audit/audit-<calendar year>.jsonl
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from pathlib import Path

from .dates import fy_label
from .models import ClientState
from .privacy.guard import atomic_write_text, check_value


class Workspace:
    def __init__(self, tra_home: Path, client_code: str, income_year: int):
        self.tra_home = Path(tra_home)
        self.client_code = client_code
        self.income_year = income_year

    @property
    def clients_dir(self) -> Path:
        return self.tra_home / "Clients" / self.client_code / fy_label(self.income_year)

    @property
    def work_dir(self) -> Path:
        return self.tra_home / "Work" / self.client_code / fy_label(self.income_year)

    @property
    def index_csv(self) -> Path:
        return self.clients_dir / "index.csv"

    @property
    def figures_csv(self) -> Path:
        return self.work_dir / "figures.csv"

    @property
    def cgt_csv(self) -> Path:
        return self.work_dir / "cgt_events.csv"

    @property
    def prefill_json(self) -> Path:
        return self.work_dir / "prefill.json"

    @property
    def prior_year_csv(self) -> Path:
        return self.work_dir / "prior_year.csv"

    @property
    def ingest_notes_json(self) -> Path:
        return self.work_dir / "ingest_notes.json"

    @property
    def state_json(self) -> Path:
        return self.work_dir / "state.json"

    @property
    def last_return_json(self) -> Path:
        return self.work_dir / "last_return.json"

    @property
    def output_dir(self) -> Path:
        return self.work_dir / "Output"

    @property
    def audit_path(self) -> Path:
        return self.tra_home / "audit" / f"audit-{date.today().year}.jsonl"

    def for_year(self, income_year: int) -> "Workspace":
        return Workspace(self.tra_home, self.client_code, income_year)

    def exists(self) -> bool:
        return self.clients_dir.is_dir() and self.work_dir.is_dir()

    def create(self, categories: list[str]) -> None:
        for category in categories:
            (self.clients_dir / category).mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> ClientState:
        return ClientState(**json.loads(self.state_json.read_text(encoding="utf-8")))

    def save_state(self, state: ClientState) -> None:
        data = dataclasses.asdict(state)
        check_value(data, "state.json")
        atomic_write_text(self.state_json, json.dumps(data, indent=2), "state.json", prechecked=True)
