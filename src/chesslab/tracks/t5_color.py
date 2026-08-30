"""Track 5: does White actually score better, and is the edge shrinking?

QUESTION. Does playing White confer a measurable score advantage, does it
differ across rating bands, and has it moved over 1998-2026?

WHY THE REPORTING IS SPLIT. "White's advantage is shrinking" and "chess is
getting drawier" produce the same headline number if you only track White's
score. A draw costs White half a point exactly as a rise in Black wins does.
So every result below is reported three ways:

  white_score          = P(white win) + 0.5 * P(draw)
  draw_rate            = P(draw)
  white_share_decisive = P(white win | decisive result)

Only the third one is a statement about who is winning games. If
`white_score` falls while `white_share_decisive` holds flat, the story is
draws, not Black's improvement.

CLUSTERING. Elite tournament chess is a small world: a few thousand players
generate all of TWIC, and strong players appear hundreds of times. Confidence
intervals here resample *players*, not games.

Run:  python -m chesslab.tracks.t5_color
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import paths, stats, viz
from ..schema import band_order
from .t1_ingest import load_games

MIN_GAMES = 200
TWIC_BANDS = [(2200, 2400), (2400, 2500), (2500, 2600), (2600, 3200)]


def _outcome_frame(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["white_win"] = (d.result == "1-0").astype(float)
    d["draw"] = (d.result == "1/2-1/2").astype(float)
    d["white_score"] = d["white_win"] + 0.5 * d["draw"]
    d["decisive"] = 1.0 - d["draw"]
    return d


def _metrics(d: pd.DataFrame, cluster_col: str | None) -> dict:
    n = len(d)
    if n == 0:
        return {}
    out = {"n_games": int(n)}
    if cluster_col is None or cluster_col not in d:
        out["white_score"] = stats.wilson_ci(d.white_score.sum(), n).as_dict()
        out["draw_rate"] = stats.wilson_ci(d.draw.sum(), n).as_dict()
        dec = d[d.decisive == 1]
        out["white_share_decisive"] = stats.wilson_ci(dec.white_win.sum(), len(dec)).as_dict()
        return out

    clusters = d[cluster_col].fillna("__na__").values
    out["white_score"] = stats.cluster_bootstrap(d.white_score.values, clusters, np.mean).as_dict()
    out["draw_rate"] = stats.cluster_bootstrap(d.draw.values, clusters, np.mean).as_dict()
    dec = d[d.decisive == 1]
    if len(dec):
        out["white_share_decisive"] = stats.cluster_bootstrap(
            dec.white_win.values, dec[cluster_col].fillna("__na__").values, np.mean
        ).as_dict()
    return out


def lichess_by_band(games: pd.DataFrame) -> dict:
    """White's edge by rating band, online rapid/classical, 2017."""
    d = games[(games.source == "lichess2017") & (games.rated == True)]  # noqa: E712
    d = d[d.white_band == d.black_band]  # equal-strength pairings only
    d = _outcome_frame(d)
    res = {}
    for band in band_order():
        cell = d[d.white_band == band]
        if len(cell) >= MIN_GAMES:
            res[band] = _metrics(cell, cluster_col=None)
    return res


def twic_by_band(games: pd.DataFrame) -> dict:
    d = games[games.source == "twic"].dropna(subset=["white_elo", "black_elo"])
    d = d[(d.white_elo - d.black_elo).abs() <= 50]  # near-equal pairings
    d = _outcome_frame(d)
    res = {}
    for lo, hi in TWIC_BANDS:
        cell = d[d.white_elo.between(lo, hi - 1)]
        if len(cell) >= MIN_GAMES:
            res[f"{lo}-{hi}"] = _metrics(cell, cluster_col="white_id")
    return res


