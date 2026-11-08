"""Every number on screen comes from a saved result file.

Provenance.num() reads a value with the primary reader (pandas / json),
formats it, records it (file, row, column, format, value, text shown) and
returns the text. verify() re-reads every recorded value with a second,
independent reader (csv module, pyarrow, json with Decimal floats) and
refuses if any value or text differs. check_digits() refuses if any digit
in the visible text has no recorded source and is not an explicit fixed label.

Readers only accept files under <LAB_ROOT>/results/. Raw, clean and sealed
data are refused outright.
"""
from __future__ import annotations

import csv
import decimal
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd


class ProvenanceError(RuntimeError):
    pass


# --------------------------------------------------------------------------- formats
def _sign(x: float) -> str:
    return "+" if x > 0 else ("-" if x < 0 else "")


FORMATS = {
    "usd": lambda v: f"{_sign(v)}${abs(v):,.2f}",
    "usd0": lambda v: f"{_sign(v)}${abs(v):,.0f}",
    "int": lambda v: f"{int(round(v)):,}",
    "pct1": lambda v: f"{100 * v:.1f}%",
    "pp1": lambda v: f"{_sign(round(100 * v, 1))}{abs(100 * v):.1f} pp",
    "atr2": lambda v: f"{_sign(round(v, 2))}{abs(v):.2f} ATR",
    "num2": lambda v: f"{_sign(round(v, 2))}{abs(v):.2f}",
    "dec2": lambda v: f"{v:.2f}",        # a threshold or level, shown without a sign
    "str": lambda v: str(v),
}


def fmt(kind: str, v) -> str:
    if kind != "str" and (v is None or (isinstance(v, float) and math.isnan(v))):
        return "n/a"
    return FORMATS[kind](float(v) if kind != "str" else v)


# --------------------------------------------------------------------------- records
@dataclass
class Rec:
    id: int
    page: str
    file: str               # relative to the results folder
    row: str                # JSON path, or "col=value;..." row selector, or "*" for a count
    column: str
    op: str                 # "cell" | "count" | "json"
    where: dict
    format: str
    value: object
    text: str
    shown: bool = True


