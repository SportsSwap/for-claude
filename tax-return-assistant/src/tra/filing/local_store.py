"""TRA_HOME/Clients/<code>/FY<year>/<Category>/<filed name>, original copied unchanged."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..dates import fy_label
from .store import FiledRef, FilingRequest


class LocalStore:
    name = "local"

    def __init__(self, tra_home: Path):
        self.tra_home = Path(tra_home)

    def file(self, source: Path, req: FilingRequest) -> FiledRef:
        folder = self.tra_home / "Clients" / req.client_code / fy_label(req.income_year) / req.category
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / req.filed_name
        shutil.copy2(source, target)
        return FiledRef(location=str(target), store="local")