def twic_by_year(games: pd.DataFrame, elo_lo: int = 2200, elo_hi: int = 3199, min_games: int | None = None) -> pd.DataFrame:
    """Yearly outcome mix for near-equal TWIC pairings inside an Elo window.

    The window matters. TWIC's coverage broadened over the sample period, so
    the *unconditional* 2200+ pool drifts downward in average strength; any
    trend measured on it is partly a trend in who TWIC reports on. Passing a
    narrow window (2400-2500) holds the population roughly fixed and is the
    version this repo treats as the headline.
    """
    min_games = MIN_GAMES if min_games is None else min_games
    d = games[games.source == "twic"].dropna(subset=["white_elo", "black_elo", "year"])
    d = d[(d.white_elo - d.black_elo).abs() <= 50]
    d = d[d.white_elo.between(elo_lo, elo_hi) & d.black_elo.between(elo_lo, elo_hi)]
    d = _outcome_frame(d)
    rows = []
    for year, cell in d.groupby("year"):
        if len(cell) < min_games:
            continue
        dec = cell[cell.decisive == 1]
        rows.append(
            {
                "year": int(year),
                "n_games": len(cell),
                "white_score": cell.white_score.mean(),
                "draw_rate": cell.draw.mean(),
                "white_share_decisive": dec.white_win.mean() if len(dec) else np.nan,
                "mean_elo": cell[["white_elo", "black_elo"]].mean(axis=1).mean(),
            }
        )
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def run() -> dict:
    games = load_games()
    li = lichess_by_band(games)
    tw_band = twic_by_band(games)
    yearly = twic_by_year(games)
    yearly_fixed = twic_by_year(games, elo_lo=2400, elo_hi=2499, min_games=40)

    def _trends(tbl: pd.DataFrame) -> dict:
        out = {}
        for metric in ("white_score", "draw_rate", "white_share_decisive"):
            iv = stats.bootstrap_slope(tbl.year, tbl[metric], w=tbl.n_games)
            out[metric] = {
                "slope_per_year": iv.point,
                "ci_lo": iv.lo,
                "ci_hi": iv.hi,
                "slope_per_decade": iv.point * 10,
                "ci_lo_per_decade": iv.lo * 10,
                "ci_hi_per_decade": iv.hi * 10,
            }
        # Composition guard: if the sampled pool drifted in strength, a trend in
        # White's score could be a trend in who is playing, not in the advantage.
        elo_trend = stats.bootstrap_slope(tbl.year, tbl.mean_elo, w=tbl.n_games)
        out["mean_elo_of_pool"] = {
            "slope_per_decade": elo_trend.point * 10,
            "ci_lo": elo_trend.lo * 10,
            "ci_hi": elo_trend.hi * 10,
        }
        return out

    trends = _trends(yearly)
    trends_fixed = _trends(yearly_fixed)

    out = {
        "lichess2017_by_rating_band": li,
        "twic_by_elo_band": tw_band,
        "twic_yearly": yearly.to_dict(orient="records"),
        "twic_yearly_fixed_band_2400_2499": yearly_fixed.to_dict(orient="records"),
        "twic_time_trends": trends,
        "twic_time_trends_fixed_band_2400_2499": trends_fixed,
        "headline": {
            "basis": "TWIC, both players 2400-2499, pairings within 50 Elo",
            "white_score_slope_per_decade": trends_fixed["white_score"]["slope_per_decade"],
            "draw_rate_slope_per_decade": trends_fixed["draw_rate"]["slope_per_decade"],
            "white_share_decisive_slope_per_decade": trends_fixed["white_share_decisive"]["slope_per_decade"],
        },
        "notes": [
            "Lichess cells are restricted to games where both players sit in the same rating band; "
            "TWIC cells to pairings within 50 Elo. An unrestricted white-score number mostly measures "
            "who got paired with whom.",
            "TWIC intervals resample players; lichess intervals are Wilson at game level because the "
            "corpus is a 20k scrape with little player repetition.",
        ],
    }
    (paths.RESULTS / "t5_color.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(yearly, li)
    return out


def _figure(yearly: pd.DataFrame, li: dict) -> None:
    fig, ax = viz.new_fig(8.5, 5.0)
    ax.plot(yearly.year, yearly.white_score, "o-", color=viz.PALETTE[0], lw=1.6, ms=4, label="White score (W + ½D)")
    ax.plot(yearly.year, yearly.white_share_decisive, "s-", color=viz.PALETTE[1], lw=1.6, ms=4, label="White share of decisive games")
    ax.plot(yearly.year, yearly.draw_rate, "^-", color=viz.PALETTE[2], lw=1.4, ms=4, label="Draw rate")
    ax.axhline(0.5, color="#888888", lw=0.8, ls="--")
    ax.set_ylim(0.3, 0.75)
    viz.finish(
        fig,
        ax,
        "White's edge over time, TWIC tournament games (pairings within 50 Elo, both 2200+)",
        "Year",
        "Proportion",
        paths.figure_path("t5_white_advantage_by_year.png"),
        note="chess-lab track 5. Sampled TWIC issues, ~2 per year. Dashed line is parity.",
    )

    if li:
        fig, ax = viz.new_fig(7.5, 4.5)
        bands = list(li)
        pts = [li[b]["white_score"]["point"] for b in bands]
        lo = [li[b]["white_score"]["point"] - li[b]["white_score"]["ci_lo"] for b in bands]
        hi = [li[b]["white_score"]["ci_hi"] - li[b]["white_score"]["point"] for b in bands]
        ax.errorbar(range(len(bands)), pts, yerr=[lo, hi], fmt="o", color=viz.PALETTE[0], capsize=3)
        ax.axhline(0.5, color="#888888", lw=0.8, ls="--")
        ax.set_xticks(range(len(bands)))
        ax.set_xticklabels(bands, rotation=30, ha="right")
        viz.finish(
            fig,
            ax,
            "White's score by rating band, lichess 2017 (both players in band)",
            "Rating band",
            "White score (W + ½D)",
            paths.figure_path("t5_white_advantage_by_band.png"),
            note="chess-lab track 5. Wilson 95% intervals.",
            legend=False,
        )


if __name__ == "__main__":
    r = run()
    print(json.dumps(r["twic_time_trends"], indent=2))