@dataclass
class Provenance:
    results: Path
    records: list = field(default_factory=list)
    page: str = ""
    _cache: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- path rule
    def path(self, rel: str) -> Path:
        p = (self.results / rel).resolve()
        res = self.results.resolve()
        if res not in p.parents and p != res:
            raise ProvenanceError(f"{rel}: the dashboard only reads saved result files under {res}")
        bad = {"raw", "clean", "sealed"}
        if any(part in bad for part in p.relative_to(res.parent).parts[:-1]) or "data" in p.relative_to(res.parent).parts:
            raise ProvenanceError(f"{rel}: the dashboard never reads data/")
        return p

    def exists(self, rel: str) -> bool:
        try:
            return self.path(rel).exists()
        except ProvenanceError:
            return False

    # ---------------------------------------------------------------- primary readers
    def _table(self, rel):
        if rel not in self._cache:
            p = self.path(rel)
            self._cache[rel] = (pd.read_parquet(p) if p.suffix == ".parquet"
                                else pd.read_csv(p, dtype=str, keep_default_na=False))
        return self._cache[rel]

    def _json(self, rel):
        if rel not in self._cache:
            self._cache[rel] = json.loads(self.path(rel).read_text())
        return self._cache[rel]

    def table(self, rel) -> pd.DataFrame:
        return self._table(rel).copy()

    def _rec(self, **kw) -> str:
        r = Rec(id=len(self.records), page=self.page, **kw)
        self.records.append(r)
        return r.text

    def json(self, rel: str, path: list, kind: str, shown: bool = True) -> str:
        v = self._json(rel)
        for k in path:
            v = v[k]
        return self._rec(file=rel, row="/".join(map(str, path)), column=str(path[-1]), op="json", where={},
                         format=kind, value=v, text=fmt(kind, v), shown=shown)

    def cell(self, rel: str, where: dict, column: str, kind: str, shown: bool = True) -> str:
        df = self._table(rel)
        m = pd.Series(True, index=df.index)
        for k, val in where.items():
            m &= df[k].astype(str) == str(val)
        rows = df[m]
        if len(rows) != 1:
            raise ProvenanceError(f"{rel}: {where} matches {len(rows)} rows, need exactly 1")
        v = rows[column].iloc[0]
        v = v.item() if hasattr(v, "item") else v
        if kind != "str":
            v = float(v) if str(v) not in ("", "nan", "NaN") else float("nan")
        sel = ";".join(f"{k}={val}" for k, val in where.items())
        return self._rec(file=rel, row=f"{sel} (row {int(rows.index[0])})", column=column, op="cell",
                         where=dict(where), format=kind, value=v, text=fmt(kind, v), shown=shown)

    def count(self, rel: str, where: dict, kind: str = "int", shown: bool = True) -> str:
        """Rows matching `where`, compared case-insensitively (true/True/TRUE are one value)."""
        df = self._table(rel)
        m = pd.Series(True, index=df.index)
        for k, val in where.items():
            m &= df[k].astype(str).str.lower() == str(val).lower()
        v = int(m.sum())
        return self._rec(file=rel, row="*", column=",".join(where), op="count", where=dict(where),
                         format=kind, value=v, text=fmt(kind, v), shown=shown)

    def value(self, text: str) -> float:
        """The recorded raw value behind a text this object returned (for chart geometry)."""
        for r in reversed(self.records):
            if r.text == text:
                return r.value
        raise KeyError(text)

    # ---------------------------------------------------------------- second, independent reader
    def _rows_csv(self, rel):
        p = self.path(rel)
        if p.suffix == ".parquet":
            import pyarrow.parquet as pq
            return pq.read_table(p).to_pylist()
        with open(p, newline="") as f:
            return list(csv.DictReader(f))

    @staticmethod
    def _num(x):
        if isinstance(x, (int, float, decimal.Decimal)):
            return float(x)
        if isinstance(x, str) and x.strip().lower() in ("", "nan", "none", "null"):
            return float("nan")   # an empty CSV cell is a missing number, as the first reader sees it
        try:
            return float(x)
        except (TypeError, ValueError):
            return x

    def reread(self, r: Rec):
        if r.op == "json":
            v = json.loads(self.path(r.file).read_text(), parse_float=decimal.Decimal)
            for k in r.row.split("/"):
                v = v[k] if not isinstance(v, list) else v[int(k)]
            return self._num(v) if r.format != "str" else str(v)
        rows = self._rows_csv(r.file)
        if r.op == "count":
            return sum(1 for x in rows if all(str(x.get(k)).lower() == str(val).lower() for k, val in r.where.items()))
        hit = [x for x in rows if all(str(x.get(k)) == str(val) for k, val in r.where.items())]
        if len(hit) != 1:
            raise ProvenanceError(f"second reader: {r.file} {r.where} matches {len(hit)} rows")
        v = hit[0][r.column]
        return self._num(v) if r.format != "str" else str(v)

    def verify(self) -> None:
        bad = []
        for r in self.records:
            v2 = self.reread(r)
            t2 = fmt(r.format, v2)
            same = t2 == r.text
            if r.format != "str":
                a, b = self._num(r.value), self._num(v2)
                if isinstance(a, float) and isinstance(b, float) and not (math.isnan(a) and math.isnan(b)):
                    same &= math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
            else:
                same &= str(r.value) == str(v2)
            if not same:
                bad.append(f"#{r.id} {r.file} {r.row} {r.column}: shown {r.text!r}, second reader {t2!r}")
        if bad:
            raise ProvenanceError("values differ between readers:\n  " + "\n  ".join(bad))

    def texts(self, page=None) -> list[str]:
        return [r.text for r in self.records if r.shown and (page is None or r.page == page)]

    def dump(self, path: Path) -> None:
        path.write_text(json.dumps([asdict(r) for r in self.records], indent=1, default=str) + "\n")


# --------------------------------------------------------------------------- digit check
def unsourced_digits(strings, allowed_texts, fixed_patterns) -> list[str]:
    """Return every visible string that still holds a digit after removing
    sourced texts and explicit fixed labels."""
    frags = sorted({t for t in allowed_texts if re.search(r"\d", t)}, key=len, reverse=True)
    pats = [re.compile(p) for p in fixed_patterns]
    bad = []
    frag_res = [re.compile(r"(?<![\d.,])" + re.escape(f) + r"(?![\d.,]*\d)") for f in frags]
    for s in strings:
        rest = s
        for f in frag_res:                # a sourced number only covers itself, never part of a longer one
            rest = f.sub(" ", rest)
        for p in pats:
            rest = p.sub(" ", rest)
        if re.search(r"\d", rest):
            bad.append(s)
    return bad
