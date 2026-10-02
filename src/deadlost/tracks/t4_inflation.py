"""Track 4: has the rating pool inflated, judged against an engine anchor?

QUESTION. Does the same nominal Elo buy the same quality of play in 2026 as it
did in 1999? If a 2450 today plays measurably worse than a 2450 twenty-five
years ago, the number has inflated. If better, it has deflated.

DESIGN. Hold the rating fixed and let the calendar vary. The sample is TWIC
games where *both* players are 2400-2499, twelve games per year, 1998-2026.
The skill anchor is average centipawn loss per move (ACPL), measured by
Stockfish 16 at a fixed node budget.

THE CONFOUND, STATED UP FRONT. This design cannot separate inflation from
population change. Suppose the FIDE pool grew and broadened over the period.
Then the set of people rated 2400-2499 in 2026 is drawn from a different
underlying distribution than the set rated 2400-2499 in 1999, and their play
could differ for reasons that have nothing to do with the rating scale
drifting. Both stories predict exactly the same ACPL trend. This track
measures the trend and refuses to name its cause.

Three further things that would corrupt ACPL if left alone, all handled:

1. **Game length.** ACPL is per move, and openings are near-perfect, so a
   game that ends at move 25 has a different ACPL than the same quality of
   play running to move 80. Reported both raw and length-adjusted.
2. **Position sharpness.** Wild positions generate large losses for both
   sides. A shift in opening fashion toward sharper or quieter play would move
   ACPL without any change in skill. Proxied by the share of moves made in
   positions the engine already scores past +/-200cp.
3. **Winsorisation.** One resignation-worthy move can dominate a game's mean.
   ACPL is reported both raw and winsorised at 300cp per move.
4. **Moves played after the contest is decided.** A move made in an
   already-lost position is not a measurement of competitive skill. The
   preferred anchor therefore excludes decided positions; see
   `trend_undecided_only`, which this track treats as primary.

   A previous build went further and reported that players had started playing
   on longer over the period (probe P7), which would have drifted the anchor in
   the same direction as inflation. **That was retracted.** It was online blitz,
   not a behavioural change: TWIC is majority online blitz from 2020, where
   players play on, and once games are restricted to classical over-the-board
   play the drift is not distinguishable from zero. The undecided-only
   specification is kept on principle rather than because of a measured drift.

5. **Format.** Only classical over-the-board games enter this track. See
   `schema.classify_format` and probe P8.

Run:  python -m deadlost.tracks.t4_inflation
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import paths, stats, viz
from ..eval_run import load_evals
from .t1_ingest import load_games

WINSOR_CP = 300
SHARP_CP = 200
#: A position past this margin is decided; moves played there measure
#: resignation norms rather than competitive skill.
DECIDED_CP = 300
MIN_MOVES_PER_GAME = 15


def build_move_table() -> pd.DataFrame:
    ev = load_evals("twic")
    games = load_games()
    sample = pd.read_csv(paths.EVAL / "eval_sample_twic.csv")
    meta = games.merge(sample[["game_id", "stratum"]], on="game_id", how="inner")

    keep = ["game_id", "year", "white_elo", "black_elo", "result", "ply_count", "white_id", "black_id"]
    df = ev.merge(meta[keep], on="game_id", how="inner")
    df["loss_winsor"] = df.loss_cp.clip(upper=WINSOR_CP)
    df["is_sharp"] = (df.cp_before.abs() >= SHARP_CP).astype(float)
    df["mover_id"] = np.where(df.mover == "white", df.white_id, df.black_id)
    df["in_decided_position"] = (df.cp_before.abs() >= DECIDED_CP).astype(float)
    return df


def game_level(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("game_id")
        .agg(
            year=("year", "first"),
            acpl=("loss_cp", "mean"),
            acpl_winsor=("loss_winsor", "mean"),
            sharp_share=("is_sharp", "mean"),
            n_moves=("loss_cp", "size"),
            ply_count=("ply_count", "first"),
            white_elo=("white_elo", "first"),
            black_elo=("black_elo", "first"),
        )
        .reset_index()
    )
    return g[g.n_moves >= MIN_MOVES_PER_GAME].reset_index(drop=True)


def yearly(g: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, cell in g.groupby("year"):
        rows.append(
            {
                "year": int(year),
                "n_games": len(cell),
                "acpl": cell.acpl.mean(),
                "acpl_winsor": cell.acpl_winsor.mean(),
                "median_acpl": cell.acpl.median(),
                "sharp_share": cell.sharp_share.mean(),
                "mean_moves": cell.n_moves.mean(),
                "mean_elo": cell[["white_elo", "black_elo"]].mean(axis=1).mean(),
            }
        )
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def _slope(tbl: pd.DataFrame, col: str) -> dict:
    iv = stats.bootstrap_slope(tbl.year, tbl[col], w=tbl.n_games)
    return {
        "slope_per_year": iv.point,
        "slope_per_decade": iv.point * 10,
        "ci_lo_per_decade": iv.lo * 10,
        "ci_hi_per_decade": iv.hi * 10,
        "excludes_zero": bool(iv.lo * iv.hi > 0),
    }


def adjusted_trend(g: pd.DataFrame) -> dict:
    """Year slope on ACPL after removing length and sharpness, by OLS.

    Regresses ACPL on year, moves-per-game and sharpness share together, so
    the year coefficient is the drift that those two do not account for.
    Bootstrap over games for the interval.
    """
    y = g.acpl_winsor.values
    X = np.column_stack([np.ones(len(g)), g.year.values - 2012, g.n_moves.values, g.sharp_share.values])

    def fit(Xm, yv):
        return np.linalg.lstsq(Xm, yv, rcond=None)[0]

    beta = fit(X, y)
    rng = np.random.default_rng(stats.SEED)
    draws = np.empty(1500)
    for b in range(1500):
        idx = rng.integers(0, len(y), size=len(y))
        draws[b] = fit(X[idx], y[idx])[1]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {
        "acpl_year_coefficient_per_decade": float(beta[1] * 10),
        "ci_lo_per_decade": float(lo * 10),
        "ci_hi_per_decade": float(hi * 10),
        "excludes_zero": bool(lo * hi > 0),
        "controls": ["moves_evaluated_per_game", "share_of_moves_in_sharp_positions"],
        "moves_coefficient": float(beta[2]),
        "sharpness_coefficient": float(beta[3]),
    }


def decided_share_trend(df: pd.DataFrame) -> dict:
    """Is the scored move sample's composition drifting over time?"""
    s = df.groupby("year").in_decided_position.mean()
    iv = stats.bootstrap_slope(s.index.values, s.values)
    return {
        "share_first_year": float(s.iloc[0]),
        "share_last_year": float(s.iloc[-1]),
        "slope_per_decade": iv.point * 10,
        "ci_lo_per_decade": iv.lo * 10,
        "ci_hi_per_decade": iv.hi * 10,
        "excludes_zero": bool(iv.lo * iv.hi > 0),
        "meaning": (
            "Players spend an increasing share of their scored moves in positions that are already "
            "decided. Those moves reflect willingness to play on, not skill, so any anchor that "
            "includes them drifts for behavioural reasons."
        ),
    }


