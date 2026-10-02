"""Track 7: try to break tracks 2-6.

This track exists to fail the other tracks, not to confirm them. Each probe
below is a way one of the earlier findings could be an artifact, written as a
concrete test with a stated pass condition. A probe that fires is a finding
about this repo, and the affected claim is downgraded in FINDINGS.md rather
than quietly kept.

PROBES

  P1 base-rate confound in track 6. Masters "save" lost positions as draws far
     more than amateurs do. But masters draw far more games overall. If the
     lost-position draw rate is just the base draw rate showing through, the
     track 6 story about defensive skill is empty. Pass condition: the save
     rate must exceed what the corpus's unconditional result mix predicts.

  P2 engine depth. Every centipawn number comes from Stockfish at 20k nodes,
     which is shallow. If a deeper search reorders the groups, the rankings are
     artifacts of a weak engine rather than facts about the players. Pass
     condition: group ordering is preserved at 4x nodes on a paired subsample.

  P3 label permutation in track 3. The blunder-rate-by-band gradient should
     vanish when band labels are shuffled. If it survives, the interval
     construction is broken. Pass condition: the observed gradient sits outside
     the permutation distribution.

  P4 clustering. If moves were treated as independent, how much narrower would
     the intervals be? This quantifies the error the repo is avoiding rather
     than testing a claim. No pass condition; it reports a ratio.

  P7 behavioural drift in the skill anchor. Tracks 4 and 8 use centipawn loss
     as a proxy for skill across 28 years. If players changed *when they stop
     playing* rather than how well they play, the composition of the scored
     move sample drifts and the anchor drifts with it. Pass condition: the
     share of scored moves made in already-decided positions shows no time
     trend. This probe was written after track 11 showed how large resignation
     effects are in this data.

  P8 format contamination. Every TWIC-derived analysis claims to describe
     classical over-the-board chess. From 2020, TWIC is majority online blitz
     and carries no TimeControl tag, so a filter must hold at load time. An
     earlier build had no such filter, and it produced a retracted headline
     (falling draw rates) and a retracted probe result (P7). Pass condition:
     no non-classical game reaches any TWIC-derived engine sample.

  P6 evaluation determinism. Every centipawn number assumes the engine gives
     the same answer for the same position regardless of what it searched
     before. It does not, unless the transposition table is explicitly reset
     per game. This probe re-evaluates a game after evaluating an unrelated one
     and demands bitwise agreement. Pass condition: identical results.

  P5 censoring in track 6. Game-sides still running at max_ply are dropped. If
     the dropped ones differ systematically, the swindle rate is biased. Pass
     condition: bounding the excluded cases both ways does not flip the
     band ordering.

Run:  python -m deadlost.tracks.t7_falsify
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import engine as eng
from .. import paths, stats
from ..eval_run import load_evals
from . import t3_blunders, t6_swindles
from .t1_ingest import load_games

DEPTH_CHECK_GAMES = 60
DEPTH_CHECK_NODES = 80_000
N_PERMUTATIONS = 1000


# --------------------------------------------------------------------------
# P1: is the master draw-save just the base draw rate?
# --------------------------------------------------------------------------


def p1_base_rate_confound() -> dict:
    """Compare lost-position save rates against unconditional result mixes.

    The comparison is deliberately conservative. If a side is lost, the
    *unconditional* draw rate of the corpus is an upper bound on what a
    "no defensive skill, results are random draws from the corpus mix" null
    would produce, since being lost can only make a draw less likely than the
    unconditional rate. So if the observed save rate is BELOW the corpus draw
    rate, the finding carries no information about defence.
    """
    games = load_games()
    t6 = json.loads((paths.RESULTS / "t6_swindles.json").read_text())

    base = {}
    li = games[(games.source == "lichess2017") & (games.rated == True)]  # noqa: E712
    li = li[li.white_band == li.black_band]
    for band, cell in li.groupby("white_band"):
        if len(cell) >= 200:
            base[band] = {"draw_rate": float((cell.result == "1/2-1/2").mean()), "n": int(len(cell))}
    tw = games[(games.source == "twic") & (games.format == "classical_otb")].dropna(subset=["white_elo", "black_elo"])
    tw = tw[tw.white_elo.between(2400, 2499) & tw.black_elo.between(2400, 2499)]
    base["2400-2499 (OTB)"] = {"draw_rate": float((tw.result == "1/2-1/2").mean()), "n": int(len(tw))}

    rows = []
    for band, v in t6.get("by_rating_band", {}).items():
        if band not in base:
            continue
        rows.append(
            {
                "band": band,
                "base_draw_rate_all_games": base[band]["draw_rate"],
                "draw_save_rate_from_lost": v["draw_save_rate"]["point"],
                "ratio_save_to_base": v["draw_save_rate"]["point"] / base[band]["draw_rate"]
                if base[band]["draw_rate"]
                else None,
                "total_save_rate": v["swindle_rate"]["point"],
                "n_lost_game_sides": v["n_lost_game_sides"],
                "n_draw_saves": round(v["draw_save_rate"]["point"] * v["n_lost_game_sides"]),
            }
        )
    df = pd.DataFrame(rows)

    # Does the draw-save gap between masters and amateurs survive normalising
    # by each group's own base draw rate?
    fired = False
    verdict = "no master/amateur draw-save contrast to test"
    if len(df) >= 2 and "2400-2499 (OTB)" in set(df.band):
        m = df[df.band == "2400-2499 (OTB)"].iloc[0]
        amateurs = df[df.band != "2400-2499 (OTB)"]
        m_ratio = m.ratio_save_to_base
        a_ratio = float(amateurs.ratio_save_to_base.mean())
        fired = bool(m_ratio is not None and m_ratio <= a_ratio)
        verdict = (
            f"master draw-save is {m_ratio:.2f}x its own base draw rate vs {a_ratio:.2f}x for amateurs; "
            + (
                "PROBE FIRES: once each group is normalised by how often it draws anyway, the master "
                "'defensive skill' reading does not survive."
                if fired
                else "probe passes: masters save as draws more than their own high base draw rate explains."
            )
        )

    return {
        "probe": "P1 base-rate confound in track 6",
        "fired": fired,
        "verdict": verdict,
        "detail": df.to_dict(orient="records"),
    }


# --------------------------------------------------------------------------
# P2: does a deeper engine reorder the groups?
# --------------------------------------------------------------------------


def p2_depth_sensitivity(n_games: int = DEPTH_CHECK_GAMES, nodes: int = DEPTH_CHECK_NODES, time_budget: float | None = None) -> dict:
    """Re-evaluate a paired subsample at higher node count, compare orderings."""
    cache = paths.EVAL / f"depth_check_{nodes}.parquet"
    shallow = load_evals("lichess")
    games = load_games().set_index("game_id")
    sample = pd.read_csv(paths.EVAL / "eval_sample_lichess.csv")

    rng = np.random.default_rng(stats.SEED)
    gids = sample.game_id.values
    pick = list(rng.choice(gids, size=min(n_games, len(gids)), replace=False))

    have = pd.read_parquet(cache) if cache.exists() else pd.DataFrame(columns=["game_id", "ply", "loss_cp"])
    todo = [g for g in pick if g not in set(have.game_id)]

    rows = []
    if todo:
        import time as _t

        t0 = _t.time()
        with eng.Evaluator(nodes=nodes) as ev:
            for gid in todo:
                moves = games.loc[gid, "moves"]
                for me in ev.eval_game(gid, moves):
                    rows.append({"game_id": gid, "ply": me.ply, "loss_cp": me.loss_cp})
                if time_budget is not None and _t.time() - t0 > time_budget:
                    break
    deep = pd.concat([have, pd.DataFrame(rows)], ignore_index=True) if rows else have
    if rows:
        # Only rewrite the cache when something new was evaluated. Rewriting an
        # unchanged cache reorders rows, changes its bytes, and makes the
        # provenance manifest report drift that is not there.
        deep = deep.drop_duplicates(subset=["game_id", "ply"])
        deep.to_parquet(cache, index=False)

    covered = set(deep.game_id.unique())
    if len(covered) < 10:
        return {"probe": "P2 engine depth", "fired": None, "verdict": "insufficient deep evaluations yet", "n_games": len(covered)}

    meta = sample.set_index("game_id")
    sh = shallow[shallow.game_id.isin(covered)].copy()
    dp = deep[deep.game_id.isin(covered)].copy()
    for frame in (sh, dp):
        frame["band"] = frame.game_id.map(meta.stratum).str.split("|").str[0]

    sh_rate = sh.assign(b=(sh.loss_cp >= t3_blunders.BLUNDER_CP)).groupby("band").b.mean()
    dp_rate = dp.assign(b=(dp.loss_cp >= t3_blunders.BLUNDER_CP)).groupby("band").b.mean()
    common = sorted(set(sh_rate.index) & set(dp_rate.index))
    sh_o = sh_rate.reindex(common)
    dp_o = dp_rate.reindex(common)

    from scipy.stats import spearmanr

    rho = float(spearmanr(sh_o.values, dp_o.values).statistic) if len(common) >= 3 else float("nan")

    # Pass criteria, all three required. Deliberately not a bare threshold on
    # rho: with five bands, Spearman can only take a handful of values, so a
    # cutoff near 1.0 fires on a single adjacent swap between two bands whose
    # rates were never distinguishable in the first place.
    grad_sh = stats.ols_slope(np.arange(len(common)), sh_o.values)[0]
    grad_dp = stats.ols_slope(np.arange(len(common)), dp_o.values)[0]
    same_sign = bool(np.sign(grad_sh) == np.sign(grad_dp))
    rank_ok = bool(rho >= 0.8 - 1e-9)

    # A "meaningful flip" is a pair of bands whose shallow rates differ by more
    # than 1 percentage point and whose order reverses under deeper search.
    flips = []
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            d_sh = sh_o.values[i] - sh_o.values[j]
            d_dp = dp_o.values[i] - dp_o.values[j]
            if abs(d_sh) > 0.01 and np.sign(d_sh) != np.sign(d_dp):
                flips.append([common[i], common[j]])
    fired = bool(len(common) >= 3 and (not rank_ok or not same_sign or flips))

    return {
        "probe": "P2 engine depth",
        "fired": fired,
        "shallow_nodes": 20000,
        "deep_nodes": nodes,
        "n_games_paired": int(len(covered)),
        "blunder_rate_by_band_shallow": {k: float(v) for k, v in sh_o.items()},
        "blunder_rate_by_band_deep": {k: float(v) for k, v in dp_o.items()},
        "spearman_rho_of_orderings": rho,
        "gradient_shallow": float(grad_sh),
        "gradient_deep": float(grad_dp),
        "gradient_sign_preserved": same_sign,
        "meaningful_flips": flips,
        "mean_abs_rate_shift": float(np.mean(np.abs(sh_o.values - dp_o.values))),
        "verdict": (
            f"PROBE FIRES: deeper search reorders the rating bands (rho={rho:.2f}, flips={flips}); "
            "the shallow-eval ordering is not safe."
            if fired
            else f"probe passes: rho={rho:.2f}, gradient sign preserved, no band pair separated by >1pp "
            "reverses under a 4x deeper search. Absolute rates shift upward slightly, as expected: a "
            "deeper engine finds more of the refutations that make a move a blunder."
        ),
    }


# --------------------------------------------------------------------------
# P3: permutation null for the band gradient
# --------------------------------------------------------------------------


def p3_permutation(n_perm: int = N_PERMUTATIONS) -> dict:
    df = t3_blunders.build_move_table()
    g = df.groupby("game_id").agg(rate=("is_blunder", "mean"), band=("band", "first"), n=("is_blunder", "size"))
    g = g[g.n >= 10]
    order = sorted(g.band.unique())
    idx = {b: i for i, b in enumerate(order)}

    def gradient(bands: np.ndarray) -> float:
        tmp = pd.DataFrame({"rate": g.rate.values, "band": bands, "n": g.n.values})
        means = tmp.groupby("band").apply(lambda c: np.average(c.rate, weights=c.n), include_groups=False)
        xs = np.array([idx[b] for b in means.index])
        return stats.ols_slope(xs, means.values)[0]

    observed = gradient(g.band.values)
    rng = np.random.default_rng(stats.SEED)
    null = np.array([gradient(rng.permutation(g.band.values)) for _ in range(n_perm)])
    p = float((np.abs(null) >= abs(observed)).mean())
    fired = bool(p > 0.05)

    return {
        "probe": "P3 permutation null for band gradient",
        "fired": fired,
        "observed_slope_per_band_step": float(observed),
        "permutation_p_value": p,
        "null_sd": float(null.std()),
        "n_permutations": n_perm,
        "verdict": (
            "PROBE FIRES: the observed by-band gradient is inside the permutation null, so it is noise."
            if fired
            else "probe passes: the by-band blunder gradient is far outside the label-shuffled null."
        ),
    }


# --------------------------------------------------------------------------
# P4: what would ignoring clustering have cost?
# --------------------------------------------------------------------------


def p4_clustering_cost() -> dict:
    df = t3_blunders.build_move_table()
    out = {}
    for band, cell in df.groupby("band"):
        clustered = stats.cluster_bootstrap(cell.is_blunder.values, cell.game_id.values, np.mean)
        naive = stats.wilson_ci(cell.is_blunder.sum(), len(cell))
        cw = clustered.hi - clustered.lo
        nw = naive.hi - naive.lo
        out[band] = {
            "clustered_ci_width": cw,
            "naive_move_level_ci_width": nw,
            "width_ratio": cw / nw if nw else None,
            "n_moves": int(len(cell)),
            "n_games": int(cell.game_id.nunique()),
        }
    ratios = [v["width_ratio"] for v in out.values() if v["width_ratio"]]
    return {
        "probe": "P4 cost of ignoring clustering",
        "fired": None,
        "mean_width_ratio": float(np.mean(ratios)) if ratios else None,
        "verdict": (
            f"Treating moves as independent would have produced intervals about "
            f"{np.mean(ratios):.1f}x too narrow."
            if ratios
            else "not computable"
        ),
        "detail": out,
    }


# --------------------------------------------------------------------------
# P5: censoring bounds in track 6
# --------------------------------------------------------------------------


def p5_censoring_bounds() -> dict:
    frames = []
    for tag in ("lichess", "twic"):
        try:
            frames.append(t6_swindles._entries(load_evals(tag), t6_swindles._meta(tag), t6_swindles.LOST_CP))
        except FileNotFoundError:
            continue
    entries = pd.concat(frames, ignore_index=True)

    rows = []
    for band, cell in entries.groupby("band"):
        live = cell[~cell.censored]
        n_cens = int(cell.censored.sum())
        if len(live) < 10:
            continue
        point = float(live.saved.mean())
        lower = float(live.saved.sum() / (len(live) + n_cens))  # all censored = not saved
        upper = float((live.saved.sum() + n_cens) / (len(live) + n_cens))  # all censored = saved
        rows.append(
            {
                "band": band,
                "excluded_rate": point,
                "worst_case_lower": lower,
                "worst_case_upper": upper,
                "n_censored": n_cens,
            }
        )
    df = pd.DataFrame(rows).sort_values("excluded_rate", ascending=False)

    # Does the ordering survive the worst case? Compare amateurs vs the OTB band.
    fired = False
    verdict = "insufficient bands to test ordering"
    if "2400-2499 (OTB)" in set(df.band) and len(df) >= 3:
        otb = df[df.band == "2400-2499 (OTB)"].iloc[0]
        amateur_min = df[df.band != "2400-2499 (OTB)"].worst_case_lower.min()
        fired = bool(otb.worst_case_upper > amateur_min)
        verdict = (
            f"OTB save rate at its most favourable bound is {otb.worst_case_upper:.3f}; the weakest "
            f"amateur band at its least favourable is {amateur_min:.3f}. "
            + (
                "PROBE FIRES: the amateur-above-master ordering does not survive worst-case censoring."
                if fired
                else "probe passes: the ordering holds under the worst censoring assumption."
            )
        )
    return {"probe": "P5 censoring bounds in track 6", "fired": fired, "verdict": verdict, "detail": df.to_dict(orient="records")}


def p6_determinism() -> dict:
    """Re-evaluate a game after an unrelated one and demand bitwise agreement.

    This probe exists because the bug it tests for was real and shipped. An
    earlier build shared one transposition table across every game in a
    process, so a game's measured blunders depended on which games preceded it
    and therefore on how a resumable run happened to be chunked. Measured cost
    at the time: about 19cp per move. Nothing about the output looked wrong.
    """
    path = eng.find_engine()
    if not path:
        return {"probe": "P6 evaluation determinism", "fired": None, "verdict": "no engine available"}

    a = "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3 Na5 Bc2 c5 d4 Qc7 Nbd2 cxd4 cxd4"
    b = "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5 O-O Nc6 a3 Bxc3 bxc3 dxc4 Bxc4 Qc7 Bd3 e5 Qc2 Re8"
    with eng.Evaluator(nodes=15000) as ev:
        first = [m.loss_cp for m in ev.eval_game("A", a)]
        _ = [m.loss_cp for m in ev.eval_game("B", b)]
        again = [m.loss_cp for m in ev.eval_game("A", a)]
    with eng.Evaluator(nodes=15000) as ev:
        fresh = [m.loss_cp for m in ev.eval_game("A", a)]

    order_ok = first == again
    process_ok = first == fresh
    n_diff = sum(x != y for x, y in zip(first, again, strict=False))
    fired = not (order_ok and process_ok)
    return {
        "probe": "P6 evaluation determinism",
        "fired": fired,
        "order_independent_within_process": order_ok,
        "matches_fresh_process": process_ok,
        "moves_differing": n_diff,
        "verdict": (
            f"PROBE FIRES: {n_diff} moves change when an unrelated game is evaluated in between. "
            "Results depend on run chunking and are not reproducible."
            if fired
            else "probe passes: evaluation is order-independent and matches a fresh process bitwise."
        ),
    }


def p7_anchor_composition_drift() -> dict:
    """Does the ACPL anchor drift because behaviour changed rather than skill?

    Moves played in an already-decided position are not competitive chess; they
    are what happens after the contest is settled. If players play more of them
    now than they used to, measured centipawn loss rises without any change in
    skill, and in the same direction that genuine rating inflation would.
    """
    t4 = paths.RESULTS / "t4_inflation.json"
    if not t4.exists():
        return {"probe": "P7 anchor composition drift", "fired": None, "verdict": "track 4 not built"}
    d = json.loads(t4.read_text())
    comp = d.get("composition_drift")
    if not comp:
        return {"probe": "P7 anchor composition drift", "fired": None, "verdict": "composition drift not reported"}

    fired = bool(comp["excludes_zero"])
    raw = d["trend_winsorised_acpl"]["slope_per_decade"]
    corrected = d["trend_undecided_only"]["slope_per_decade"]
    return {
        "probe": "P7 anchor composition drift",
        "fired": fired,
        "decided_move_share_first_year": comp["share_first_year"],
        "decided_move_share_last_year": comp["share_last_year"],
        "slope_per_decade": comp["slope_per_decade"],
        "acpl_trend_all_moves": raw,
        "acpl_trend_undecided_only": corrected,
        "share_of_trend_removed": (raw - corrected) / raw if raw else None,
        "verdict": (
            "PROBE FIRES: the share of scored moves made in already-decided positions rises over the "
            f"period ({comp['share_first_year']:.3f} to {comp['share_last_year']:.3f}), so the skill "
            "anchor drifts for behavioural reasons. Track 4 now reports an undecided-positions-only "
            "anchor as its headline; the uncorrected trend should not be cited."
            if fired
            else "probe passes: no time trend in the composition of the scored move sample."
        ),
        "why_it_matters": (
            "The contaminant points the same direction as the hypothesis under test. A repo that only "
            "looked at the uncorrected anchor would have had a standing chance of reporting behavioural "
            "drift as rating inflation."
        ),
    }


def p8_format_contamination() -> dict:
    """No online or fast game may reach an analysis that claims classical play."""
    from ..eval_run import TWIC_TAGS

    games = load_games().set_index("game_id")
    per_tag = {}
    leaked_total = 0
    for tag in sorted(TWIC_TAGS):
        try:
            unfiltered = load_evals(tag, classical_only=False)
            filtered = load_evals(tag)
        except FileNotFoundError:
            continue
        g_all = unfiltered.game_id.unique()
        g_kept = filtered.game_id.unique()
        fmt_all = games.loc[g_all, "format"]
        fmt_kept = games.loc[g_kept, "format"]
        leaked = int((fmt_kept != "classical_otb").sum())
        leaked_total += leaked
        per_tag[tag] = {
            "games_evaluated": int(len(g_all)),
            "non_classical_share_before_filter": float((fmt_all != "classical_otb").mean()),
            "games_reaching_analysis": int(len(g_kept)),
            "non_classical_reaching_analysis": leaked,
        }
    t1 = json.loads((paths.RESULTS / "t1_validation.json").read_text())
    return {
        "probe": "P8 format contamination",
        "fired": bool(leaked_total > 0),
        "per_sample": per_tag,
        "twic_format_by_era": t1.get("twic_format_by_era"),
        "verdict": (
            f"PROBE FIRES: {leaked_total} non-classical games reach analyses that claim classical play."
            if leaked_total
            else "probe passes: the classical filter holds for every TWIC-derived sample. Without it, a "
            "fifth or more of several samples would be online or fast chess, concentrated after 2020."
        ),
        "history": (
            "This probe was written after the fact. An earlier build treated all of TWIC as classical "
            "over-the-board play. The error was found by a literature search, not by any test: a 2026 "
            "study reported classical draw rates RISING after 2020 while this repo reported them "
            "falling, and chasing the contradiction exposed the contamination."
        ),
    }


def run(depth_budget: float | None = None) -> dict:
    probes = [
        p1_base_rate_confound(),
        p2_depth_sensitivity(time_budget=depth_budget),
        p3_permutation(),
        p4_clustering_cost(),
        p5_censoring_bounds(),
        p6_determinism(),
        p7_anchor_composition_drift(),
        p8_format_contamination(),
    ]
    out = {
        "probes": probes,
        "summary": {
            "fired": [p["probe"] for p in probes if p.get("fired") is True],
            "passed": [p["probe"] for p in probes if p.get("fired") is False],
            "informational": [p["probe"] for p in probes if p.get("fired") is None],
        },
    }
    (paths.RESULTS / "t7_falsify.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(probes)
    return out


def _figure(probes: list[dict]) -> None:
    """P1's figure: save rates against each group's own base draw rate.

    This is the picture that killed the track 6 secondary claim, so it belongs
    in the repo rather than only in the JSON.
    """
    from .. import viz

    p1 = next((p for p in probes if p["probe"].startswith("P1")), None)
    if not p1 or not p1.get("detail"):
        return
    df = pd.DataFrame(p1["detail"]).sort_values("base_draw_rate_all_games")
    fig, ax = viz.new_fig(8.0, 5.0)
    x = np.arange(len(df))
    ax.bar(x - 0.2, df.base_draw_rate_all_games, width=0.4, color=viz.PALETTE[0], label="Draw rate, all games")
    ax.bar(x + 0.2, df.draw_save_rate_from_lost, width=0.4, color=viz.PALETTE[1], label="Draw rate from lost positions")
    for i, r in enumerate(df.itertuples(index=False)):
        # A zero-count cell has no meaningful ratio; label it as the small
        # sample it is rather than printing "0.00x" as though it were measured.
        lab = f"{r.ratio_save_to_base:.2f}x" if r.n_draw_saves > 0 else f"0/{r.n_lost_game_sides}"
        ax.text(i, max(r.base_draw_rate_all_games, r.draw_save_rate_from_lost) + 0.012,
                lab, ha="center", fontsize=7, color="#333333")
    ax.set_ylim(0, max(df.base_draw_rate_all_games.max(), df.draw_save_rate_from_lost.max()) * 1.22)
    ax.set_xticks(x)
    ax.set_xticklabels(df.band, rotation=25, ha="right")
    viz.finish(
        fig, ax,
        "Probe P1: saving a lost position as a draw, against the base rate of drawing at all",
        "Rating band",
        "Proportion",
        paths.figure_path("t7_p1_base_rate_confound.png"),
        note="deadlost track 7. Labels are the ratio of the two bars; a cell with no draw-saves is "
             "labelled as a count instead. Masters draw far more overall AND save lost positions as draws "
             "at a LOWER multiple of their own base rate (0.13x) than amateurs do (0.24x mean). The "
             "amateur mean includes a 0/73 cell, so excluding it would widen the gap, not narrow it.",
    )


if __name__ == "__main__":
    r = run()
    for p in r["probes"]:
        print(f"[{'FIRED' if p.get('fired') else 'pass ' if p.get('fired') is False else 'info '}] {p['probe']}")
        print(f"        {p['verdict']}")
