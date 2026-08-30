"""Track 1: build the shared games table.

Run:  python -m chesslab.tracks.t1_ingest

Writes `data/derived/games.parquet` and `results/t1_validation.json`.
"""

from __future__ import annotations

import json

import pandas as pd

from .. import ingest_lichess, ingest_twic, paths
from ..schema import COLUMNS, SCHEMA_VERSION, rating_band

LICHESS_CSV = paths.RAW / "lichess_games_2017.csv"
TWIC_DIR = paths.RAW / "twic"


def build(twic_limit: int | None = None) -> pd.DataFrame:
    frames = []
    reports = {}

    if LICHESS_CSV.exists():
        recs, rep = ingest_lichess.ingest(LICHESS_CSV, check_legality=True)
        frames.append(pd.DataFrame([r.as_row() for r in recs], columns=COLUMNS))
        reports["lichess2017"] = rep.as_dict()
    else:
        raise FileNotFoundError(f"missing {LICHESS_CSV}; run scripts/fetch_data.sh")

    files = sorted(TWIC_DIR.glob("twic*.pgn"), key=lambda p: int("".join(c for c in p.stem if c.isdigit())))
    if twic_limit:
        files = files[:twic_limit]
    if not files:
        raise FileNotFoundError(f"no PGN files under {TWIC_DIR}; run scripts/fetch_data.sh")

    recs, rep = ingest_twic.ingest(files)
    d = rep.as_dict()
    d["issues_ingested"] = len(files)
    d["issue_range"] = [files[0].stem, files[-1].stem]
    frames.append(pd.DataFrame([r.as_row() for r in recs], columns=COLUMNS))
    reports["twic"] = d

    df = pd.concat(frames, ignore_index=True)
    df["white_band"] = df["white_elo"].map(rating_band)
    df["black_band"] = df["black_elo"].map(rating_band)

    paths.GAMES_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(paths.GAMES_PARQUET, index=False)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "rows": int(len(df)),
        "by_source": df["source"].value_counts().to_dict(),
        "reports": reports,
        "twic_year_span": [
            int(df.loc[df.source == "twic", "year"].min()),
            int(df.loc[df.source == "twic", "year"].max()),
        ],
        "lichess_tc_class_counts": df.loc[df.source == "lichess2017", "tc_class"].value_counts().to_dict(),
        "lichess_rated_share": float(df.loc[df.source == "lichess2017", "rated"].mean()),
        "eval_coverage_note": (
            "No upstream engine evaluations are used. Every centipawn number in this repo "
            "is computed locally by Stockfish 16 at a fixed node budget; see "
            "results/t1_eval_scope.json for the exact scope."
        ),
    }
    (paths.RESULTS / "t1_validation.json").write_text(json.dumps(summary, indent=2, default=str))
    return df


def load_games() -> pd.DataFrame:
    if not paths.GAMES_PARQUET.exists():
        raise FileNotFoundError("games.parquet missing; run python -m chesslab.tracks.t1_ingest")
    return pd.read_parquet(paths.GAMES_PARQUET)


if __name__ == "__main__":
    df = build()
    print(json.dumps(json.loads((paths.RESULTS / "t1_validation.json").read_text()), indent=2)[:4000])
