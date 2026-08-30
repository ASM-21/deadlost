"""Track 10: do the findings survive the analytic choices that produced them?

Every earlier track reports one specification. This track re-runs the main
estimands across every defensible combination of the judgement calls behind
them, and reports where the published number sits in that distribution.

Three estimands are audited, chosen because they are the claims most likely to
be cited:

  C1  the blunder-rate gradient across rating bands (track 3's strongest result)
  C2  the fast-versus-slow blunder difference (track 3's headline about time)
  C3  the ACPL drift at fixed nominal rating (track 4's null)

C3 audits the **unadjusted** yearly trend, not track 4's headline. Track 4
reports +0.69 cp/decade after controlling for game length and position
sharpness; the raw trend it also reports is +1.33 (winsorised), and that is
what the curve here spans. The gap between them is the controls doing real
work: sharpness rose measurably over the period and sharper positions generate
more centipawn loss, so part of the raw upward drift is a change in the kind of
chess being played rather than in the players.

For each, the decisions varied are the ones that were genuinely arbitrary. Note
what is *not* varied: anything fixed by the data rather than by preference. The
engine node budget cannot be varied here because it would require re-evaluating
every position, and the clamp cannot be lowered below what the stored
evaluations already had applied.

HOW TO READ THE OUTPUT. `share_same_sign_as_median` near 1.0 means the
direction of the finding does not depend on the choices. `headline_percentile_
in_curve` near 0.5 means the published specification was typical rather than
favourable. `variance_attribution` ranks which choice moved the answer most,
which is the actionable part: a decision that dominates the spread should have
been argued for rather than defaulted.

WHAT THIS CANNOT DO. Every specification uses the same games, so the estimates
are strongly correlated and their spread is not a confidence interval. This
audits robustness to choices, not sampling error. Track 7's probes and the
power report cover the other two failure modes.

Run:  python -m chesslab.tracks.t10_multiverse
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import multiverse as mv
from .. import paths, stats
from ..eval_run import load_evals
from .t1_ingest import load_games

# --------------------------------------------------------------------------
# shared data prep
# --------------------------------------------------------------------------


def _lichess_moves() -> pd.DataFrame:
    ev = load_evals("lichess")
    games = load_games()
    sample = pd.read_csv(paths.EVAL / "eval_sample_lichess.csv")
    meta = games.merge(sample[["game_id", "stratum"]], on="game_id", how="inner")
    keep = ["game_id", "stratum", "white_elo", "black_elo", "base_seconds", "increment_seconds", "ply_count"]
    df = ev.merge(meta[keep], on="game_id", how="inner")
    df["band_lo"] = df["stratum"].str.split("|").str[0]
    df["tc_bucket"] = df["stratum"].str.split("|").str[1]
    df["est_total_seconds"] = df.base_seconds.fillna(0) + 40 * df.increment_seconds.fillna(0)
    df["mover_elo"] = np.where(df.mover == "white", df.white_elo, df.black_elo)
    return df


def _twic_moves() -> pd.DataFrame:
    ev = load_evals("twic")
    games = load_games()
    sample = pd.read_csv(paths.EVAL / "eval_sample_twic.csv")
    meta = games.merge(sample[["game_id", "stratum"]], on="game_id", how="inner")
    keep = ["game_id", "year", "white_elo", "black_elo", "ply_count"]
    df = ev.merge(meta[keep], on="game_id", how="inner")
    return df


def _apply_common(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Filters shared by every estimand."""
    d = df[df.ply >= spec["skip_ply"]]
    if spec.get("max_ply_cap"):  # 0 means no cap
        d = d[d.ply < spec["max_ply_cap"]]
    counts = d.groupby("game_id").ply.size()
    keep = counts[counts >= spec["min_moves_per_game"]].index
    return d[d.game_id.isin(keep)]


# --------------------------------------------------------------------------
# C1: blunder gradient across rating bands
# --------------------------------------------------------------------------

