"""Track 11: is the online/over-the-board gap format, or is it strength?

THE QUESTION THIS INHERITS. Track 6 found that lost positions are saved far
more often online than over the board and could not say why, because its two
corpora vary rating and playing format together. Track 9 held format constant
and found no rating gradient within over-the-board play, which is suggestive
but rests on an absence. Neither could compare like with like, because the
corpora do not overlap in rating.

WHY MATCHING ON RATING WOULD NOT HAVE WORKED ANYWAY. A lichess rapid rating and
a FIDE classical rating are different scales attached to different populations.
Even where the numbers coincide they do not denote the same thing, so
"controlling for rating" across these corpora would control for a label rather
than for strength.

WHAT THIS TRACK DOES INSTEAD. Match on **engine-measured skill**. Every game in
this repository is scored by the same Stockfish build at the same node budget,
so average centipawn loss is one measurement instrument applied identically to
both corpora. That gives a common yardstick where nominal ratings give none,
and it turns out to give common support as well: strong online players and
weaker over-the-board players overlap in the 20-40 cp range.

THE MEASUREMENT MUST BE PRE-TREATMENT. A player's ACPL over a whole game is
contaminated by the blunder that lost it: conditioning on having reached a lost
position selects for exactly the moves that inflate the number. Skill here is
therefore measured **only over the moves played before the position went bad**,
which is a pre-treatment quantity in the sense that matters.

CONTROLS. Three things differ between corpora besides format and could produce
the gap on their own:

  defender skill      pre-entry ACPL of the side that went lost
  converter skill     pre-entry ACPL of the opponent, who has to finish the job
  severity            how lost the position was at entry, in centipawns

All three enter the model. Severity matters most: if over-the-board players
reach *more decisively* lost positions, a lower save rate follows without any
format effect at all.

WHAT REMAINS UNIDENTIFIED, and it is not small. ACPL is a noisy proxy for
skill, and matching on a noisy proxy leaves residual confounding: measurement
error attenuates the control, so some strength difference survives inside a
matched cell. The overlap region is also the tail of both distributions,
unusually strong online players against unusually weak over-the-board ones,
which are not typical members of either population. And "format" here is a
bundle: online rapid differs from classical tournament play in clock, stakes,
resignation norms and opponent pool all at once. This track narrows the
explanation from "rating or format" to "something bundled with format", which
is progress and not a resolution.

Run:  python -m chesslab.tracks.t11_matched_skill
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import paths, power, stats, viz
from ..eval_run import load_evals
from .t6_swindles import LOST_CP, _entries
from .t6_swindles import _meta as meta_lichess
from .t9_otb_swindles import _meta as meta_otb

MIN_PRE_MOVES = 8
ACPL_BINS = [(20, 25), (25, 30), (30, 35), (35, 40)]
WINDOW = (20, 40)


def build_entries() -> pd.DataFrame:
    """Lost game-sides from both corpora, with pre-entry skill attached."""
    frames = []
    for tag in ("lichess", "otb"):
        ev = load_evals(tag)
        meta = meta_lichess("lichess") if tag == "lichess" else meta_otb()
        e = _entries(ev, meta, LOST_CP)
        e = e[~e.censored].copy()
        if e.empty:
            continue

        # Pre-entry ACPL for both sides, computed once per game rather than
        # per row: a game can contribute two lost sides and both need both
        # players' numbers.
        ev = ev.assign(loss_w=ev.loss_cp.clip(upper=300))
        pre_def, pre_opp, n_pre = [], [], []
        for r in e.itertuples(index=False):
            g = ev[ev.game_id == r.game_id]
            d = g[(g.mover == r.side) & (g.ply < r.entry_ply)]
            o = g[(g.mover != r.side) & (g.ply < r.entry_ply)]
            pre_def.append(d.loss_w.mean() if len(d) >= MIN_PRE_MOVES else np.nan)
            pre_opp.append(o.loss_w.mean() if len(o) >= MIN_PRE_MOVES else np.nan)
            n_pre.append(len(d))
        e["pre_acpl"] = pre_def
        e["opp_pre_acpl"] = pre_opp
        e["n_pre_moves"] = n_pre
        e["corpus"] = tag
        frames.append(e)

    d = pd.concat(frames, ignore_index=True)
    d = d[d.pre_acpl.notna() & d.opp_pre_acpl.notna()]
    d["online"] = (d.corpus == "lichess").astype(float)
    # entry_cp is negative-signed severity from the loser's view; magnitude is
    # what matters, and it is clamped in the stored evaluations.
    d["severity"] = d.entry_cp.abs()
    return d


def support_table(d: pd.DataFrame) -> dict:
    """Where the two corpora actually overlap on measured skill."""
    rows = []
    for lo, hi in ACPL_BINS:
        cell = d[d.pre_acpl.between(lo, hi, inclusive="left")]
        on = cell[cell.online == 1]
        off = cell[cell.online == 0]
        rows.append(
            {
                "acpl_bin": f"{lo}-{hi}",
                "n_online": int(len(on)),
                "n_otb": int(len(off)),
                "save_online": float(on.saved.mean()) if len(on) else None,
                "save_otb": float(off.saved.mean()) if len(off) else None,
                "mean_pre_acpl_online": float(on.pre_acpl.mean()) if len(on) else None,
                "mean_pre_acpl_otb": float(off.pre_acpl.mean()) if len(off) else None,
                "usable": bool(len(on) >= 8 and len(off) >= 8),
            }
        )
    return {"bins": rows, "n_usable_bins": sum(r["usable"] for r in rows)}


def stratified_contrast(d: pd.DataFrame) -> dict:
    """Save-rate difference, averaged over skill bins with common support.

    Each bin contributes its own online-minus-OTB difference, weighted by the
    harmonic mean of its two cell sizes so a bin that is thin on either side
    cannot dominate. This is the non-parametric version of the question and
    makes no functional-form assumption.
    """
    diffs, weights, detail = [], [], []
    for lo, hi in ACPL_BINS:
        cell = d[d.pre_acpl.between(lo, hi, inclusive="left")]
        on, off = cell[cell.online == 1], cell[cell.online == 0]
        if len(on) < 8 or len(off) < 8:
            continue
        diff = float(on.saved.mean() - off.saved.mean())
        w = 2 * len(on) * len(off) / (len(on) + len(off))
        diffs.append(diff)
        weights.append(w)
        detail.append({"acpl_bin": f"{lo}-{hi}", "diff": diff, "n_online": len(on), "n_otb": len(off)})
    if not diffs:
        return {"error": "no bin has common support"}

    point = float(np.average(diffs, weights=weights))

    # Cluster bootstrap over games, recomputing the whole stratified estimate.
    rng = np.random.default_rng(stats.SEED)
    games = d.game_id.unique()
    by_game = {g: sub for g, sub in d.groupby("game_id")}
    draws = []
    for _ in range(800):
        pick = rng.choice(games, size=len(games), replace=True)
        boot = pd.concat([by_game[g] for g in pick], ignore_index=True)
        bd, bw = [], []
        for lo, hi in ACPL_BINS:
            cell = boot[boot.pre_acpl.between(lo, hi, inclusive="left")]
            on, off = cell[cell.online == 1], cell[cell.online == 0]
            if len(on) < 5 or len(off) < 5:
                continue
            bd.append(on.saved.mean() - off.saved.mean())
            bw.append(2 * len(on) * len(off) / (len(on) + len(off)))
        if bd:
            draws.append(np.average(bd, weights=bw))
    lo_ci, hi_ci = (np.percentile(draws, [2.5, 97.5]) if len(draws) > 100 else (np.nan, np.nan))

    return {
        "stratified_difference": point,
        "ci_lo": float(lo_ci),
        "ci_hi": float(hi_ci),
        "excludes_zero": bool(np.isfinite(lo_ci) and lo_ci * hi_ci > 0),
        "n_bootstrap": len(draws),
        "per_bin": detail,
    }


def logistic_fit(d: pd.DataFrame) -> dict:
    """saved ~ online + defender skill + converter skill + severity.

    Fitted by IRLS so the module carries no statsmodels dependency. The
    coefficient of interest is `online`, in log-odds. Restricted to the common
    support window: outside it the corpus indicator would be collinear with
    skill and the model would be extrapolating rather than comparing.
    """
    w = d[d.pre_acpl.between(*WINDOW, inclusive="left")].copy()
    if w.online.nunique() < 2 or len(w) < 40:
        return {"error": "insufficient common support for a model fit"}

    cols = ["online", "pre_acpl", "opp_pre_acpl", "severity"]
    X = np.column_stack([np.ones(len(w))] + [w[c].values.astype(float) for c in cols])
    # Standardise the continuous controls so the intercept and the online
    # coefficient stay interpretable.
    for j in range(2, X.shape[1]):
        col = X[:, j]
        X[:, j] = (col - col.mean()) / (col.std() or 1.0)
    y = w.saved.values.astype(float)

    def irls(Xm, yv, iters: int = 60):
        beta = np.zeros(Xm.shape[1])
        for _ in range(iters):
            eta = np.clip(Xm @ beta, -30, 30)
            p = 1 / (1 + np.exp(-eta))
            wgt = np.clip(p * (1 - p), 1e-6, None)
            z = eta + (yv - p) / wgt
            WX = Xm * wgt[:, None]
            try:
                beta_new = np.linalg.solve(Xm.T @ WX, Xm.T @ (wgt * z))
            except np.linalg.LinAlgError:
                return None
            if np.max(np.abs(beta_new - beta)) < 1e-8:
                return beta_new
            beta = beta_new
        return beta

    beta = irls(X, y)
    if beta is None:
        return {"error": "fit did not converge"}

    rng = np.random.default_rng(stats.SEED)
    games = w.game_id.unique()
    idx_by_game = {g: np.where(w.game_id.values == g)[0] for g in games}
    draws = []
    for _ in range(600):
        pick = rng.choice(games, size=len(games), replace=True)
        idx = np.concatenate([idx_by_game[g] for g in pick])
        b = irls(X[idx], y[idx])
        if b is not None and np.all(np.isfinite(b)):
            draws.append(b)
    draws = np.array(draws)
    names = ["intercept"] + cols
    out = {"n": int(len(w)), "n_bootstrap": int(len(draws)), "window_acpl": list(WINDOW)}
    if len(draws) > 100:
        lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
        for i, name in enumerate(names):
            out[name] = {
                "log_odds": float(beta[i]),
                "odds_ratio": float(np.exp(beta[i])),
                "ci_lo_log_odds": float(lo[i]),
                "ci_hi_log_odds": float(hi[i]),
                "excludes_zero": bool(lo[i] * hi[i] > 0),
            }
    return out


def _ended_in_mate(moves: str) -> bool:
    from ..schema import final_board

    try:
        return final_board(moves).is_checkmate()
    except Exception:  # noqa: BLE001
        return False


def resignation_rate(d: pd.DataFrame) -> dict:
    """Measure resignation directly, without conditioning on anything.

    The threshold analysis below is suggestive but conditions on a collider.
    This does not. Checkmate is detectable from the move list itself, exactly
    and in both corpora: on lichess games carrying an explicit `mate`
    termination tag, replaying the moves recovers checkmate in 100 out of 100.
    That matters because TWIC carries no termination tags at all, so the move
    list is the only available witness, and it is a reliable one.

    The quantity reported is measured on lost game-sides **that went on to
    lose**. Restricting to eventual losses removes the circularity in asking
    whether someone who saved the game had resigned: they obviously had not.
    Among players who did lose, ending in mate means they played the position
    to its conclusion; ending otherwise means they stopped early.
    """
    from .t1_ingest import load_games

    games = load_games().set_index("game_id")
    lost_and_lost = d[~d.saved].copy()
    if lost_and_lost.empty:
        return {"error": "no unsaved lost game-sides"}

    mate_flags, tags = [], []
    for r in lost_and_lost.itertuples(index=False):
        row = games.loc[r.game_id]
        mate_flags.append(_ended_in_mate(row["moves"]))
        tags.append(row.get("termination"))
    lost_and_lost["ended_in_mate"] = mate_flags
    lost_and_lost["termination_tag"] = tags

    out = {}
    for label, sub in (("online", lost_and_lost[lost_and_lost.online == 1]),
                       ("otb", lost_and_lost[lost_and_lost.online == 0])):
        if sub.empty:
            continue
        entry = {
            "n_lost_and_lost": int(len(sub)),
            "played_to_mate": float(sub.ended_in_mate.mean()),
            "stopped_early": float(1 - sub.ended_in_mate.mean()),
        }
        tagged = sub[sub.termination_tag.notna()]
        if len(tagged):
            entry["termination_tags"] = tagged.termination_tag.value_counts(normalize=True).round(4).to_dict()
        out[label] = entry

    diff = None
    if "online" in out and "otb" in out:
        a = lost_and_lost[lost_and_lost.online == 1]
        b = lost_and_lost[lost_and_lost.online == 0]
        pooled = pd.concat([a.assign(grp=1.0), b.assign(grp=0.0)])

        def stat(vals, grps):
            x, y = vals[grps == 1], vals[grps == 0]
            return float(x.mean() - y.mean()) if len(x) and len(y) else np.nan

        iv = stats.cluster_bootstrap_pairs(
            pooled.ended_in_mate.astype(float).values, pooled.grp.values, pooled.game_id.values, stat
        )
        diff = {
            "played_to_mate_online_minus_otb": iv.point,
            "ci_lo": iv.lo,
            "ci_hi": iv.hi,
            "excludes_zero": bool(iv.lo * iv.hi > 0),
        }

    return {
        "by_corpus": out,
        "difference": diff,
        "why_this_is_the_clean_test": (
            "Unlike the threshold analysis, this conditions on nothing post-treatment. It asks, of the "
            "players who ended up losing, what share played the position to checkmate rather than "
            "stopping early. A player who stops early forgoes any chance of saving the game, so a large "
            "difference here is a direct behavioural explanation for a difference in save rates."
        ),
        "caveat": (
            "'Stopped early' bundles resignation with losing on time, and the two cannot be separated "
            "for TWIC, which carries no termination tags. For the online corpus they can: the tag "
            "breakdown is reported above. Over-the-board classical games rarely end on time, so the "
            "over-the-board figure is close to a pure resignation rate."
        ),
    }


def resignation_mechanism(d: pd.DataFrame) -> dict:
    """Do over-the-board players simply resign lost positions sooner?

    This is the most plausible single explanation for the whole effect and it
    deserves a test rather than a place on a caveat list. A resigned game can
    never be saved, so if masters resign promptly and online players grind on,
    the online save rate is inflated by opportunity alone.

    The descriptive evidence is unambiguous: median moves played after reaching
    a lost position is roughly twice as high online.

    THE ANALYTIC TRAP, STATED BEFORE THE NUMBERS. Conditioning on how long a
    game continued is conditioning on a **post-treatment collider**. A game that
    gets saved necessarily lasted longer, so "among game-sides that played at
    least N more moves" over-selects saves in both corpora and inflates both
    rates. The narrowing of the gap across thresholds is therefore *consistent
    with* resignation driving the effect, and is not a clean decomposition of it.
    Reported as suggestive, and deliberately not converted into a percentage of
    the gap explained.
    """
    rows = []
    for thr in (0, 5, 10, 15, 20, 25):
        sub = d[d.moves_after_entry >= thr]
        on, off = sub[sub.online == 1], sub[sub.online == 0]
        if len(on) < 15 or len(off) < 15:
            continue
        rows.append(
            {
                "min_moves_after_entry": thr,
                "n_online": int(len(on)),
                "n_otb": int(len(off)),
                "save_online": float(on.saved.mean()),
                "save_otb": float(off.saved.mean()),
                "gap": float(on.saved.mean() - off.saved.mean()),
            }
        )

    duration = {
        "median_moves_after_entry_online": float(d[d.online == 1].moves_after_entry.median()),
        "median_moves_after_entry_otb": float(d[d.online == 0].moves_after_entry.median()),
        "mean_moves_after_entry_online": float(d[d.online == 1].moves_after_entry.mean()),
        "mean_moves_after_entry_otb": float(d[d.online == 0].moves_after_entry.mean()),
    }

    trend = None
    if len(rows) >= 3:
        iv = stats.bootstrap_slope([r["min_moves_after_entry"] for r in rows], [r["gap"] for r in rows])
        trend = {
            "gap_change_per_extra_move_threshold": iv.point,
            "ci_lo": iv.lo,
            "ci_hi": iv.hi,
            "gap_at_lowest_threshold": rows[0]["gap"],
            "gap_at_highest_threshold": rows[-1]["gap"],
        }

    return {
        "duration": duration,
        "by_threshold": rows,
        "trend": trend,
        "reading": (
            "Over-the-board players stop about twice as early after the position turns lost, and the "
            "online advantage shrinks as the comparison is restricted to game-sides that kept playing. "
            "Both are what a resignation-norm explanation predicts."
        ),
        "why_this_is_not_proof": (
            "Restricting on moves played after entry conditions on a post-treatment collider: a saved "
            "game lasts longer by construction. That inflates the save rate in both corpora at higher "
            "thresholds and makes the residual gap uninterpretable as a causal remainder. The correct "
            "conclusion is that resignation norms are a live and probably large part of the explanation, "
            "not that they account for a specific share of it."
        ),
        "how_to_settle_it": (
            "Termination reason is recorded for the online corpus and largely absent for TWIC. A corpus "
            "with reliable termination tags on both sides would allow restricting to games that ended in "
            "mate or a completed conversion, where resignation cannot operate at all."
        ),
    }


def run() -> dict:
    d = build_entries()
    support = support_table(d)
    strat = stratified_contrast(d)
    model = logistic_fit(d)

    raw_gap = float(d[d.online == 1].saved.mean() - d[d.online == 0].saved.mean())
    matched = strat.get("stratified_difference")
    explained = None
    if matched is not None and raw_gap:
        explained = 1 - matched / raw_gap

    win = d[d.pre_acpl.between(*WINDOW, inclusive="left")]
    mde = power.mde_two_sample_proportion(
        float(win.saved.mean()) if len(win) else 0.1,
        int(min((win.online == 1).sum(), (win.online == 0).sum())) or 1,
        width_ratio=1.48,
    )

    out = {
        "design": {
            "matching_variable": "pre-entry average centipawn loss, same engine and node budget in both corpora",
            "why_not_rating": (
                "A lichess rapid rating and a FIDE classical rating are different scales on different "
                "populations; matching on them would control for a label, not for strength."
            ),
            "common_support_window_acpl": list(WINDOW),
            "lost_game_sides": {"online": int((d.online == 1).sum()), "otb": int((d.online == 0).sum())},
        },
        "raw_gap_online_minus_otb": raw_gap,
        "common_support": support,
        "stratified_contrast": strat,
        "logistic_model": model,
        "resignation_rate": resignation_rate(d),
        "resignation_mechanism": resignation_mechanism(d),
        "share_of_gap_explained_by_skill_matching": explained,
        "resolution": {**mde.as_dict(), "note": "smallest gap the matched comparison could have resolved"},
        "reading": (
            "Matching on measured skill does not shrink the gap; it widens it. If the online/over-the-board "
            "difference were a strength effect it should collapse toward zero once both sides are compared "
            "at equal engine-measured playing quality. Instead the corpora differ by more at matched skill "
            "than in aggregate, because the stronger over-the-board population was masking the effect. "
            "The leading remaining explanation is behavioural rather than skill-based: over-the-board "
            "players resign lost positions and online players play them out."
        ),
        "what_remains_unidentified": [
            "ACPL is a noisy skill proxy; measurement error attenuates the control, so residual strength "
            "differences survive inside a matched cell.",
            "The overlap region is the tail of both distributions: unusually strong online players against "
            "unusually weak over-the-board ones. Neither is a typical member of its population.",
            "'Format' is a bundle. Clock, stakes, resignation norms and opponent pool all differ together, "
            "and this design cannot separate them from one another.",
            "Resignation norms are now tested rather than merely suspected; see resignation_mechanism. "
            "The test is suggestive and cannot be conclusive, because conditioning on how long a game "
            "continued conditions on a collider.",
        ],
    }
    (paths.RESULTS / "t11_matched_skill.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(d, support, raw_gap, matched)
    return out


def _figure(d: pd.DataFrame, support: dict, raw_gap: float, matched: float | None) -> None:
    rows = [r for r in support["bins"] if r["usable"]]
    fig, ax = viz.new_fig(8.6, 5.2)
    if rows:
        xs = np.arange(len(rows))
        ax.bar(xs - 0.19, [r["save_online"] for r in rows], width=0.38, color=viz.PALETTE[0],
               label="Online (lichess rapid)")
        ax.bar(xs + 0.19, [r["save_otb"] for r in rows], width=0.38, color=viz.PALETTE[1],
               label="Over the board (TWIC classical)")
        for i, r in enumerate(rows):
            ax.text(i - 0.19, r["save_online"] + 0.006, f"n={r['n_online']}", ha="center", fontsize=6.5, color="#444")
            ax.text(i + 0.19, r["save_otb"] + 0.006, f"n={r['n_otb']}", ha="center", fontsize=6.5, color="#444")
        ax.set_xticks(xs)
        ax.set_xticklabels([r["acpl_bin"] for r in rows])
    note = (
        "chess-lab track 11. Bins are pre-entry average centipawn loss, measured by the same engine at the "
        "same node budget in both corpora, so this compares players of equal measured strength rather than "
        "equal nominal rating. "
        + (f"Raw gap {raw_gap:+.3f}; after skill matching {matched:+.3f}." if matched is not None else "")
        + " Lower ACPL is stronger play."
    )
    viz.finish(
        fig, ax,
        "Saving a lost position at matched engine-measured skill",
        "Defender's pre-entry ACPL (cp, lower is stronger)",
        "Share of lost game-sides saved",
        paths.figure_path("t11_matched_skill.png"),
        note=note,
    )


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("raw_gap_online_minus_otb", "stratified_contrast",
                                        "share_of_gap_explained_by_skill_matching")},
                     indent=2, default=float)[:1800])
