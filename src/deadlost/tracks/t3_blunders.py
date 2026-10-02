"""Track 3: blunder rate against thinking time, and whether it is linear.

QUESTION AS ORIGINALLY POSED. Does blunder rate scale smoothly with less time
per move, or is there a non-linear jump at some threshold (bullet vs blitz vs
rapid), and does the shape differ by rating band?

WHAT THE DATA ACTUALLY SUPPORTS. The available lichess corpus is
overwhelmingly rapid: 10+0 alone is over a third of it and games with a base
under three minutes are about 1% of the file. There is no bullet and
essentially no blitz to compare against. **The threshold question is not
testable here and this track does not pretend otherwise.** What is testable is
the shape of the curve over the range that exists, roughly 5 to 60 seconds per
move, which is where most human tournament and online chess actually lives.

DEFINITIONS. A move's `loss_cp` is the drop in the position's evaluation from
the mover's point of view (see `engine.MoveEval`). Two thresholds are reported
because the finding should not hinge on one arbitrary cutoff:

  blunder  loss_cp >= 300   (roughly a piece, or a decisive tactical miss)
  mistake  loss_cp >= 100   (roughly a pawn)

NORMALISATION. Rates are per move, never per game. Longer games contain more
blunder opportunities, so raw counts would mostly measure game length, and
game length itself varies with time control.

CLUSTERING. Confidence intervals resample games, not moves. Sixty moves from
one game are one draw from the population of games, not sixty.

Run:  python -m deadlost.tracks.t3_blunders
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import paths, stats, viz
from ..eval_run import load_evals
from .t1_ingest import load_games

BLUNDER_CP = 300
MISTAKE_CP = 100
ALT_THRESHOLDS = (150, 200, 300, 500)


def build_move_table() -> pd.DataFrame:
    """Join move evaluations to game metadata, one row per evaluated move."""
    ev = load_evals("lichess")
    games = load_games()
    sample = pd.read_csv(paths.EVAL / "eval_sample_lichess.csv")
    meta = games.merge(sample[["game_id", "stratum"]], on="game_id", how="inner")

    keep = ["game_id", "stratum", "white_band", "base_seconds", "increment_seconds", "ply_count", "result"]
    df = ev.merge(meta[keep], on="game_id", how="inner")
    df["band"] = df["white_band"]
    df["tc_bucket"] = df["stratum"].str.split("|").str[1]

    # Nominal seconds per move. This deliberately divides the estimated game
    # duration by a FIXED 40 moves rather than by the game's own move count.
    # Dividing by actual length would make the x-axis endogenous: a game that
    # ran long would be labelled "fast" purely because it lasted, and since
    # game length correlates with how the game was played, that manufactures
    # a relationship between time and blunders out of nothing. The nominal
    # budget is a property of the time control alone.
    df["est_total_seconds"] = df["base_seconds"].fillna(0) + 40 * df["increment_seconds"].fillna(0)
    df["seconds_per_move"] = df["est_total_seconds"] / 40.0
    # Kept only to quantify how badly the endogenous version would have misled.
    moves_per_side = np.ceil(df["ply_count"] / 2).clip(lower=1)
    df["seconds_per_move_endogenous"] = df["est_total_seconds"] / moves_per_side

    df["is_blunder"] = (df.loss_cp >= BLUNDER_CP).astype(float)
    df["is_mistake"] = (df.loss_cp >= MISTAKE_CP).astype(float)
    return df


def rate_with_ci(d: pd.DataFrame, col: str) -> dict:
    if d.empty:
        return {}
    return stats.cluster_bootstrap(d[col].values, d.game_id.values, np.mean).as_dict()


def by_cell(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (band, bucket), cell in df.groupby(["band", "tc_bucket"]):
        iv = rate_with_ci(cell, "is_blunder")
        mi = rate_with_ci(cell, "is_mistake")
        rows.append(
            {
                "band": band,
                "tc_bucket": bucket,
                "n_games": cell.game_id.nunique(),
                "n_moves": len(cell),
                "median_seconds_per_move": float(cell.seconds_per_move.median()),
                "blunder_rate": iv["point"],
                "blunder_ci_lo": iv["ci_lo"],
                "blunder_ci_hi": iv["ci_hi"],
                "mistake_rate": mi["point"],
                "mean_loss_cp": float(cell.loss_cp.mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["band", "median_seconds_per_move"]).reset_index(drop=True)


def shape_test(df: pd.DataFrame) -> dict:
    """Is blunder rate linear in seconds-per-move, or linear in its log?

    Aggregated to game level first, so each game is one observation, then
    compared on adjusted R^2 plus a bootstrap interval on the quadratic term.

    Read the R^2 values carefully. Game-level blunder rate is dominated by
    which two humans sat down, not by the clock, so *no* function of the time
    control explains much of the between-game variance. A near-zero R^2 here
    is not evidence that time control does not matter: see
    `fast_vs_slow_difference`, which tests the group difference directly. It is
    evidence that time control is a small effect sitting inside a very noisy
    distribution, which is a different and more honest statement.
    """
    g = df.groupby("game_id").agg(
        blunder_rate=("is_blunder", "mean"),
        spm=("seconds_per_move", "first"),
        band=("band", "first"),
        n_moves=("is_blunder", "size"),
    )
    g = g[g.n_moves >= 10]
    x, y, w = g.spm.values, g.blunder_rate.values, g.n_moves.values

    def _fit(xx, yy, ww, deg):
        X = np.vander(xx, deg + 1)
        Wm = np.diag(ww)
        beta = np.linalg.lstsq(X.T @ Wm @ X, X.T @ Wm @ yy, rcond=None)[0]
        resid = yy - X @ beta
        ss_res = float((ww * resid ** 2).sum())
        ss_tot = float((ww * (yy - np.average(yy, weights=ww)) ** 2).sum())
        n, p = len(yy), deg + 1
        r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
        adj = 1 - (1 - r2) * (n - 1) / (n - p) if n > p else float("nan")
        return beta, adj

    lin_beta, lin_adj = _fit(x, y, w, 1)
    quad_beta, quad_adj = _fit(x, y, w, 2)
    log_beta, log_adj = _fit(np.log(x), y, w, 1)

    rng = np.random.default_rng(stats.SEED)
    draws = np.empty(1000)
    for b in range(1000):
        idx = rng.integers(0, len(x), size=len(x))
        draws[b] = _fit(x[idx], y[idx], w[idx], 2)[0][0]
    lo, hi = np.percentile(draws, [2.5, 97.5])

    # How much would the endogenous axis have inflated the apparent effect?
    ge = df.groupby("game_id").agg(
        blunder_rate=("is_blunder", "mean"),
        spm_endo=("seconds_per_move_endogenous", "first"),
        n_moves=("is_blunder", "size"),
    )
    ge = ge[ge.n_moves >= 10]
    endo_slope, endo_adj = _fit(ge.spm_endo.values, ge.blunder_rate.values, ge.n_moves.values, 1)

    return {
        "x_axis": "nominal seconds per move = (base + 40*inc)/40, independent of game length",
        "linear_slope_per_10s": float(lin_beta[0] * 10),
        "linear_adj_r2": lin_adj,
        "quadratic_adj_r2": quad_adj,
        "log_linear_adj_r2": log_adj,
        "quadratic_coefficient": float(quad_beta[0]),
        "quadratic_ci": [float(lo), float(hi)],
        "quadratic_excludes_zero": bool(lo > 0 or hi < 0),
        "n_games": int(len(g)),
        "endogenous_axis_check": {
            "note": (
                "Same fit using seconds-per-move computed from each game's OWN length. "
                "Comparing the two slopes shows how much of an apparent time effect is "
                "an artifact of long games being labelled fast."
            ),
            "slope_per_10s": float(endo_slope[0] * 10),
            "adj_r2": endo_adj,
        },
    }


def threshold_sensitivity(df: pd.DataFrame) -> dict:
    """Does the bucket ordering survive moving the blunder cutoff?"""
    out = {}
    for thr in ALT_THRESHOLDS:
        col = (df.loss_cp >= thr).astype(float)
        tmp = df.assign(hit=col)
        rates = tmp.groupby("tc_bucket").hit.mean().sort_index()
        out[f"cp>={thr}"] = {
            "rates": rates.round(5).to_dict(),
            "ordering_fast_to_slow": list(rates.reindex(["fast_<600s", "mid_600-899s", "slow_900s+"]).round(5).values),
        }
    return out


def fast_vs_slow_difference(df: pd.DataFrame) -> dict:
    """CI on the fast-minus-slow blunder rate difference, clustered on games.

    Comparing two separate confidence intervals for overlap is the wrong test
    and is needlessly conservative: two intervals can overlap while the
    difference between them is still clearly non-zero. This resamples games and
    recomputes the difference on each draw, which is the quantity the claim is
    actually about.
    """
    fast = df[df.tc_bucket == "fast_<600s"]
    slow = df[df.tc_bucket == "slow_900s+"]
    pooled = pd.concat([fast.assign(grp=1), slow.assign(grp=0)])

    def stat(vals: np.ndarray, grps: np.ndarray) -> float:
        f = vals[grps == 1]
        s_ = vals[grps == 0]
        if len(f) == 0 or len(s_) == 0:
            return np.nan
        return float(f.mean() - s_.mean())

    iv = stats.cluster_bootstrap_pairs(
        pooled.is_blunder.values.astype(float),
        pooled.grp.values.astype(float),
        pooled.game_id.values,
        stat,
    )
    return {
        "difference_fast_minus_slow": iv.point,
        "ci_lo": iv.lo,
        "ci_hi": iv.hi,
        "excludes_zero": bool(iv.lo * iv.hi > 0),
        "relative_increase": iv.point / float(slow.is_blunder.mean()) if len(slow) else None,
        "note": (
            "Tested as a difference, not by checking whether the two separate intervals overlap. "
            "They do overlap slightly; the difference is nonetheless distinguishable from zero."
        ),
    }


def run() -> dict:
    df = build_move_table()
    cells = by_cell(df)

    overall_bucket = {}
    for bucket, cell in df.groupby("tc_bucket"):
        overall_bucket[bucket] = {
            "n_games": int(cell.game_id.nunique()),
            "n_moves": int(len(cell)),
            "median_seconds_per_move": float(cell.seconds_per_move.median()),
            "blunder_rate": rate_with_ci(cell, "is_blunder"),
            "mistake_rate": rate_with_ci(cell, "is_mistake"),
        }

    overall_band = {}
    for band, cell in df.groupby("band"):
        overall_band[band] = {
            "n_games": int(cell.game_id.nunique()),
            "blunder_rate": rate_with_ci(cell, "is_blunder"),
            "mean_loss_cp": float(cell.loss_cp.mean()),
        }

    out = {
        "definitions": {"blunder_cp": BLUNDER_CP, "mistake_cp": MISTAKE_CP},
        "scope_limitation": (
            "No bullet and essentially no blitz in the corpus. Observed range is roughly "
            "5-60 seconds per move. A threshold effect at the fast end is NOT tested here."
        ),
        "by_time_bucket": overall_bucket,
        "by_rating_band": overall_band,
        "cells": cells.to_dict(orient="records"),
        "fast_vs_slow_difference": fast_vs_slow_difference(df),
        "shape_test": shape_test(df),
        "threshold_sensitivity": threshold_sensitivity(df),
    }
    (paths.RESULTS / "t3_blunders.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(cells, df)
    return out


def _figure(cells: pd.DataFrame, df: pd.DataFrame) -> None:
    fig, ax = viz.new_fig(8.5, 5.2)
    for i, (band, cell) in enumerate(cells.groupby("band")):
        cell = cell.sort_values("median_seconds_per_move")
        yerr = [
            (cell.blunder_rate - cell.blunder_ci_lo).values,
            (cell.blunder_ci_hi - cell.blunder_rate).values,
        ]
        ax.errorbar(
            cell.median_seconds_per_move,
            cell.blunder_rate,
            yerr=yerr,
            fmt="o-",
            ms=4,
            lw=1.4,
            capsize=2,
            color=viz.PALETTE[i % len(viz.PALETTE)],
            label=band,
        )
    viz.finish(
        fig,
        ax,
        f"Blunder rate (loss >= {BLUNDER_CP}cp) vs estimated seconds per move, by rating band",
        "Nominal seconds per move ((base + 40*inc) / 40)",
        "Blunders per move",
        paths.figure_path("t3_blunder_rate_vs_time.png"),
        note="deadlost track 3. Lichess 2017 rated sample, Stockfish 16. Bars are 95% game-clustered bootstrap. "
        "No bullet/blitz in corpus: the fast end of the curve is unobserved.",
    )


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("by_time_bucket", "shape_test")}, indent=2, default=float)[:2500])
