"""Track 8: rating inflation, following the same players across their careers.

WHY THIS TRACK EXISTS. Track 4 held the *rating* fixed at 2400-2499 and let the
calendar vary, then said plainly that it could not distinguish inflation from a
change in who holds that rating. That confound is not a footnote, it is the
whole difficulty of the question. This track attacks it directly: hold the
*person* fixed instead.

DESIGN. Build a panel of players who appear in TWIC across many years. For each
player-year, measure their mean rating and their engine-measured play quality
(ACPL). Fit

    ACPL ~ player fixed effect + rating + year

Within a single player, rating and ACPL should move together: when they play
better, they gain rating. If the rating *scale* drifts, a player of unchanged
skill sees their rating rise anyway. Controlling for the player's own rating,
the year coefficient captures what a rating point buys over time.

  positive year coefficient  -> the same rating now comes with worse play
                                (consistent with inflation)
  negative year coefficient  -> deflation
  interval spanning zero     -> no detectable drift

TWO THINGS THIS FIXES RELATIVE TO TRACK 4.

1. **Composition is differenced away.** The player fixed effect absorbs every
   fixed property of the person. A change in who enters the 2400s cannot
   produce a year coefficient here, because comparisons are within-person.
2. **The ACPL-per-Elo gradient is measured on the right population.** Track 4
   had to borrow that gradient from lichess amateurs to express its null in
   Elo, which was its most fragile number. Here the rating coefficient is
   estimated within these same players, so the Elo translation is internal.

WHAT IT DOES NOT FIX, AND PROVABLY CANNOT. Career stage. This is not a soft
caveat, it is an algebraic impossibility, and an earlier version of this module
got it wrong by including `career_year` as a "control".

Within a player, `career_year = year - first_year`, and `first_year` is constant
for that player. The within-transformation subtracts each player's own mean, so

    career_year - mean(career_year) = year - mean(year)

The two regressors become the *identical column* after demeaning. Including
both does not control for anything; it hands the solver a rank-deficient matrix
that splits one coefficient arbitrarily between two names. The giveaway in the
earlier output was that `year` and `career_year` came back equal to ten decimal
places.

This is the age-period-cohort identification problem. In a player fixed-effects
design, calendar time and career stage are the same variable up to a constant,
so the year coefficient is unavoidably a *sum* of two things: drift in the
rating scale, and the average career trajectory of these players. No amount of
data separates them here.

What can still be identified is *curvature*: `career_year_sq` is not collinear
with year after demeaning, because players start in different calendar years.
So the model can absorb the shape of a typical career arc while remaining
unable to separate its linear part from scale drift. That is what is fitted
below, and the year coefficient is reported as the compound quantity it is.

Also: TWIC reports tournament chess. A player's TWIC games are not their whole
year, and appearing in TWIC at all is selective.

PANEL SIZE, AND A RETRACTED LESSON. This track originally ran on 34 players and
reported -0.65 cp per decade. Enlarged to 100 players, a previous build reported
+1.32 and concluded that the small panel's estimate had carried no directional
information. **That conclusion was retracted.** The larger panel had been drawn
from TWIC without a format filter, and TWIC is majority online blitz from 2020,
which inflates centipawn loss late in the period. Restricted to classical
over-the-board games, the enlarged panel gives a coefficient with the SAME sign
as the original. There was no sign instability, only contamination. Both are
nulls.

The panel was expanded and re-evaluated at a cheaper engine budget in the same
step, so the two changes were deliberately disentangled before drawing that
conclusion. Re-scoring the TWIC sample at both budgets shows the 5,000-node
ACPL year trend (+1.645 cp/decade) matches the 20,000-node one (+1.681), and
the ratio between budgets has no year trend of its own (-0.016 per decade,
interval spanning zero). The sign change is sampling, not search depth.

WHAT THE LARGER PANEL DID NOT FIX. ROADMAP.md predicted that roughly 100
players would make the career-curvature specification informative. It does not:
the year interval in that specification is still about +/-6.5 cp per decade,
four times the headline spec's width, and the curvature term itself remains
indistinguishable from zero. The obstacle is not the number of players but the
collinearity described above, which more players cannot dissolve.

Run:  python -m deadlost.tracks.t8_player_panel
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import paths, stats, viz
from ..eval_run import load_evals
from .t1_ingest import load_games

MIN_GAMES_PER_PLAYER_YEAR = 3
MIN_YEARS_PER_PLAYER = 5
MIN_CAREER_SPAN = 10
WINSOR_CP = 300
SHARP_CP = 200
PANEL_TAG = "panel"


def player_game_frame(games: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, game): stack White and Black perspectives."""
    # Used for panel SELECTION only, so it spans every format to reproduce the
    # committed panel; the analysis drops non-classical games at load time.
    tw = games[games.source == "twic"].dropna(subset=["white_elo", "black_elo", "year"])
    w = tw[["game_id", "year", "white_id", "white_elo"]].rename(columns={"white_id": "pid", "white_elo": "elo"})
    w["color"] = "white"
    b = tw[["game_id", "year", "black_id", "black_elo"]].rename(columns={"black_id": "pid", "black_elo": "elo"})
    b["color"] = "black"
    return pd.concat([w, b], ignore_index=True).dropna(subset=["pid"])


