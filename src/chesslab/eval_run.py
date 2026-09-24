"""Select a bounded, stratified sample of games and evaluate every move.

Engine time is the binding constraint in this repo, so the sample is designed
rather than taken off the top of the file. Two independent samples:

`lichess` -- stratified on (rating band x time-control bucket). Downstream
tracks compare blunder rates *across* those cells, so cells are filled to equal
size where the corpus allows and the realised counts go in the manifest.

`twic` -- restricted to games where **both** players sit in a narrow Elo window
and stratified on year. That is the point of the rating-inflation track: hold
the nominal rating fixed and ask whether the play behind it changed.

Two properties matter for running this on a small machine:

1. **Strata-interleaved order.** Games are emitted round-robin across strata,
   so any prefix of the run is close to balanced. A run stopped early is still
   an analysable sample, not a sample of whichever cell sorted first.
2. **Sharded, resumable writes.** Completed games land in
   `data/eval/<tag>/shard_*.parquet`; re-invoking skips ids already on disk.
   Losing the process costs at most one shard.

Run:  python -m chesslab.eval_run --which lichess --per-cell 32 --nodes 20000
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import engine as eng
from . import paths
from .tracks.t1_ingest import load_games

SEED = 20260810

#: Time-control buckets for the lichess corpus, on estimated total seconds
#: (base + 40*increment). The corpus is overwhelmingly rapid, so these are the
#: bands that actually exist, not the bullet/blitz/rapid labels one would pick
#: if the data supported them.
TC_BUCKETS = [
    ("fast_<600s", 0, 600),
    ("mid_600-899s", 600, 900),
    ("slow_900s+", 900, 10 ** 9),
]

LICHESS_BANDS = ["1200-1400", "1400-1600", "1600-1800", "1800-2000", "2000-2200"]

TWIC_ELO_LO, TWIC_ELO_HI = 2400, 2500

EVAL_COLUMNS = ["game_id", "ply", "mover", "cp_before", "cp_after", "loss_cp", "fullmove"]


def est_seconds(df: pd.DataFrame) -> pd.Series:
    return df["base_seconds"].fillna(0) + 40 * df["increment_seconds"].fillna(0)


def tc_bucket(seconds: float) -> str | None:
    for name, lo, hi in TC_BUCKETS:
        if lo <= seconds < hi:
            return name
    return None


def interleave(sample: pd.DataFrame, stratum_col: str = "stratum") -> pd.DataFrame:
    """Reorder round-robin across strata so every prefix is near-balanced."""
    groups = [g.reset_index(drop=True) for _, g in sample.groupby(stratum_col, sort=True)]
    if not groups:
        return sample
    rows = []
    for i in range(max(len(g) for g in groups)):
        for g in groups:
            if i < len(g):
                rows.append(g.iloc[i])
    return pd.DataFrame(rows).reset_index(drop=True)


def select_lichess(df: pd.DataFrame, per_cell: int = 32) -> pd.DataFrame:
    d = df[(df.source == "lichess2017") & (df.rated == True)].copy()  # noqa: E712
    d["est_seconds"] = est_seconds(d)
    d["tc_bucket"] = d["est_seconds"].map(tc_bucket)
    # Both players in the same band keeps the "rating band" label unambiguous:
    # a 1300 vs 2100 game belongs to neither player's band.
    d = d[d.white_band == d.black_band]
    d = d[d.white_band.isin(LICHESS_BANDS)]
    d = d[d.tc_bucket.notna()]

    rng = np.random.default_rng(SEED)
    picks = []
    for band in LICHESS_BANDS:
        for name, _, _ in TC_BUCKETS:
            cell = d[(d.white_band == band) & (d.tc_bucket == name)]
            n = min(per_cell, len(cell))
            if n:
                idx = rng.choice(cell.index.values, size=n, replace=False)
                picks.append(cell.loc[idx])
    out = pd.concat(picks, ignore_index=True) if picks else d.head(0)
    out["stratum"] = out["white_band"] + "|" + out["tc_bucket"]
    return interleave(out)


def select_twic(df: pd.DataFrame, per_year: int = 12) -> pd.DataFrame:
    # Selection deliberately includes every format, reproducing the committed
    # samples exactly; non-classical games are dropped at load time
    # (eval_run.load_evals). A fresh redraw restricted to classical games would
    # add power but change every sampled game; see ROADMAP.md.
    d = df[(df.source == "twic")].copy()
    d = d[d.white_elo.between(TWIC_ELO_LO, TWIC_ELO_HI - 1) & d.black_elo.between(TWIC_ELO_LO, TWIC_ELO_HI - 1)]
    rng = np.random.default_rng(SEED + 1)
    picks = []
    for _year, cell in d.groupby("year"):
        n = min(per_year, len(cell))
        if n:
            idx = rng.choice(cell.index.values, size=n, replace=False)
            picks.append(cell.loc[idx])
    out = pd.concat(picks, ignore_index=True) if picks else d.head(0)
    out["stratum"] = out["year"].astype(int).astype(str)
    return interleave(out)


#: Elo bands for the format-controlled over-the-board sample (track 9).
OTB_BANDS = [(2200, 2400), (2400, 2500), (2500, 2600), (2600, 3200)]


def select_otb_bands(df: pd.DataFrame, per_band: int = 130) -> pd.DataFrame:
    """Equal-sized samples across TWIC rating bands, format held constant.

    Track 6 could only contrast online amateurs against over-the-board masters,
    which confounds rating with playing format (online rapid vs classical OTB).
    This sample varies rating *inside* one format so the two can be separated.
    Pairings are restricted to within 100 Elo so a band label describes both
    players, not just one.
    """
    # Selection deliberately includes every format, reproducing the committed
    # samples exactly; non-classical games are dropped at load time
    # (eval_run.load_evals). A fresh redraw restricted to classical games would
    # add power but change every sampled game; see ROADMAP.md.
    d = df[df.source == "twic"].dropna(subset=["white_elo", "black_elo"]).copy()
    d = d[(d.white_elo - d.black_elo).abs() <= 100]
    rng = np.random.default_rng(SEED + 2)
    picks = []
    for lo, hi in OTB_BANDS:
        cell = d[d.white_elo.between(lo, hi - 1) & d.black_elo.between(lo, hi - 1)]
        n = min(per_band, len(cell))
        if n:
            idx = rng.choice(cell.index.values, size=n, replace=False)
            chosen = cell.loc[idx].copy()
            chosen["stratum"] = f"{lo}-{hi}"
            picks.append(chosen)
    out = pd.concat(picks, ignore_index=True) if picks else d.head(0)
    return interleave(out)


def select_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Track 8's within-player panel. Selection lives in the track module."""
    from .tracks.t8_player_panel import build_panel_sample

    panel = build_panel_sample(df)
    # One row per game for evaluation; a game with two panel players is
    # evaluated once and both sides' moves are attributed downstream.
    uniq = panel.drop_duplicates(subset=["game_id"]).copy()
    return interleave(uniq)


