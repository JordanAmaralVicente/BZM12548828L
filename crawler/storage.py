"""Histórico de preços em CSV (versionado no git)."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRICES_CSV = DATA / "prices.csv"
RUNS_CSV = DATA / "runs.csv"
STATE_JSON = DATA / "state.json"

PRICE_FIELDS = ["ts", "store", "product", "price", "title", "url"]
RUN_FIELDS = ["ts", "store", "status", "raw_items", "matched", "message"]


def _append(path: Path, fields: list[str], rows: list[dict]) -> None:
    DATA.mkdir(exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def append_prices(rows: list[dict]) -> None:
    _append(PRICES_CSV, PRICE_FIELDS, rows)


def append_runs(rows: list[dict]) -> None:
    _append(RUNS_CSV, RUN_FIELDS, rows)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_prices() -> list[dict]:
    rows = _read(PRICES_CSV)
    for r in rows:
        r["price"] = float(r["price"])
    return rows


def load_runs() -> list[dict]:
    return _read(RUNS_CSV)