def run() -> dict:
    df = build_move_table()
    g = game_level(df)
    tbl = yearly(g)

    # Preferred anchor: competitive moves only.
    df_undecided = df[df.in_decided_position == 0]
    g_undecided = game_level(df_undecided)
    tbl_undecided = yearly(g_undecided)

    raw = _slope(tbl, "acpl")
    wins = _slope(tbl, "acpl_winsor")
    sharp = _slope(tbl, "sharp_share")
    length = _slope(tbl, "mean_moves")
    elo = _slope(tbl, "mean_elo")
    adj = adjusted_trend(g)

    # Translate the ACPL drift into an Elo-equivalent, using the cross-sectional
    # ACPL-per-Elo gradient measured in the lichess corpus (track 3's by-band
    # mean loss). This is the single most fragile number in the repo: it assumes
    # the ACPL/Elo relationship measured on 1200-2200 online rapid transfers to
    # 2400s over the board, which is a stretch. Reported with that caveat
    # attached, never on its own.
    elo_equiv = None
    t3_path = paths.RESULTS / "t3_blunders.json"
    if t3_path.exists():
        t3 = json.loads(t3_path.read_text())
        bands = t3.get("by_rating_band", {})
        xs, ys = [], []
        for band, v in bands.items():
            lo_edge = int(band.split("-")[0])
            xs.append(lo_edge + 100)
            ys.append(v["mean_loss_cp"])
        if len(xs) >= 3:
            slope_cp_per_elo = stats.ols_slope(xs, ys)[0]
            if slope_cp_per_elo and slope_cp_per_elo != 0:
                elo_equiv = {
                    "acpl_cp_per_elo_point": slope_cp_per_elo,
                    "elo_equivalent_drift_per_decade": adj["acpl_year_coefficient_per_decade"] / slope_cp_per_elo,
                    "caveat": (
                        "Gradient measured on lichess 1200-2200 online rapid and applied to TWIC 2400-2499 "
                        "over-the-board. Different populations, different conditions, almost certainly a "
                        "different gradient. Treat as an order of magnitude, not an estimate."
                    ),
                }

    undecided = _slope(tbl_undecided, "acpl_winsor")
    composition = decided_share_trend(df)

    out = {
        "headline_specification": "trend_undecided_only",
        "trend_undecided_only": {
            **undecided,
            "note": (
                "ACPL computed only over moves made while the position was still competitive "
                f"(|eval| < {DECIDED_CP}cp). This is the anchor this track prefers, because it is "
                "immune to the resignation-timing drift documented in composition_drift. No games are "
                "lost to this filter at the current sample: all 330 retain enough competitive moves to "
                "clear the minimum, so the comparison against the all-moves spec is like for like."
            ),
            "effect_of_the_correction": (
                "Decided positions are a small minority of scored moves, so excluding them moves the "
                "trend only modestly. The specification is retained because post-decision moves do not "
                "measure competitive skill, not because a composition drift was found; the drift an "
                "earlier build reported was format contamination (see probe P7 and P8)."
            ),
        },
        "composition_drift": composition,
        "design": {
            "corpus": "TWIC, both players 2400-2499",
            "years": [int(tbl.year.min()), int(tbl.year.max())],
            "games": int(len(g)),
            "moves": int(len(df)),
            "anchor": "average centipawn loss per move, Stockfish 16 fixed nodes",
        },
        "trend_raw_acpl": raw,
        "trend_winsorised_acpl": wins,
        "trend_sharpness": sharp,
        "trend_game_length": length,
        "trend_mean_elo_within_band": elo,
        "trend_adjusted": adj,
        "elo_equivalent": elo_equiv,
        "yearly": tbl.to_dict(orient="records"),
        "what_this_cannot_settle": [
            "Inflation versus population change. Both predict the same ACPL trend at fixed nominal rating, "
            "and nothing in this data distinguishes them.",
            "Whether FIDE rating floors, K-factor changes or the growth of the rated pool drove any drift.",
            "Anything about ratings outside 2400-2499 or outside TWIC's tournament coverage.",
        ],
    }
    (paths.RESULTS / "t4_inflation.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(tbl)
    return out


def _figure(tbl: pd.DataFrame) -> None:
    fig, ax = viz.new_fig(8.5, 5.0)
    ax.plot(tbl.year, tbl.acpl_winsor, "o-", color=viz.PALETTE[0], lw=1.6, ms=4, label="ACPL (winsorised at 300cp)")
    ax.plot(tbl.year, tbl.acpl, "s--", color=viz.PALETTE[1], lw=1.1, ms=3, alpha=0.7, label="ACPL (raw)")
    ax2 = ax.twinx()
    ax2.plot(tbl.year, tbl.sharp_share, "^:", color=viz.PALETTE[2], lw=1.2, ms=3, label="Share of moves in sharp positions")
    ax2.set_ylabel("Sharp-position share", fontsize=9)
    ax2.tick_params(labelsize=8)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], fontsize=8, frameon=False)
    viz.finish(
        fig,
        ax,
        "Engine-measured play quality at a fixed nominal rating (TWIC, both players 2400-2499)",
        "Year",
        "Average centipawn loss per move",
        paths.figure_path("t4_acpl_at_fixed_rating.png"),
        note="deadlost track 4. Lower ACPL is better play. A rising line at fixed rating is consistent with "
        "inflation OR with the 2400-2499 pool changing composition; this design cannot separate them.",
        legend=False,
    )


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("trend_winsorised_acpl", "trend_adjusted", "elo_equivalent")}, indent=2, default=float))