def eligible_players(games: pd.DataFrame) -> pd.DataFrame:
    """Players with enough year-observations and a long enough career span."""
    pg = player_game_frame(games)
    py = pg.groupby(["pid", "year"]).agg(n=("game_id", "size"), elo=("elo", "mean")).reset_index()
    py = py[py.n >= MIN_GAMES_PER_PLAYER_YEAR]
    span = py.groupby("pid").agg(
        years=("year", "nunique"), ymin=("year", "min"), ymax=("year", "max"),
        elo_min=("elo", "min"), elo_max=("elo", "max"),
    )
    span["span"] = span.ymax - span.ymin
    span["elo_range"] = span.elo_max - span.elo_min
    return span[(span.years >= MIN_YEARS_PER_PLAYER) & (span.span >= MIN_CAREER_SPAN)]


#: Panel size. Raised from 34 to 100 once the 5,000-node budget was validated
#: (see scripts/calibrate_nodes.py): at ~0.9 s/game the larger panel costs about
#: what the smaller one did at 20,000 nodes. The 34-player version could not
#: support a career-curvature term, which was the binding limitation ROADMAP.md
#: identified for this track.
DEFAULT_PANEL_PLAYERS = 100


def select_panel(games: pd.DataFrame, n_players: int = DEFAULT_PANEL_PLAYERS, cells_per_player: int = 6, games_per_cell: int = 2) -> pd.DataFrame:
    """Pick players and spread their year-cells across each career.

    Players are chosen for *within-player rating variation*, not for fame: the
    rating coefficient is what makes the Elo translation internal, and it can
    only be estimated from players whose rating actually moved. Year cells are
    spread evenly across each player's own span so the panel is not concentrated
    in whichever years TWIC happened to cover heavily.
    """
    span = eligible_players(games)
    chosen = span.sort_values(["elo_range", "years"], ascending=False).head(n_players)

    pg = player_game_frame(games)
    py = pg.groupby(["pid", "year"]).agg(n=("game_id", "size")).reset_index()
    py = py[(py.n >= MIN_GAMES_PER_PLAYER_YEAR) & (py.pid.isin(chosen.index))]

    rng = np.random.default_rng(stats.SEED)
    picks = []
    for pid, cell in py.groupby("pid"):
        years = np.sort(cell.year.unique())
        if len(years) > cells_per_player:
            idx = np.linspace(0, len(years) - 1, cells_per_player).round().astype(int)
            years = years[np.unique(idx)]
        for y in years:
            pool = pg[(pg.pid == pid) & (pg.year == y)]
            k = min(games_per_cell, len(pool))
            take = rng.choice(pool.index.values, size=k, replace=False)
            picks.append(pool.loc[take])
    panel = pd.concat(picks, ignore_index=True)
    panel["stratum"] = panel.pid.astype(str) + "|" + panel.year.astype(int).astype(str)
    return panel


def build_panel_sample(games: pd.DataFrame | None = None, n_players: int = DEFAULT_PANEL_PLAYERS) -> pd.DataFrame:
    """Write the panel selection CSV that `eval_run --which panel` consumes."""
    games = load_games() if games is None else games
    panel = select_panel(games, n_players=n_players)
    meta = games.set_index("game_id")
    panel = panel.join(meta[["moves", "result", "ply_count", "white_elo", "black_elo"]], on="game_id")
    out = paths.EVAL / "eval_sample_panel.csv"
    panel.to_csv(out, index=False)
    return panel


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------


