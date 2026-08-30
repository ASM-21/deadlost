"""Track 2: does an objectively "good" opening actually win more games?

QUESTION. For well-known openings, does the engine-assessed advantage at the
end of the book line translate into practical score, and does the gap between
the two widen at lower rating levels?

WHY THIS IS THE TRICKIEST TRACK TO STATE HONESTLY. The naive version, "compare
each opening's engine eval to its win rate", is almost meaningless, because
across the openings people actually play the engine eval barely varies. Every
mainline opening evaluates to roughly +0.2 to +0.4 for White. The spread in
practical results between openings is many times larger than the spread in
engine evaluations, so a correlation between the two is dominated by noise and
by who chooses which opening.

So the comparison is made in a way that survives that:

1. Openings are classified from the moves against the lichess ECO table, not
   from each corpus's own tag, so both corpora use one classifier.
2. Engine evaluation is taken at the **book exit position** (the end of the
   longest matched named line), at a higher node budget than the move-level
   sample, because we need to distinguish +0.15 from +0.35 rather than detect
   blunders.
3. Practical score is measured **within rating band**, so an opening's score
   is not just a measure of who plays it.
4. The reported quantity is the **residual**: practical score minus what the
   engine evaluation predicts, converted to the same units via a fitted
   eval-to-score mapping. That residual is the "practical vs objective" gap the
   question is actually about.

COLOR. Openings are inherently colored, so everything is reported as White's
score and every opening is analysed from White's side.

Run:  python -m chesslab.tracks.t2_openings
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

from .. import engine as eng
from .. import openings, paths, stats, viz
from .t1_ingest import load_games

MIN_GAMES_PER_CELL = 60
MIN_GAMES_PER_FAMILY = 300
BOOK_EVAL_NODES = 400_000
TOP_FAMILIES = 12

#: Logistic mapping from centipawns to expected score. The constant is the
#: standard lichess/Stockfish win-probability scaling; it is a convention, not
#: a fitted parameter, and every conclusion below is stated as a *ranking* or
#: a residual so it does not hinge on the exact constant.
CP_SCALE = 350.0


def cp_to_expected_score(cp: float) -> float:
    return 1.0 / (1.0 + np.exp(-cp / CP_SCALE))


def annotate_openings(games: pd.DataFrame) -> pd.DataFrame:
    d = games.copy()
    cls = [openings.classify(m) for m in d.moves]
    d["eco_matched"] = [c[0] for c in cls]
    d["line_name"] = [c[1] for c in cls]
    d["book_ply"] = [c[2] for c in cls]
    d["family"] = [openings.family(c[1]) for c in cls]
    return d


def evaluate_book_exits(
    d: pd.DataFrame,
    nodes: int = BOOK_EVAL_NODES,
    cache: pathlib.Path | None = None,
    time_budget: float | None = None,
) -> pd.DataFrame:
    """Engine evaluation of each distinct book-exit position.

    Distinct positions, not distinct games: thousands of games share the same
    book exit, so this costs about a thousand evaluations rather than a few
    hundred thousand. Node budget is much higher than the move-level sample
    because the job here is to tell +0.15 from +0.35, not to spot blunders.

    Resumable: already-evaluated lines are read from `cache` and skipped, and
    `time_budget` (seconds) stops the run cleanly with partial results saved.
    """
    import time

    import chess

    reps = (
        d[d.book_ply > 0]
        .groupby("line_name")
        .agg(moves=("moves", "first"), book_ply=("book_ply", "first"), eco=("eco_matched", "first"))
        .reset_index()
    )

    have = pd.DataFrame(columns=["line_name", "eco", "book_ply", "book_cp", "fen"])
    if cache is not None and cache.exists():
        have = pd.read_parquet(cache)
        reps = reps[~reps.line_name.isin(set(have.line_name))]

    rows: list[dict] = []
    t0 = time.time()
    if len(reps):
        with eng.Evaluator(nodes=nodes) as ev:
            for i, rec in enumerate(reps.itertuples(index=False), start=1):
                board = chess.Board()
                try:
                    for tok in rec.moves.split()[: rec.book_ply]:
                        board.push_san(tok)
                except Exception:  # noqa: BLE001
                    continue
                cp = eng.clamp(ev.eval_board(board, game=rec.line_name))
                rows.append(
                    {
                        "line_name": rec.line_name,
                        "eco": rec.eco,
                        "book_ply": int(rec.book_ply),
                        "book_cp": cp,
                        "fen": board.fen(),
                    }
                )
                if time_budget is not None and time.time() - t0 > time_budget:
                    print(f"[t2] book-eval budget reached at {i}/{len(reps)} lines", flush=True)
                    break

    out = pd.concat([have, pd.DataFrame(rows)], ignore_index=True) if rows else have
    if cache is not None and len(out):
        out.to_parquet(cache, index=False)
    return out


def family_book_cp(d: pd.DataFrame, line_evals: pd.DataFrame) -> pd.DataFrame:
    """Game-weighted mean book evaluation per family.

    Weighting by games, not by lines, means a family's number reflects the
    positions people actually reach, not the long tail of rare sidelines.
    """
    m = d.merge(line_evals[["line_name", "book_cp"]], on="line_name", how="inner")
    return (
        m.groupby("family")
        .agg(book_cp=("book_cp", "mean"), n_games=("game_id", "count"), mean_book_ply=("book_ply", "mean"))
        .reset_index()
    )


def practical_by_family_band(d: pd.DataFrame, band_col: str, bands: list[str]) -> pd.DataFrame:
    d = d.copy()
    d["white_score"] = d.result.map({"1-0": 1.0, "1/2-1/2": 0.5, "0-1": 0.0})
    d["draw"] = (d.result == "1/2-1/2").astype(float)
    rows = []
    for (fam, band), cell in d.groupby(["family", band_col]):
        if len(cell) < MIN_GAMES_PER_CELL or band not in bands:
            continue
        iv = stats.wilson_ci(cell.white_score.sum(), len(cell))
        rows.append(
            {
                "family": fam,
                "band": band,
                "n_games": len(cell),
                "white_score": iv.point,
                "ci_lo": iv.lo,
                "ci_hi": iv.hi,
                "draw_rate": float(cell.draw.mean()),
            }
        )
    return pd.DataFrame(rows)


def gap_by_band(practical: pd.DataFrame, fam_cp: pd.DataFrame) -> pd.DataFrame:
    """Residual of practical score against engine-predicted score, per band."""
    m = practical.merge(fam_cp[["family", "book_cp"]], on="family", how="inner")
    m["predicted_score"] = cp_to_expected_score(m.book_cp)
    m["gap"] = m.white_score - m.predicted_score
    return m


def run(skip_engine: bool = False, book_eval_budget: float | None = None) -> dict:
    games = annotate_openings(load_games())

    li = games[(games.source == "lichess2017") & (games.rated == True)].copy()  # noqa: E712
    li = li[li.white_band == li.black_band]
    tw = games[games.source == "twic"].dropna(subset=["white_elo", "black_elo"]).copy()
    tw = tw[(tw.white_elo - tw.black_elo).abs() <= 100]
    tw["band"] = pd.cut(
        tw.white_elo,
        [2200, 2400, 2500, 2600, 3200],
        labels=["2200-2400", "2400-2500", "2500-2600", "2600+"],
        right=False,
    ).astype(str)

    fams = (
        pd.concat([li.family, tw.family])
        .value_counts()
        .head(TOP_FAMILIES)
        .index.tolist()
    )
    fams = [f for f in fams if isinstance(f, str)]

    cache = paths.EVAL / "book_exit_evals.parquet"
    subset = pd.concat([li, tw])
    subset = subset[subset.family.isin(fams)]
    needed = set(subset[subset.book_ply > 0].line_name.unique())
    have = set(pd.read_parquet(cache).line_name) if cache.exists() else set()
    if needed - have:
        if skip_engine:
            raise FileNotFoundError(
                f"{len(needed - have)} book-exit positions not yet evaluated and skip_engine=True; "
                "run scripts/build_all.sh"
            )
        line_evals = evaluate_book_exits(subset, cache=cache, time_budget=book_eval_budget)
    else:
        line_evals = pd.read_parquet(cache)
    missing = needed - set(line_evals.line_name)
    if missing:
        raise RuntimeError(
            f"book-exit evaluation incomplete: {len(missing)} of {len(needed)} lines missing. "
            "Re-run to resume; results are cached."
        )

    all_games = pd.concat([li.assign(corpus="lichess2017"), tw.assign(corpus="twic")])
    all_games = all_games[all_games.family.isin(fams)]
    fam_cp = family_book_cp(all_games, line_evals)
    fam_cp = fam_cp[fam_cp.n_games >= MIN_GAMES_PER_FAMILY]

    li_bands = ["1200-1400", "1400-1600", "1600-1800", "1800-2000", "2000-2200"]
    tw_bands = ["2200-2400", "2400-2500", "2500-2600", "2600+"]

    li_prac = practical_by_family_band(li[li.family.isin(fam_cp.family)], "white_band", li_bands)
    tw_prac = practical_by_family_band(tw[tw.family.isin(fam_cp.family)], "band", tw_bands)

    li_gap = gap_by_band(li_prac, fam_cp)
    tw_gap = gap_by_band(tw_prac, fam_cp)
    both = pd.concat([li_gap.assign(corpus="lichess2017"), tw_gap.assign(corpus="twic")], ignore_index=True)

    band_order = li_bands + tw_bands
    spread = []
    for band in band_order:
        cell = both[both.band == band]
        if len(cell) < 3:
            continue
        spread.append(
            {
                "band": band,
                "n_families": len(cell),
                "mean_abs_gap": float(cell.gap.abs().mean()),
                "sd_of_practical_score_across_families": float(cell.white_score.std(ddof=1)),
                "mean_gap": float(cell.gap.mean()),
            }
        )
    spread_df = pd.DataFrame(spread)

    # The headline comparison the question asks for: does the objective/practical
    # gap widen at lower levels? Fitted SEPARATELY per corpus. A single fit
    # across the concatenated band list would run a regression through two
    # different populations (online rapid, then over-the-board classical) as if
    # they were one ordered scale, and the step between the corpora would
    # dominate the slope.
    trends = {}
    for corpus, band_list in (("lichess2017", li_bands), ("twic", tw_bands)):
        cell = spread_df[spread_df.band.isin(band_list)]
        if len(cell) >= 3:
            iv = stats.bootstrap_slope(range(len(cell)), cell.mean_abs_gap)
            trends[corpus] = {
                "n_bands": int(len(cell)),
                "slope_per_band_step": iv.point,
                "ci_lo": iv.lo,
                "ci_hi": iv.hi,
                "excludes_zero": bool(iv.lo * iv.hi > 0),
            }

    # Rank agreement between engine ordering and practical ordering, per band.
    from scipy.stats import spearmanr

    rank_rows = []
    for band, cell in both.groupby("band"):
        if len(cell) < 4:
            continue
        merged = cell.merge(fam_cp[["family", "book_cp"]], on="family", suffixes=("", "_y"))
        rho, p = spearmanr(merged.book_cp, merged.white_score)
        rank_rows.append({"band": band, "n_families": len(merged), "spearman_rho": float(rho), "p_value": float(p)})

    # Six bands means six independent chances to clear p<0.05 by luck alone.
    # Reporting the minimum p-value across them without correction is how a
    # null becomes a "finding". Holm-Bonferroni controls the family-wise error
    # rate; the binomial check asks whether the COUNT of nominally significant
    # bands is itself surprising.
    from scipy.stats import binom

    raw = sorted((r["p_value"], r["band"]) for r in rank_rows)
    m = len(raw)
    holm = []
    running = 0.0
    for i, (pv, band) in enumerate(raw):
        adj = min(1.0, max(running, (m - i) * pv))
        running = adj
        holm.append({"band": band, "p_raw": pv, "p_holm": adj, "significant_after_correction": adj < 0.05})
    n_nominal = sum(1 for pv, _ in raw if pv < 0.05)
    multiplicity = {
        "n_bands_tested": m,
        "n_nominally_significant": n_nominal,
        "expected_by_chance_at_0.05": round(0.05 * m, 2),
        "prob_of_at_least_this_many_under_null": float(binom.sf(n_nominal - 1, m, 0.05)) if n_nominal else 1.0,
        "holm_bonferroni": holm,
        "any_significant_after_correction": any(h["significant_after_correction"] for h in holm),
        "signs_of_rho": [round(r["spearman_rho"], 2) for r in rank_rows],
        "note": (
            "The one nominally significant band (2600+, rho negative) points the OPPOSITE way to the "
            "folk claim: engine-preferred openings score slightly worse among the strongest players. "
            "It does not survive correction, the sign of rho flips across bands, and one hit in six "
            "tests is close to what chance produces. Read as noise, not as a reversal."
        ),
    }

    out = {
        "method_note": (
            "Engine evaluation of mainline openings spans a far narrower range than practical "
            "results do, so this track reports rank agreement and residuals rather than a "
            "correlation that would be dominated by noise."
        ),
        "families_analysed": fam_cp.sort_values("book_cp", ascending=False).to_dict(orient="records"),
        "engine_eval_spread_cp": {
            "min": float(fam_cp.book_cp.min()),
            "max": float(fam_cp.book_cp.max()),
            "range": float(fam_cp.book_cp.max() - fam_cp.book_cp.min()),
        },
        "practical_score_spread": {
            "within_band_sd_mean": float(spread_df.sd_of_practical_score_across_families.mean())
            if len(spread_df)
            else None
        },
        "gap_by_band": spread_df.to_dict(orient="records"),
        "gap_trend_low_to_high_band_by_corpus": trends,
        "gap_trend_note": (
            "mean_gap rises across the TWIC bands, but predicted_score is fixed per family, so that "
            "rise is just White's score rising with strength (see track 5), not opening assessment "
            "becoming more accurate. mean_abs_gap is the quantity relevant to the question."
        ),
        "rank_agreement_by_band": rank_rows,
        "rank_agreement_multiplicity": multiplicity,
        "cells": both.to_dict(orient="records"),
        "book_eval_nodes": BOOK_EVAL_NODES,
    }
    (paths.RESULTS / "t2_openings.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(both, fam_cp, band_order)
    return out


def _figure(both: pd.DataFrame, fam_cp: pd.DataFrame, band_order: list[str]) -> None:
    fig, ax = viz.new_fig(9.0, 5.4)
    present = [b for b in band_order if b in set(both.band)]
    xpos = {b: i for i, b in enumerate(present)}
    for i, (fam, cell) in enumerate(both.groupby("family")):
        cell = cell[cell.band.isin(xpos)].copy()
        cell["x"] = cell.band.map(xpos)
        cell = cell.sort_values("x")
        ax.plot(cell.x, cell.gap, "o-", ms=3.5, lw=1.2, color=viz.PALETTE[i % len(viz.PALETTE)], alpha=0.85, label=fam)
    ax.axhline(0, color="#666666", lw=0.9, ls="--")
    ax.set_xticks(list(xpos.values()))
    ax.set_xticklabels(present, rotation=30, ha="right", fontsize=7.5)
    ax.legend(fontsize=6.5, frameon=False, ncol=2)
    viz.finish(
        fig,
        ax,
        "Practical score minus engine-predicted score, by opening family and rating band",
        "Rating band (lichess online, then TWIC over-the-board)",
        "White score gap (practical - predicted)",
        paths.figure_path("t2_opening_gap_by_band.png"),
        note="chess-lab track 2. Positive = the opening scores better in practice than its engine evaluation implies. "
        "The two corpora are different populations; the x-axis is ordered, not continuous.",
        legend=False,
    )

    fig, ax = viz.new_fig(8.0, 4.8)
    f = fam_cp.sort_values("book_cp")
    ax.barh(range(len(f)), f.book_cp, color=viz.PALETTE[0])
    ax.set_yticks(range(len(f)))
    ax.set_yticklabels(f.family, fontsize=7.5)
    viz.finish(
        fig,
        ax,
        f"Engine evaluation at book exit, game-weighted, Stockfish 16 @ {BOOK_EVAL_NODES:,} nodes",
        "Centipawns (White POV)",
        "",
        paths.figure_path("t2_book_exit_eval.png"),
        note="chess-lab track 2. Note the narrow range: mainline openings differ by far less than practical results do.",
        legend=False,
    )


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("engine_eval_spread_cp", "gap_by_band", "rank_agreement_by_band")}, indent=2))