C1_DECISIONS = [
    mv.Decision("blunder_cp", [100, 150, 200, 300, 500],
                "Where a mistake becomes a blunder. No principled cutoff exists."),
    mv.Decision("skip_ply", [8, 12, 16, 20],
                "How many opening plies count as book and are excluded."),
    mv.Decision("min_moves_per_game", [10, 20, 30],
                "Shortest game admitted; short games give noisy per-game rates."),
    mv.Decision("max_ply_cap", [0, 80, 120],
                "Whether to truncate long endgames (0 means no cap)."),
]


def c1_estimator(moves: pd.DataFrame):
    def est(spec: dict):
        d = _apply_common(moves, spec)
        if d.empty:
            return None
        d = d.assign(hit=(d.loss_cp >= spec["blunder_cp"]).astype(float))
        by = d.groupby("band_lo").agg(rate=("hit", "mean"), n=("hit", "size"))
        if len(by) < 4:
            return None
        xs = np.arange(len(by))
        return stats.ols_slope(xs, by.rate.values, by.n.values)[0]

    return est


# --------------------------------------------------------------------------
# C2: fast vs slow difference
# --------------------------------------------------------------------------

C2_DECISIONS = [
    mv.Decision("blunder_cp", [100, 150, 200, 300, 500], "Blunder threshold."),
    mv.Decision("skip_ply", [8, 12, 16, 20], "Book plies excluded."),
    mv.Decision("min_moves_per_game", [10, 20, 30], "Shortest game admitted."),
    mv.Decision("split_seconds", [600, 750, 900],
                "Where 'fast' ends and 'slow' begins on estimated total seconds."),
]


def c2_estimator(moves: pd.DataFrame):
    def est(spec: dict):
        d = _apply_common(moves, {**spec, "max_ply_cap": 0})
        if d.empty:
            return None
        d = d.assign(hit=(d.loss_cp >= spec["blunder_cp"]).astype(float))
        fast = d[d.est_total_seconds < spec["split_seconds"]]
        slow = d[d.est_total_seconds >= spec["split_seconds"]]
        if len(fast) < 200 or len(slow) < 200:
            return None
        return float(fast.hit.mean() - slow.hit.mean())

    return est


# --------------------------------------------------------------------------
# C3: ACPL drift at fixed nominal rating
# --------------------------------------------------------------------------

C3_DECISIONS = [
    mv.Decision("winsor_cp", [200, 300, 500, 1500],
                "Cap on a single move's loss, to stop one collapse dominating a game mean."),
    mv.Decision("skip_ply", [8, 12, 16, 20], "Book plies excluded."),
    mv.Decision("min_moves_per_game", [15, 25, 35], "Shortest game admitted."),
    mv.Decision("elo_window", ["2400-2499", "2380-2519", "2350-2549"],
                "Width of the fixed-rating window; wider admits more data but less 'fixed'."),
]


def c3_estimator(moves: pd.DataFrame):
    def est(spec: dict):
        lo, hi = (int(x) for x in spec["elo_window"].split("-"))
        d = moves[moves.white_elo.between(lo, hi) & moves.black_elo.between(lo, hi)]
        d = _apply_common(d, {**spec, "max_ply_cap": None})
        if d.empty:
            return None
        d = d.assign(loss=d.loss_cp.clip(upper=spec["winsor_cp"]))
        g = d.groupby("game_id").agg(acpl=("loss", "mean"), year=("year", "first"), n=("loss", "size"))
        yearly = g.groupby("year").agg(acpl=("acpl", "mean"), n=("n", "sum")).reset_index()
        yearly = yearly[yearly.n >= 100]
        if len(yearly) < 8:
            return None
        return stats.ols_slope(yearly.year, yearly.acpl, yearly.n)[0] * 10  # per decade

    return est


# --------------------------------------------------------------------------