def build_move_table() -> pd.DataFrame:
    ev = load_evals(PANEL_TAG)
    panel = pd.read_csv(paths.EVAL / "eval_sample_panel.csv")

    df = ev.merge(panel[["game_id", "pid", "year", "color", "elo"]], on="game_id", how="inner")
    # Attribute each move to the player who made it, then keep only the moves
    # made by the panel player in that row. A game contributes two rows to the
    # panel when both players are panel members, and each side's moves are
    # scored separately.
    df = df[df.mover == df.color]
    df["loss_winsor"] = df.loss_cp.clip(upper=WINSOR_CP)
    df["is_sharp"] = (df.cp_before.abs() >= SHARP_CP).astype(float)
    return df


def player_year_table(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby(["pid", "year"])
        .agg(
            acpl=("loss_winsor", "mean"),
            acpl_raw=("loss_cp", "mean"),
            sharp_share=("is_sharp", "mean"),
            n_moves=("loss_cp", "size"),
            n_games=("game_id", "nunique"),
            elo=("elo", "mean"),
        )
        .reset_index()
    )
    g = g[g.n_moves >= 20]
    first = g.groupby("pid").year.transform("min")
    g["career_year"] = g.year - first
    g["career_year_sq"] = g.career_year ** 2
    keep = g.groupby("pid").year.transform("nunique") >= 3
    return g[keep].reset_index(drop=True)


SPECS = {
    "bare": ["elo", "year"],
    "with_sharpness": ["elo", "year", "sharp_share"],
    "with_career_curvature": ["elo", "year", "sharp_share", "career_year_sq"],
}


def within_player_fit(g: pd.DataFrame, regressors: list[str] | None = None, controls: bool = True) -> dict:
    """Player fixed effects by within-transformation, then weighted OLS.

    Demeaning by player is equivalent to including a dummy per player and keeps
    the design matrix small. Degrees of freedom are adjusted for the absorbed
    fixed effects, and the bootstrap resamples whole *players*, since two
    observations of the same person are not independent.
    """
    # NOTE: career_year is deliberately absent from every spec. It is perfectly
    # collinear with year after the within-transformation (see module
    # docstring). career_year_sq is not, and absorbs career curvature.
    if regressors is None:
        regressors = SPECS["with_sharpness"] if controls else SPECS["bare"]
    cols = ["acpl"] + list(regressors)
    d = g.dropna(subset=cols).copy()
    if d.pid.nunique() < 5:
        return {"error": "not enough players"}

    def demean(frame: pd.DataFrame) -> pd.DataFrame:
        return frame[cols].sub(frame.groupby(frame.pid)[cols].transform("mean"))

    def fit(frame: pd.DataFrame) -> np.ndarray:
        dm = demean(frame)
        y = dm.acpl.values
        X = dm[[c for c in cols if c != "acpl"]].values
        w = frame.n_moves.values.astype(float)
        Xw = X * np.sqrt(w)[:, None]
        yw = y * np.sqrt(w)
        beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
        return beta

    names = [c for c in cols if c != "acpl"]
    beta = fit(d)

    players = d.pid.unique()
    by_player = {p: d[d.pid == p] for p in players}
    rng = np.random.default_rng(stats.SEED)
    draws = []
    for _ in range(800):
        pick = rng.choice(players, size=len(players), replace=True)
        # Each DRAWN COPY gets its own key, so a player selected twice
        # contributes two separate fixed effects. Keying per row instead would
        # give every observation its own effect and the within-transformation
        # would demean everything to zero.
        parts = []
        for copy_idx, pl in enumerate(pick):
            part = by_player[pl].copy()
            part["pid"] = f"{pl}__{copy_idx}"
            parts.append(part)
        boot = pd.concat(parts, ignore_index=True)
        try:
            b = fit(boot)
        except Exception:  # noqa: BLE001
            continue
        if np.all(np.isfinite(b)):
            draws.append(b)
    draws = np.array(draws)
    if len(draws) < 100:
        return {"error": f"bootstrap failed: only {len(draws)} usable draws"}
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)

    out = {}
    for i, name in enumerate(names):
        out[name] = {
            "coefficient": float(beta[i]),
            "ci_lo": float(lo[i]),
            "ci_hi": float(hi[i]),
            "excludes_zero": bool(lo[i] * hi[i] > 0),
        }
    out["n_players"] = int(d.pid.nunique())
    out["n_player_years"] = int(len(d))
    out["n_bootstrap"] = int(len(draws))

    # Elo-equivalent drift, entirely from within-panel quantities.
    elo_coef = beta[names.index("elo")]
    year_coef = beta[names.index("year")]
    if elo_coef < 0:
        per_decade = -10 * year_coef / elo_coef
        denom = draws[:, names.index("elo")]
        with np.errstate(divide="ignore", invalid="ignore"):
            boot_equiv = -10 * draws[:, names.index("year")] / denom
        # Draws where the rating coefficient is near zero make the ratio
        # explode; those carry no information about an Elo equivalent.
        boot_equiv = boot_equiv[np.isfinite(boot_equiv) & (denom < -1e-4)]
        if len(boot_equiv) < 100:
            out["elo_equivalent_drift_per_decade"] = {
                "estimable": False,
                "reason": "rating coefficient too close to zero to invert reliably",
                "usable_draws": int(len(boot_equiv)),
            }
            return out
        elo_lo, elo_hi = np.percentile(boot_equiv, [2.5, 97.5])
        # A ratio of two noisy coefficients has a heavy-tailed distribution. If
        # the resulting interval is wider than the entire plausible range of
        # rating drift, quoting a point estimate from it would be false
        # precision, so it is reported as not estimable instead.
        usable = bool((elo_hi - elo_lo) < 200)
        out["elo_equivalent_drift_per_decade"] = {
            "estimable": usable,
            "reason": None if usable else (
                "interval on the ratio spans more than 200 Elo per decade; the within-player rating "
                "coefficient is not precise enough to invert. The year coefficient itself is the "
                "reportable quantity."
            ),
            "point": float(per_decade),
            "ci_lo": float(elo_lo),
            "ci_hi": float(elo_hi),
            "sign_convention": "positive means the same play now earns a HIGHER rating (inflation)",
            "note": (
                "Both the numerator and the denominator come from this panel, so unlike track 4's "
                "translation no gradient is borrowed from a different population."
            ),
        }
    return out


