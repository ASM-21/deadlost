"""Filesystem layout. Everything derived lands under `data/derived`."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("CHESSLAB_ROOT", Path(__file__).resolve().parents[2]))

DATA = ROOT / "data"
RAW = DATA / "raw"
DERIVED = DATA / "derived"
EVAL = DATA / "eval"
FIGURES = ROOT / "figures"
RESULTS = ROOT / "results"

GAMES_PARQUET = DERIVED / "games.parquet"
MOVE_EVALS_PARQUET = EVAL / "move_evals.parquet"
EVAL_SAMPLE_CSV = EVAL / "eval_sample.csv"

for _p in (DERIVED, EVAL, FIGURES, RESULTS):
    _p.mkdir(parents=True, exist_ok=True)


def result_path(name: str) -> Path:
    return RESULTS / name


def figure_path(name: str) -> Path:
    return FIGURES / name
