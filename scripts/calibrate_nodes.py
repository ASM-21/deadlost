"""Is engine compute better spent on more games or deeper search?

THE QUESTION. Every centipawn number here costs search time, and the repo's
binding constraint is total engine compute rather than available games: the
corpus has 190,967 games and only 1,748 are evaluated. The power report shows
every null is limited by sample size. So the allocation question is real: at a
fixed compute budget, does a group comparison get sharper from evaluating more
games shallowly, or fewer games deeply?

WHY THE ANSWER IS NOT OBVIOUS. Shallower search misclassifies individual moves,
which adds noise to each observation. But group comparisons average over
thousands of moves, and misclassification that is unrelated to the grouping
attenuates toward zero rather than biasing the ordering. If that attenuation is
mild, more games wins easily, because standard error falls with the square root
of sample size while the attenuation cost is roughly constant.

WHAT THIS MEASURES. The same games evaluated at several node budgets, compared
on three things:

1. **Cost.** Wall-clock seconds per game at each budget, measured not assumed.
2. **Move-level agreement.** How often a move classified as a blunder at the
   reference budget is also a blunder at the cheaper one. This is the
   pessimistic view and will look bad; it is not what the tracks report.
3. **Group-level agreement.** Whether the by-band blunder rates and their
   gradient survive. This is what the tracks actually claim, and it is the
   number that should drive the decision.

Then it computes an **effective games per unit compute** figure: how many games
each budget buys per minute, and what that implies for confidence interval
width, so the tradeoff is stated in the units that matter.

Run:  python scripts/calibrate_nodes.py --games 30 --budgets 5000,10000,20000
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from chesslab import engine as eng  # noqa: E402
from chesslab import paths, stats  # noqa: E402
from chesslab.tracks.t1_ingest import load_games  # noqa: E402

REFERENCE_NODES = 80_000
BLUNDER_CP = 300
CACHE = paths.EVAL / "node_calibration.parquet"


def evaluate_at(game_ids: list[str], nodes: int, games: pd.DataFrame, time_budget: float | None = None):
    """Evaluate the given games at one node budget, returning rows and seconds."""
    rows = []
    t0 = time.time()
    done = 0
    with eng.Evaluator(nodes=nodes) as ev:
        for gid in game_ids:
            for me in ev.eval_game(gid, games.loc[gid, "moves"]):
                rows.append(
                    {"nodes": nodes, "game_id": gid, "ply": me.ply, "mover": me.mover, "loss_cp": me.loss_cp}
                )
            done += 1
            if time_budget is not None and time.time() - t0 > time_budget:
                break
    return rows, time.time() - t0, done


def load_cache() -> pd.DataFrame:
    return pd.read_parquet(CACHE) if CACHE.exists() else pd.DataFrame(
        columns=["nodes", "game_id", "ply", "mover", "loss_cp"]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--budgets", type=str, default="5000,10000,20000")
    ap.add_argument(
        "--use-production-reference",
        action="store_true",
        help=(
            "Use the already-evaluated 20k-node production sample as the reference instead of "
            "re-running at 80k. Trades a shallower reference for a ~20x larger comparison set, "
            "which is the right trade when the reference budget is not the quantity in question."
        ),
    )
    ap.add_argument("--time-budget", type=float, default=None, help="seconds per budget, then checkpoint")
    args = ap.parse_args()
    budgets = [int(b) for b in args.budgets.split(",")]

    games = load_games().set_index("game_id")
    sample = pd.read_csv(paths.EVAL / "eval_sample_lichess.csv")
    rng = np.random.default_rng(stats.SEED)
    chosen = list(rng.choice(sample.game_id.values, size=min(args.games, len(sample)), replace=False))

    cache = load_cache()

    reference_nodes = REFERENCE_NODES
    if args.use_production_reference:
        # Fold the production 20k evaluations in as the reference. They already
        # exist for all 480 sampled games, so the comparison set becomes the
        # whole sample rather than the few dozen that fit in a re-run budget.
        # The earlier n=24 attempt failed precisely on sample size: its measured
        # attenuation was non-monotone in the node budget, which cannot happen
        # as a real effect.
        from chesslab.eval_run import load_evals as _load_evals

        reference_nodes = 20000
        prod = _load_evals("lichess")
        prod = prod[prod.game_id.isin(chosen)][["game_id", "ply", "mover", "loss_cp"]].copy()
        prod["nodes"] = reference_nodes
        cache = pd.concat([cache[cache.nodes != reference_nodes], prod], ignore_index=True)
        budgets = [b for b in budgets if b < reference_nodes]
    timings = {}
    tpath = paths.RESULTS / "node_calibration.json"
    if tpath.exists():
        # Reload the RAW accumulator, not the derived per-game averages: the
        # latter is a float per budget and cannot be summed across runs.
        timings = json.loads(tpath.read_text()).get("raw_timings", {})

    for nodes in budgets + [reference_nodes]:
        have = set(cache[cache.nodes == nodes].game_id.unique()) if len(cache) else set()
        todo = [g for g in chosen if g not in have]
        if not todo:
            continue
        rows, secs, done = evaluate_at(todo, nodes, games, args.time_budget)
        if rows:
            cache = pd.concat([cache, pd.DataFrame(rows)], ignore_index=True)
            cache.to_parquet(CACHE, index=False)
        if done:
            prev = timings.get(str(nodes), {"seconds": 0.0, "games": 0})
            timings[str(nodes)] = {
                "seconds": prev["seconds"] + secs,
                "games": prev["games"] + done,
            }
        print(f"nodes={nodes}: +{done} games in {secs:.0f}s", flush=True)

    # ---- analysis over whatever is cached for all budgets
    covered = {n: set(cache[cache.nodes == n].game_id.unique()) for n in set(budgets + [reference_nodes])}
    common = set.intersection(*covered.values()) if covered else set()
    out: dict = {
        "reference_nodes": reference_nodes,
        "blunder_cp": BLUNDER_CP,
        "games_common_to_all_budgets": len(common),
        "seconds_per_game": {
            k: (v["seconds"] / v["games"] if v["games"] else None) for k, v in timings.items()
        },
        "raw_timings": timings,
        "budgets": {},
    }

    if len(common) >= 10:
        ref = cache[(cache.nodes == reference_nodes) & (cache.game_id.isin(common))]
        ref = ref.set_index(["game_id", "ply"]).loss_cp
        meta = sample.set_index("game_id")

        for nodes in budgets:
            cur = cache[(cache.nodes == nodes) & (cache.game_id.isin(common))]
            cur_i = cur.set_index(["game_id", "ply"]).loss_cp
            joined = pd.concat([ref.rename("ref"), cur_i.rename("cur")], axis=1).dropna()

            ref_b = joined.ref >= BLUNDER_CP
            cur_b = joined.cur >= BLUNDER_CP
            agree = float((ref_b == cur_b).mean())
            recall = float((cur_b & ref_b).sum() / ref_b.sum()) if ref_b.sum() else float("nan")
            precision = float((cur_b & ref_b).sum() / cur_b.sum()) if cur_b.sum() else float("nan")

            # group level: by-band rates and gradient
            g = cur.copy()
            g["band"] = g.game_id.map(meta.stratum).str.split("|").str[0]
            r = cache[(cache.nodes == reference_nodes) & (cache.game_id.isin(common))].copy()
            r["band"] = r.game_id.map(meta.stratum).str.split("|").str[0]
            cur_rates = g.assign(b=g.loss_cp >= BLUNDER_CP).groupby("band").b.mean()
            ref_rates = r.assign(b=r.loss_cp >= BLUNDER_CP).groupby("band").b.mean()
            bands = sorted(set(cur_rates.index) & set(ref_rates.index))
            xs = np.arange(len(bands))
            grad_cur = stats.ols_slope(xs, cur_rates.reindex(bands).values)[0]
            grad_ref = stats.ols_slope(xs, ref_rates.reindex(bands).values)[0]

            # A second estimand. The gradient is track 3's; tracks 4 and 8 rest
            # on mean centipawn loss instead, which could degrade differently
            # because it uses the whole loss distribution rather than a
            # threshold crossing. Validating one estimand does not validate the
            # other, so both are measured.
            acpl_cur = float(cur.loss_cp.clip(upper=300).mean())
            acpl_ref = float(r.loss_cp.clip(upper=300).mean())
            acpl_by_band_cur = g.assign(l=g.loss_cp.clip(upper=300)).groupby("band").l.mean()
            acpl_by_band_ref = r.assign(l=r.loss_cp.clip(upper=300)).groupby("band").l.mean()
            acpl_grad_cur = stats.ols_slope(xs, acpl_by_band_cur.reindex(bands).values)[0]
            acpl_grad_ref = stats.ols_slope(xs, acpl_by_band_ref.reindex(bands).values)[0]

            spg = out["seconds_per_game"].get(str(nodes))
            spg_ref = out["seconds_per_game"].get(str(reference_nodes))
            speedup = (spg_ref / spg) if (spg and spg_ref) else None
            out["budgets"][str(nodes)] = {
                "move_level_blunder_agreement": agree,
                "recall_of_reference_blunders": recall,
                "precision_against_reference": precision,
                "band_rates": {b: float(cur_rates[b]) for b in bands},
                "band_rates_reference": {b: float(ref_rates[b]) for b in bands},
                "gradient": grad_cur,
                "gradient_reference": grad_ref,
                "gradient_attenuation": (grad_cur / grad_ref) if grad_ref else None,
                "acpl_mean": acpl_cur,
                "acpl_mean_reference": acpl_ref,
                "acpl_ratio": (acpl_cur / acpl_ref) if acpl_ref else None,
                "acpl_gradient_attenuation": (acpl_grad_cur / acpl_grad_ref) if acpl_grad_ref else None,
                "seconds_per_game": spg,
                "games_per_minute": (60.0 / spg) if spg else None,
                "speedup_vs_reference": speedup,
                # More games narrow a CI by sqrt(n). If a budget is k times
                # faster, it buys k times the games, so intervals shrink by
                # sqrt(k) -- provided the group-level estimate survives.
                "implied_ci_narrowing_vs_reference": math.sqrt(speedup) if speedup else None,
            }

        # SANITY CHECK BEFORE RECOMMENDING ANYTHING.
        # Attenuation must rise toward 1.0 as the budget approaches the
        # reference: a deeper search cannot systematically distort a group
        # estimate FURTHER from its own deeper self. If the measured curve is
        # not monotone, the estimate is dominated by sampling noise and any
        # recommendation drawn from it would be an artifact. This check exists
        # because the first run of this script produced 0.90, 0.79, 1.11 across
        # increasing budgets and would otherwise have "recommended" the
        # cheapest one on the strength of pure noise.
        ordered = sorted(out["budgets"].items(), key=lambda kv: int(kv[0]))
        atts = [v.get("gradient_attenuation") for _, v in ordered]
        n_common = out["games_common_to_all_budgets"]
        out["attenuation_by_budget"] = {k: v.get("gradient_attenuation") for k, v in ordered}

        if len(atts) >= 2:
            # With several budgets, attenuation must approach 1 as the budget
            # approaches the reference. Non-monotone means noise.
            monotone = all(a is not None for a in atts) and all(
                abs(1 - atts[i + 1]) <= abs(1 - atts[i]) + 0.05 for i in range(len(atts) - 1)
            )
            out["attenuation_monotone"] = bool(monotone)
            trustworthy = monotone
            untrusted_reason = "attenuation is not monotone in the node budget"
        else:
            # A single budget gives no monotonicity to check, so the guard
            # becomes a sample-size requirement instead. The earlier failure was
            # 24 common games; a few hundred is what makes an attenuation
            # estimate stable.
            out["attenuation_monotone"] = None
            trustworthy = n_common >= 200 and atts and atts[0] is not None
            untrusted_reason = f"only {n_common} common games (need >=200 with a single budget)"

        if not trustworthy:
            out["recommendation"] = {
                "nodes": None,
                "reasoning": (
                    f"REFUSED: {untrusted_reason}. Attenuation by budget: "
                    f"{out['attenuation_by_budget']}. Cost measurements are still valid; the accuracy "
                    "side is not. Re-run with more games before trusting any recommendation."
                ),
                "cost_findings_still_valid": True,
                "games_needed_estimate": "on the order of 200+ common games, not tens",
            }
        else:
            best = None
            for nodes, v in ordered:
                att = v.get("gradient_attenuation")
                nar = v.get("implied_ci_narrowing_vs_reference")
                acpl_r = v.get("acpl_ratio")
                # Both estimands must survive, not just the gradient.
                if acpl_r is not None and not (0.9 <= acpl_r <= 1.1):
                    continue
                if att and nar and 0.85 < att < 1.15:
                    score = nar * att
                    if best is None or score > best[1]:
                        best = (nodes, score)
            out["recommendation"] = (
                {
                    "nodes": int(best[0]),
                    "reasoning": (
                        "Cheapest budget whose by-band gradient retains at least 85% of the reference "
                        "value, weighted by the interval narrowing its speed buys. Move-level agreement "
                        "is deliberately NOT the criterion: individual misclassifications average out "
                        "of a group comparison, and optimising for them would buy precision the tracks "
                        "never use."
                    ),
                }
                if best
                else {"nodes": None, "reasoning": "no budget preserved the gradient adequately"}
            )
    else:
        out["recommendation"] = {"nodes": None, "reasoning": "not enough games evaluated at all budgets yet"}

    tpath.write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "raw_timings"}, indent=2, default=float)[:2600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
