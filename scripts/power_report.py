"""Attach a resolution bound to every null claim in the repo.

Reads the committed results and, for each null, answers: how big an effect
would this design have caught? Writes `results/power_report.json` and prints a
table.

Benchmarks below are the effect sizes worth caring about, chosen before looking
at the answers. They are stated here rather than in prose so they can be argued
with.

Run:  python scripts/power_report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from chesslab import power  # noqa: E402
from chesslab.paths import RESULTS  # noqa: E402

#: Effect sizes that would matter if real, fixed in advance.
#: Effect sizes used to judge whether a null is informative. These are
#: ILLUSTRATIVE magnitudes chosen by this repository, not figures taken from the
#: literature, and they are labelled that way wherever they are reported.
#:
#: An earlier version of this file justified the rating benchmark with the line
#: "commonly repeated claims about FIDE inflation run at 30-100 Elo/decade". That
#: figure was never sourced, and the literature search contradicted its framing:
#: the documented concern of the last decade is rating DEFLATION, concentrated
#: below 2000 and driven by a tenfold growth of the rated pool (Sonas 2023, 2024,
#: the analysis behind FIDE's March 2024 compression), while engine-anchored
#: studies find little or no drift in either direction at master level (Regan &
#: Haworth 2011; Regan, Macieja & Haworth 2012). The benchmark is therefore
#: stated as a symmetric drift magnitude, with no claim about who asserts it.
BENCHMARKS = {
    # 50 Elo per decade of drift in EITHER direction. At the within-panel
    # gradient of ~0.010 cp per Elo point, that is ~0.5 cp of ACPL per decade.
    "rating_drift_cp_per_decade": 0.5,
    # A quarter-pawn of engine evaluation, mapped to score at track 2's scale.
    "opening_score_per_pawn": 0.05,
}
BENCHMARK_PROVENANCE = {
    "rating_drift_cp_per_decade": (
        "Illustrative: 50 Elo/decade in either direction, converted with the within-player "
        "rating gradient from track 8. Chosen by this repository; not a literature figure."
    ),
    "opening_score_per_pawn": "Illustrative: chosen by this repository; not a literature figure.",
}


def load(name: str) -> dict | None:
    p = RESULTS / name
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    out: dict = {
        "benchmarks": BENCHMARKS,
        "benchmark_provenance": BENCHMARK_PROVENANCE,
        "nulls": {},
        "clustering": {},
    }

    t7 = load("t7_falsify.json")
    width_ratio = 1.0
    if t7:
        p4 = next((p for p in t7["probes"] if p["probe"].startswith("P4")), None)
        if p4 and p4.get("mean_width_ratio"):
            width_ratio = float(p4["mean_width_ratio"])
    out["clustering"] = {
        "ci_width_ratio_clustered_over_naive": width_ratio,
        "implied_design_effect_on_sample_size": power.design_effect(width_ratio),
        "note": (
            "Interval width scales with the standard error and sample size with variance, so a "
            f"{width_ratio:.2f}x width penalty means roughly {power.design_effect(width_ratio):.1f}x "
            "the games are needed for the same resolution. Every MDE below carries this."
        ),
    }

    # --- track 4: cross-sectional inflation null
    t4 = load("t4_inflation.json")
    if t4:
        tr = t4["trend_adjusted"]
        out["nulls"]["t4_inflation_acpl_per_decade"] = power.interpret_null(
            tr["acpl_year_coefficient_per_decade"],
            tr["ci_lo_per_decade"],
            tr["ci_hi_per_decade"],
            "cp per decade",
            benchmark=BENCHMARKS["rating_drift_cp_per_decade"],
        )

    # --- track 8: within-player inflation null
    t8 = load("t8_player_panel.json")
    if t8:
        y = t8["within_player_fit"]["year"]
        out["nulls"]["t8_within_player_acpl_per_decade"] = power.interpret_null(
            y["coefficient"] * 10,
            y["ci_lo"] * 10,
            y["ci_hi"] * 10,
            "cp per decade",
            benchmark=BENCHMARKS["rating_drift_cp_per_decade"],
        )
        ladder = t8.get("specification_ladder", {})
        if "with_career_curvature" in ladder:
            c = ladder["with_career_curvature"]["year"]
            out["nulls"]["t8_curvature_spec_resolution"] = power.mde_from_ci(
                c["ci_lo"] * 10, c["ci_hi"] * 10, "cp per decade"
            ).as_dict()

    # --- track 2: opening slope null, where x-range is the binding constraint
    t2 = load("t2_openings.json")
    if t2 and t2.get("families_analysed"):
        fams = t2["families_analysed"]
        x = np.array([f["book_cp"] for f in fams], dtype=float) / 100.0  # pawns
        # Residual noise in practical score is reported per band as the spread
        # across families; use the mean of those as the residual sd.
        spread = t2.get("practical_score_spread", {})
        resid_sd = float(spread.get("within_band_sd_mean", float("nan")))
        if np.isfinite(resid_sd) and resid_sd > 0:
            mde = power.mde_slope(resid_sd, x)
            out["nulls"]["t2_opening_slope"] = {
                **mde.as_dict(),
                "benchmark": BENCHMARKS["opening_score_per_pawn"],
                "benchmark_detectable": bool(BENCHMARKS["opening_score_per_pawn"] > mde.value),
                "x_range_pawns": [float(x.min()), float(x.max())],
                "why": (
                    "The x-axis spans about "
                    f"{(x.max() - x.min()):.2f} pawns across every mainline opening. Slope resolution "
                    "depends on the spread of x as much as on sample size, which is why this null is "
                    "weak no matter how many games are added."
                ),
            }

    # --- track 6: what the swindle-rate design could resolve
    t6 = load("t6_swindles.json")
    if t6:
        g = t6.get("online_gradient", {})
        rates = g.get("online_band_rates", [])
        if rates:
            base = float(np.mean([r["rate"] for r in rates]))
            n_per = int(np.mean([r["n"] for r in rates]))
            mde = power.mde_two_sample_proportion(base, n_per, width_ratio=width_ratio)
            out["nulls"]["t6_online_band_contrast"] = {
                **mde.as_dict(),
                "baseline_rate": base,
                "n_per_band": n_per,
                "n_required_for_5pp": power.n_required_for_effect(base, 0.05, width_ratio),
                "n_required_for_10pp": power.n_required_for_effect(base, 0.10, width_ratio),
                "why": (
                    "The observed spread across online bands is a few points. This is the smallest "
                    "band-to-band gap the current sample could have called real."
                ),
            }

    (RESULTS / "power_report.json").write_text(json.dumps(out, indent=2, default=float))

    print("clustering design effect: "
          f"{out['clustering']['implied_design_effect_on_sample_size']:.2f}x sample for same resolution\n")
    print(f"{'null':42s} {'resolution':>14s}  verdict vs benchmark")
    print("-" * 100)
    for name, v in out["nulls"].items():
        res = v.get("resolution_half_width", v.get("mde"))
        verdict = v.get("verdict") or (
            ("benchmark detectable" if v.get("benchmark_detectable") else "benchmark NOT detectable")
            if "benchmark_detectable" in v
            else ""
        )
        print(f"{name:42s} {res:14.4g}  {verdict[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