def run() -> dict:
    li = _lichess_moves()
    tw = _twic_moves()

    c1 = mv.run_curve(
        C1_DECISIONS, c1_estimator(li),
        headline={"blunder_cp": 300, "skip_ply": 8, "min_moves_per_game": 10, "max_ply_cap": 0},
    )
    c2 = mv.run_curve(
        C2_DECISIONS, c2_estimator(li),
        headline={"blunder_cp": 300, "skip_ply": 8, "min_moves_per_game": 10, "split_seconds": 600},
    )
    c3 = mv.run_curve(
        C3_DECISIONS, c3_estimator(tw),
        headline={"winsor_cp": 300, "skip_ply": 8, "min_moves_per_game": 15, "elo_window": "2400-2499"},
    )

    def verdict(curve: dict, expect_negative: bool | None) -> str:
        if "error" in curve:
            return curve["error"]
        share = curve["share_same_sign_as_median"]
        pct = curve.get("headline_percentile_in_curve")
        parts = [f"{share:.0%} of {curve['n_estimated']} specifications share the median's sign"]
        if pct is not None:
            parts.append(f"the reported specification sits at the {pct:.0%} percentile of the curve")
        if expect_negative is not None:
            agree = 1 - curve["share_positive"] if expect_negative else curve["share_positive"]
            parts.append(f"{agree:.0%} point the direction the headline claims")
        return "; ".join(parts)

    out = {
        "what_this_audits": (
            "Robustness to arbitrary analytic choices, not sampling error. Specifications share the "
            "same games and are strongly correlated, so the spread is not a confidence interval."
        ),
        "sign_consistency_is_not_significance": (
            "C3's point estimate is positive in every specification, which is easy to misread. All "
            "144 specifications run on the same games, so agreeing with each other costs them nothing. "
            "Track 4's interval on this same unadjusted quantity is [-0.20, +2.85] and includes zero. "
            "The curve says the SIGN does not depend on arbitrary choices; it says nothing about "
            "whether the effect is distinguishable from noise."
        ),
        "C3_audits_the_unadjusted_trend": (
            "Track 4's headline (+0.69 cp/decade) controls for game length and position sharpness. "
            "This curve spans the raw trend (~+1.4), so it is not directly comparable. The difference "
            "is attributable to the controls: sharpness rose +0.033 per decade with an interval "
            "excluding zero, and sharper positions carry roughly +20cp of loss per unit."
        ),
        "C1_blunder_gradient_across_bands": {**c1, "verdict": verdict(c1, expect_negative=True)},
        "C2_fast_minus_slow_blunder_rate": {**c2, "verdict": verdict(c2, expect_negative=False)},
        "C3_acpl_drift_per_decade": {**c3, "verdict": verdict(c3, None)},
    }
    for key in list(out):
        if isinstance(out[key], dict) and "estimates" in out[key]:
            # Keep the file readable; the full grid stays available in the figure.
            out[key]["estimates"] = out[key]["estimates"][:0]
    (paths.RESULTS / "t10_multiverse.json").write_text(json.dumps(out, indent=2, default=float))

    mv.curve_figure(
        c1, C1_DECISIONS,
        "Specification curve: blunder-rate gradient across rating bands",
        "Slope per band step",
        paths.figure_path("t10_curve_blunder_gradient.png"),
        note="chess-lab track 10. Every defensible combination of four analytic choices. Negative means "
             "blunder rate falls as rating rises. Gold line is the specification reported in track 3.",
    )
    mv.curve_figure(
        c2, C2_DECISIONS,
        "Specification curve: fast-minus-slow blunder rate",
        "Difference in blunders per move",
        paths.figure_path("t10_curve_fast_vs_slow.png"),
        note="chess-lab track 10. Positive means faster games blunder more. Gold line is the "
             "specification reported in track 3.",
    )
    mv.curve_figure(
        c3, C3_DECISIONS,
        "Specification curve: ACPL drift at fixed nominal rating",
        "cp per decade",
        paths.figure_path("t10_curve_acpl_drift.png"),
        note="chess-lab track 10. Track 4 reports this as a null; the curve shows whether that null "
             "depends on the choices behind it. Gold line is the reported specification.",
    )
    return out


if __name__ == "__main__":
    r = run()
    for k, v in r.items():
        if isinstance(v, dict) and "verdict" in v:
            print(f"\n{k}")
            print(f"  median {v['median']:+.5g}  range [{v['min']:+.5g}, {v['max']:+.5g}]")
            print(f"  {v['verdict']}")
            print(f"  drivers: {json.dumps(v['variance_attribution']['shares_of_total_variance'])}")
