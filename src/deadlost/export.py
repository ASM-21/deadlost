"""Export the expensive artifact as a reusable, documented dataset.

The engine evaluations are the only part of this repo that costs real time to
reproduce: roughly an hour of single-core Stockfish for 1,748 games and about
124,000 scored positions. Everything else is a few minutes of pandas. So the
useful thing to hand someone is not the analysis, it is the scored move table
with enough metadata attached to run their own analysis, and enough
documentation to know what they are holding.

This writes three files:

  moves.parquet        one row per evaluated move, joined to game metadata
  games.parquet        one row per evaluated game, with sampling stratum
  DATA_DICTIONARY.md   what every column means, how it was produced, and the
                       five traps that are easy to fall into with this data

The data dictionary is not optional garnish. Three of the errors made while
building this repo came from misreading a column: treating moves as independent
observations, dividing by a game's own length to build a time axis, and
comparing rating bands across corpora with different playing formats. Anyone
reusing this table can make the same mistakes, so the warnings ship with it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import paths
from .eval_run import load_evals
from .tracks.t1_ingest import load_games

TAGS = ("lichess", "twic", "panel", "otb")

DATA_DICTIONARY = """# deadlost analysis dataset

Engine-scored chess moves with game metadata. Produced by deadlost; see
FINDINGS.md for what was concluded from it and README.md for how to regenerate.

## Provenance

- **Games**: a 2017 scrape of lichess.org (CC0, via the datasnaek Kaggle
  dataset) and a 1998-2026 sample of The Week In Chess tournament PGN.
- **Evaluations**: Stockfish 16 NNUE, single thread, **fixed node budget**
  (20,000 nodes per position), transposition table reset per game.
- Fixed nodes rather than fixed time so the numbers reproduce on any machine
  regardless of load. Per-game hash reset so they do not depend on the order
  games were evaluated in.
- The first 8 plies of each game are treated as opening book and are not
  scored. Every game is scored to its end; nothing is truncated.
- Evaluations are clamped to +/- 1500 centipawns before any arithmetic.

## moves.parquet

One row per scored move.

| column | type | meaning |
|---|---|---|
| `game_id` | str | joins to `games.parquet`; prefixed by source |
| `sample` | str | which sample this game belongs to (see below) |
| `ply` | int | 0-based half-move index; ply 0 is White's first move |
| `mover` | str | `white` or `black`, the side that made this move |
| `fullmove` | int | standard chess move number |
| `cp_before` | int | evaluation before the move, **White's point of view**, clamped |
| `cp_after` | int | evaluation after the move actually played, White's POV, clamped |
| `loss_cp` | int | centipawns lost by `mover`, floored at 0 (see trap 3) |
| `white_elo`, `black_elo` | float | ratings at time of game |
| `result` | str | `1-0`, `0-1`, or `1/2-1/2` |
| `year` | float | year of the game (TWIC only; the lichess corpus is one 2017 scrape) |
| `tc_class` | str | time control class, or `otb` for over-the-board |
| `format` | str | `classical_otb`, `fast_otb` or `online`; inferred from Event/Site for TWIC (see trap 5) |
| `stratum` | str | the sampling cell this game was drawn from |

### Samples

| `sample` | design | use it for |
|---|---|---|
| `lichess` | 5 rating bands x 3 time buckets, 32 games each | rating and time-control comparisons |
| `twic` | 12 games per year, both players 2400-2499 | change over time at fixed rating |
| `panel` | 34 players x ~6 career years | within-player analysis |
| `otb` | 4 FIDE bands, 130 games each | rating comparisons with format held constant |

**Samples are stratified, not random.** Each was designed for one question.
Pooling them and computing a marginal statistic gives a number that describes
no population. In particular the `lichess` sample has equal counts per rating
band, which is not how the underlying corpus is distributed.

## games.parquet

One row per evaluated game: `game_id`, `sample`, `stratum`, `source`, ratings,
`result`, `ply_count`, `year`, `tc_class`, `eco`, `opening_name`, `moves`
(space-separated SAN).

## Five traps

**1. Moves are not independent observations.** One game contributes ~70
correlated moves; one player contributes many correlated games. Confidence
intervals computed at move level are roughly 1.5x too narrow, which is a 2.2x
error in effective sample size. Resample whole games (or players), don't treat
rows as draws.