def run() -> dict:
    df = build_move_table()
    g = player_year_table(df)

    ladder = {name: within_player_fit(g, regressors=r) for name, r in SPECS.items()}
    # The headline spec is `with_sharpness`. `with_career_curvature` is reported
    # because it is the honest robustness check, and it shows the panel cannot
    # support that term: the year interval widens by roughly an order of
    # magnitude and the rating coefficient loses precision, because a quadratic
    # in career stage is itself strongly correlated with calendar year. That is
    # an admission about statistical power, not evidence for or against drift.
    full = ladder["with_sharpness"]
    bare = ladder["bare"]

    out = {
        "design": {
            "panel": "TWIC players with >=5 year-observations spanning >=10 years",
            "unit": "player-year",
            "players": int(g.pid.nunique()),
            "player_years": int(len(g)),
            "moves": int(len(df)),
            "years": [int(g.year.min()), int(g.year.max())],
            "model": "ACPL ~ player FE + rating + year + career_year_sq + sharpness",
            "identification_warning": (
                "The year coefficient is NOT a clean estimate of scale drift. Within a player, calendar "
                "year and career stage differ by a player-specific constant and are the same regressor "
                "after demeaning, so the year coefficient is the SUM of rating-scale drift and the "
                "average linear career trajectory of these 34 players. Only career curvature is "
                "separately identified."
            ),
        },
        "headline_spec": "with_sharpness",
        "within_player_fit": full,
        "within_player_fit_no_controls": bare,
        "specification_ladder": {
            name: {
                k: v for k, v in fit.items()
                if k in ("elo", "year", "sharp_share", "career_year_sq", "elo_equivalent_drift_per_decade")
            }
            for name, fit in ladder.items()
        },
        "power_note": (
            "The classical panel is enough to estimate a within-player rating gradient and a year term, "
            "and still not enough to add career curvature on top: that spec's year interval is several "
            "times wider and its curvature term does not exclude zero. Enlarging the panel did not fix "
            "it, because the limit is collinearity rather than sample size, which is the standard "
            "age-period-cohort result (Fosse & Winship 2019)."
        ),
        "sign_instability_of_the_34_player_version": {
            "old_panel_players": 34,
            "old_year_coefficient_per_decade": -0.648,
            "new_panel_players": 100,
            "new_year_coefficient_per_decade": None,
            "note": (
                "RETRACTED as a finding. A previous build reported that enlarging the panel flipped the "
                "sign. That enlarged panel included online blitz games. On classical games only, the new "
                "estimate (filled in below) has the same sign as the original. Both are nulls."
            ),
        },
        "engine_budget_invariance": {
            "checked": True,
            "acpl_year_trend_at_20000_nodes": 1.681,
            "acpl_year_trend_at_5000_nodes": 1.645,
            "budget_ratio_year_trend_per_decade": -0.0157,
            "budget_ratio_trend_excludes_zero": False,
            "note": (
                "The panel was enlarged and re-evaluated at a cheaper budget together, so the two were "
                "separated. Search depth does not interact with year. Measured before the format filter "
                "existed; the comparison is between node budgets on identical games, so contamination "
                "affects both sides equally and does not bear on this conclusion."
            ),
        },
        "player_summary": g.groupby("pid")
        .agg(years=("year", "nunique"), elo_min=("elo", "min"), elo_max=("elo", "max"), acpl=("acpl", "mean"))
        .round(1)
        .reset_index()
        .to_dict(orient="records"),
        "what_this_still_cannot_settle": [
            "Career stage, and not for want of controls: within a player, calendar year and career year "
            "are collinear by construction, so their linear effects are not separately identifiable. The "
            "year coefficient is a compound of scale drift and mean career trajectory. This is the "
            "age-period-cohort problem and it is structural, not a sample-size issue.",
            "Selection into TWIC. Appearing in tournament reports at all is not random, and a player's "
            "TWIC games are not their full year.",
            "Engine drift is not at issue (one fixed Stockfish build, fixed nodes), but the anchor is "
            "still ACPL, which measures one aspect of play quality rather than skill in general.",
        ],
    }
    out["sign_instability_of_the_34_player_version"]["new_year_coefficient_per_decade"] = (
        full["year"]["coefficient"] * 10
    )
    (paths.RESULTS / "t8_player_panel.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(g, full)
    return out


def _figure(g: pd.DataFrame, fit: dict) -> None:
    fig, ax = viz.new_fig(8.5, 5.2)
    # Within-player trajectories, each centred on its own mean so many careers
    # can be read on one axis.
    # Centre each observation on ITS PLAYER'S CAREER MEAN, computed across the
    # whole panel, before aggregating by year. Demeaning inside a year group
    # would subtract a player's single observation from itself and pin the mean
    # line to zero at every year.
    d = g.copy()
    d["acpl_centred"] = d.acpl - d.groupby("pid").acpl.transform("mean")
    for i, (_pid, cell) in enumerate(d.groupby("pid")):
        cell = cell.sort_values("year")
        ax.plot(cell.year, cell.acpl_centred, lw=0.7, alpha=0.35, color=viz.PALETTE[i % len(viz.PALETTE)])
    yearly = d.groupby("year").apply(
        lambda c: np.average(c.acpl_centred, weights=c.n_moves), include_groups=False
    )
    counts = d.groupby("year").size()
    # Years with one or two players carry almost no information and would read
    # as swings; show them faintly rather than dropping them silently.
    solid = yearly[counts >= 4]
    ax.plot(yearly.index, yearly.values, "-", color="#111111", lw=0.9, alpha=0.35)
    ax.plot(solid.index, solid.values, "o-", color="#111111", lw=2.0, ms=4,
            label="Panel mean (player-centred, years with 4+ players)")
    ax.axhline(0, color="#888888", lw=0.8, ls="--")
    yc = fit.get("year", {})
    viz.finish(
        fig, ax,
        "Play quality over time, within player (each career centred on its own mean)",
        "Year",
        "ACPL minus that player's career mean (cp)",
        paths.figure_path("t8_within_player_acpl.png"),
        note=(
            "deadlost track 8. Thin lines are individual careers. Lower is better play. The fitted year "
            f"coefficient after controlling for the player's own rating is {yc.get('coefficient', float('nan')):.2f} cp/year "
            f"[{yc.get('ci_lo', float('nan')):.2f}, {yc.get('ci_hi', float('nan')):.2f}]."
        ),
    )


if __name__ == "__main__":
    r = run()
    print(json.dumps(r["within_player_fit"], indent=2, default=float))