def select(which: str, games: pd.DataFrame, per_cell: int = 32, per_year: int = 12, per_band: int = 130) -> pd.DataFrame:
    if which == "lichess":
        return select_lichess(games, per_cell)
    if which == "twic":
        return select_twic(games, per_year)
    if which == "otb":
        return select_otb_bands(games, per_band)
    return select_panel(games)


# --------------------------------------------------------------------------
# sharded storage
# --------------------------------------------------------------------------


def shard_dir(tag: str) -> Path:
    p = paths.EVAL / tag
    p.mkdir(parents=True, exist_ok=True)
    return p


def done_game_ids(tag: str) -> set[str]:
    ids: set[str] = set()
    for f in sorted(shard_dir(tag).glob("shard_*.parquet")):
        try:
            ids |= set(pd.read_parquet(f, columns=["game_id"]).game_id.unique())
        except Exception:  # noqa: BLE001
            continue
    return ids


#: Samples drawn from TWIC. Every analysis of these claims to describe classical
#: over-the-board play, which TWIC stopped being predominantly in 2020 (see
#: schema.classify_format). They are therefore filtered to classical games at
#: load time, in ONE place, so that no track can forget to.
TWIC_TAGS = frozenset({"twic", "otb", "panel"})


def load_evals(tag: str, classical_only: bool | None = None) -> pd.DataFrame:
    """All move evaluations for a tag, deduplicated on (game_id, ply).

    For TWIC-derived tags, games that are not classical over-the-board are
    dropped by default. Pass classical_only=False to get everything, which the
    format-contamination audit does on purpose.
    """
    files = sorted(shard_dir(tag).glob("shard_*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"no engine evaluations for '{tag}'. Run: python -m chesslab.eval_run --which {tag}"
        )
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df = df.drop_duplicates(subset=["game_id", "ply"]).reset_index(drop=True)
    if classical_only is None:
        classical_only = tag in TWIC_TAGS
    if classical_only:
        games = load_games()
        keep = set(games.loc[games.format == "classical_otb", "game_id"])
        df = df[df.game_id.isin(keep)].reset_index(drop=True)
    return df


def _write_shard(rows: list[dict], tag: str) -> None:
    if not rows:
        return
    path = shard_dir(tag) / f"shard_{int(time.time() * 1000)}.parquet"
    pd.DataFrame(rows, columns=EVAL_COLUMNS).to_parquet(path, index=False)


def run(
    sample: pd.DataFrame,
    tag: str,
    nodes: int,
    max_ply: int,
    skip_ply: int,
    shard_every: int = 40,
    time_budget: float | None = None,
) -> dict:
    """Evaluate the sample, resumably. Returns a manifest dict."""
    done = done_game_ids(tag)
    todo = sample[~sample.game_id.isin(done)]
    t0 = time.time()
    buf: list[dict] = []
    failed = 0

    if len(todo):
        with eng.Evaluator(nodes=nodes) as ev:
            for k, rec in enumerate(todo.itertuples(index=False), start=1):
                try:
                    game_rows = [
                        {
                            "game_id": me.game_id,
                            "ply": me.ply,
                            "mover": me.mover,
                            "cp_before": me.cp_before,
                            "cp_after": me.cp_after,
                            "loss_cp": me.loss_cp,
                            "fullmove": me.fullmove,
                        }
                        for me in ev.eval_game(rec.game_id, rec.moves, skip_opening_ply=skip_ply, max_ply=max_ply)
                    ]
                    buf.extend(game_rows)
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"[{tag}] game {rec.game_id} failed: {exc}", flush=True)
                if k % shard_every == 0:
                    _write_shard(buf, tag)
                    buf = []
                    el = time.time() - t0
                    print(f"[{tag}] {k}/{len(todo)} this run, {el:.0f}s, {el / k:.2f}s/game", flush=True)
                if time_budget is not None and time.time() - t0 > time_budget:
                    print(f"[{tag}] time budget reached after {k} games", flush=True)
                    break
    _write_shard(buf, tag)

    ev_df = load_evals(tag) if shard_dir(tag).glob("shard_*.parquet") else pd.DataFrame()
    covered = set(ev_df.game_id.unique()) if len(ev_df) else set()
    in_sample = sample[sample.game_id.isin(covered)]
    return {
        "tag": tag,
        "engine": eng.engine_id(),
        "engine_path": eng.find_engine(),
        "nodes_per_position": nodes,
        "skip_opening_ply": skip_ply,
        "max_ply": max_ply,
        "clamp_cp": eng.CLAMP_CP,
        "seed": SEED,
        "games_selected": int(len(sample)),
        "games_evaluated": int(len(in_sample)),
        "games_failed_this_run": failed,
        "plies_evaluated": int(len(ev_df)),
        "complete": bool(len(in_sample) >= len(sample) - failed),
        "strata_selected": sample["stratum"].value_counts().sort_index().to_dict(),
        "strata_evaluated": in_sample["stratum"].value_counts().sort_index().to_dict(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["lichess", "twic", "panel", "otb"], required=True)
    ap.add_argument("--per-cell", type=int, default=32)
    ap.add_argument("--per-year", type=int, default=12)
    ap.add_argument("--per-band", type=int, default=130)
    ap.add_argument("--nodes", type=int, default=20000)
    ap.add_argument("--max-ply", type=int, default=eng.DEFAULT_MAX_PLY)
    ap.add_argument("--skip-ply", type=int, default=eng.DEFAULT_SKIP_OPENING_PLY)
    ap.add_argument("--shard-every", type=int, default=40)
    ap.add_argument("--time-budget", type=float, default=None, help="seconds; checkpoint and stop")
    args = ap.parse_args()

    games = load_games()
    sample = select(args.which, games, args.per_cell, args.per_year, args.per_band)
    if args.which != "panel":
        # The panel CSV is written by the track module and carries per-player
        # rows, so it must not be overwritten with the per-game selection.
        sample[["game_id", "source", "stratum", "white_elo", "black_elo", "result", "ply_count", "year"]].to_csv(
            paths.EVAL / f"eval_sample_{args.which}.csv", index=False
        )
    manifest = run(
        sample, args.which, args.nodes, args.max_ply, args.skip_ply, args.shard_every, args.time_budget
    )
    (paths.RESULTS / f"t1_eval_scope_{args.which}.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: v for k, v in manifest.items() if not k.startswith("strata")}, indent=2))


if __name__ == "__main__":
    main()