**2. Do not build a per-move time axis from a game's own length.** Dividing a
time budget by the moves actually played makes the axis endogenous: a game that
ran long gets labelled "fast" because it lasted. In this data that does not
merely attenuate the time effect, it reverses its sign. Use
`(base + 40*increment) / 40` from `games.parquet`, which depends only on the
time control.

**3. `loss_cp` is floored at zero.** A move that appears to gain evaluation
means the previous search was shallow, not that the player found something
better than best play. Negative "losses" are set to 0. Mean `loss_cp` is
therefore slightly positive even for perfect play, and the floor matters most
at low node budgets.

**4. Rating and playing format are confounded across corpora.** The lichess
sample is online rapid at 1200-2200; the TWIC samples are over-the-board
classical at 2200+. They do not overlap in rating. Any comparison spanning both
varies two things at once. The `otb` sample exists precisely so rating can be
varied with format held constant.

**5. TWIC is not all classical over-the-board chess.** From 2020 it is majority
online blitz (chess.com "Titled Tuesday" and similar), and TWIC PGN has no
TimeControl tag. The `format` column is inferred from Event and Site headers.
Filter to `format == "classical_otb"` before describing classical play. An earlier
analysis on this data got a headline backwards by not doing so.

## Licence

Code Apache-2.0. Game scores are facts and not copyrightable; see NOTICE for the
upstream sources and their terms. Stockfish (GPL-3.0) was invoked as a separate
process and is neither included nor linked.
"""


def build_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    games = load_games()
    move_frames, game_frames = [], []

    for tag in TAGS:
        try:
            ev = load_evals(tag)
        except FileNotFoundError:
            continue
        sample_csv = paths.EVAL / f"eval_sample_{tag}.csv"
        if not sample_csv.exists():
            continue
        sample = pd.read_csv(sample_csv)
        # The panel sample's stratum is "player|year" but a year-only stratum
        # reads back from CSV as an int, so mixed dtypes reach parquet. Coerce.
        strata = sample.drop_duplicates(subset=["game_id"])[["game_id", "stratum"]].copy()
        strata["stratum"] = strata["stratum"].astype(str)

        meta_cols = [
            "game_id", "source", "white_elo", "black_elo", "result",
            "year", "tc_class", "format", "ply_count", "eco", "opening_name", "moves",
            "base_seconds", "increment_seconds",
        ]
        meta = games[meta_cols].merge(strata, on="game_id", how="inner")
        meta = meta.assign(sample=tag)

        m = ev.merge(
            meta[["game_id", "sample", "stratum", "white_elo", "black_elo", "result", "year", "tc_class", "format"]],
            on="game_id", how="inner",
        )
        move_frames.append(m)
        game_frames.append(meta)

    if not move_frames:
        raise FileNotFoundError("no engine evaluations found; run scripts/build_all.sh")

    moves = pd.concat(move_frames, ignore_index=True)
    gdf = pd.concat(game_frames, ignore_index=True).drop_duplicates(subset=["game_id", "sample"])

    cols = [
        "game_id", "sample", "ply", "mover", "fullmove", "cp_before", "cp_after",
        "loss_cp", "white_elo", "black_elo", "result", "year", "tc_class", "format", "stratum",
    ]
    moves = moves[[c for c in cols if c in moves.columns]]
    return moves, gdf


def export_all(out_dir: Path | None = None) -> list[Path]:
    out = out_dir or (paths.ROOT / "export")
    out.mkdir(parents=True, exist_ok=True)
    moves, gdf = build_tables()

    mp = out / "moves.parquet"
    gp = out / "games.parquet"
    dd = out / "DATA_DICTIONARY.md"
    moves.to_parquet(mp, index=False)
    gdf.to_parquet(gp, index=False)

    counts = moves.groupby("sample").agg(moves=("ply", "size"), games=("game_id", "nunique"))
    summary = "\n".join(
        f"| `{s}` | {int(r.games):,} | {int(r.moves):,} |" for s, r in counts.iterrows()
    )
    dd.write_text(
        DATA_DICTIONARY
        + "\n## Contents of this export\n\n| sample | games | scored moves |\n|---|---|---|\n"
        + summary
        + f"\n| **total** | **{moves.game_id.nunique():,}** | **{len(moves):,}** |\n"
    )
    return [mp, gp, dd]
