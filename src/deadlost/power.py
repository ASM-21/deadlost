"""Minimum detectable effects, so a null means something.

Three of this repo's headline results are nulls: no rating inflation (tracks 4
and 8), and no relationship between engine-assessed opening quality and
practical results (track 2). A null on its own is nearly content-free. "We
found no effect" is compatible with "there is no effect", "there is an effect
and our sample is too small", and "our design cannot see this effect at all",
and readers cannot tell which without a number attached.

This module attaches the number. For each null it reports a **minimum
detectable effect** (MDE): the smallest true effect the design would have
caught, at conventional power, given the noise actually observed. A null plus
an MDE is a bounded claim: "any drift larger than X would have shown up, and
none did."

Two methods, chosen to match how each result was computed:

`mde_from_ci` inverts the observed confidence interval. If a bootstrap gave a
95% interval of half-width h around a point estimate, then an effect of roughly
h is the smallest one that interval would have excluded from zero. This is the
right tool when the headline came from a bootstrap, which is most of this repo.
It is descriptive rather than a true power calculation, and is labelled as
such.

`mde_two_sample_proportion` and `mde_slope` are conventional power
calculations for the cases where the design is simple enough to admit one, and
they take the **design effect** from clustering into account. Ignoring
clustering here would understate the required sample by the same factor it
understates the intervals, which for this corpus is about 1.5x in width, so
roughly 2.2x in sample size.

Run:  python scripts/power_report.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

#: Conventional two-sided alpha and target power.
ALPHA = 0.05
POWER = 0.80

_Z_ALPHA = 1.959963985
_Z_POWER = 0.8416212336


@dataclass(frozen=True)
class MDE:
    """A minimum detectable effect and how it was obtained."""

    value: float
    units: str
    method: str
    note: str = ""

    def as_dict(self) -> dict:
        return {"mde": self.value, "units": self.units, "method": self.method, "note": self.note}


def mde_from_ci(ci_lo: float, ci_hi: float, units: str, scale: float = 1.0) -> MDE:
    """Half-width of an observed interval, as a descriptive detectability bound.

    Interpretation: an effect of this size would have produced an interval
    excluding zero, had it been centred where the observed estimate is. This is
    not a power calculation and does not claim 80% power; it is the honest
    reading of what a bootstrap interval already tells you about resolution.
    """
    half = abs(ci_hi - ci_lo) / 2.0 * scale
    return MDE(
        value=half,
        units=units,
        method="half-width of observed bootstrap CI",
        note=(
            "Descriptive resolution bound, not an 80%-power MDE. An effect near this size sits at the "
            "edge of what the observed interval could distinguish from zero."
        ),
    )


def design_effect(width_ratio: float) -> float:
    """Convert a clustered/naive CI *width* ratio into a variance inflation.

    Confidence interval width scales with the standard error, and required
    sample size scales with variance, so a width ratio r implies r**2 more
    observations for the same resolution. Probe P4 measures this ratio
    empirically for this corpus.
    """
    return float(width_ratio) ** 2


def mde_two_sample_proportion(
    p_baseline: float,
    n_per_group: int,
    width_ratio: float = 1.0,
    alpha: float = ALPHA,
    power: float = POWER,
) -> MDE:
    """Smallest detectable difference between two proportions.

    `width_ratio` is the clustered-to-naive CI width ratio; passing it inflates
    the variance by its square, which is what clustering costs in sample terms.
    """
    if not (0 < p_baseline < 1) or n_per_group <= 0:
        return MDE(float("nan"), "proportion", "two-sample normal approximation")
    deff = design_effect(width_ratio)
    var = 2.0 * p_baseline * (1.0 - p_baseline) * deff / n_per_group
    delta = (_Z_ALPHA + _Z_POWER) * math.sqrt(var)
    return MDE(
        value=float(delta),
        units="difference in proportion",
        method="two-sample normal approximation",
        note=(
            f"baseline p={p_baseline:.3f}, n={n_per_group} per group, "
            f"design effect {deff:.2f}x from clustering"
        ),
    )


def mde_slope(residual_sd: float, x_values: np.ndarray, alpha: float = ALPHA, power: float = POWER) -> MDE:
    """Smallest detectable slope given residual noise and the spread of x.

    The spread of x matters as much as the sample size: a regression run over a
    narrow x-range has poor resolution no matter how many points it has. That is
    exactly track 2's situation, where every mainline opening evaluates within a
    26cp band.
    """
    x = np.asarray(x_values, dtype=float)
    x = x[np.isfinite(x)]
    sxx = float(((x - x.mean()) ** 2).sum())
    if sxx <= 0 or residual_sd <= 0:
        return MDE(float("nan"), "slope", "OLS slope power")
    se = residual_sd / math.sqrt(sxx)
    return MDE(
        value=float((_Z_ALPHA + _Z_POWER) * se),
        units="slope (y units per x unit)",
        method="OLS slope power",
        note=f"residual sd={residual_sd:.4g}, sum of squared x deviations={sxx:.4g}, n={len(x)}",
    )


def n_required_for_effect(
    p_baseline: float,
    target_delta: float,
    width_ratio: float = 1.0,
    alpha: float = ALPHA,
    power: float = POWER,
) -> int:
    """Per-group sample needed to detect a given difference in proportions.

    The practical question behind every null in this repo: how much more data
    would settle it?
    """
    if target_delta <= 0 or not (0 < p_baseline < 1):
        return -1
    deff = design_effect(width_ratio)
    n = 2.0 * p_baseline * (1.0 - p_baseline) * deff * ((_Z_ALPHA + _Z_POWER) / target_delta) ** 2
    return int(math.ceil(n))


def interpret_null(point: float, ci_lo: float, ci_hi: float, units: str, benchmark: float | None = None) -> dict:
    """Package a null with its resolution, and optionally against a benchmark.

    `benchmark` is a real-world effect size worth caring about. Comparing it to
    the interval turns "we found nothing" into one of two much more useful
    statements: the design could have seen an effect that size and did not, or
    the design was never able to see it.
    """
    half = abs(ci_hi - ci_lo) / 2.0
    out = {
        "point_estimate": point,
        "ci": [ci_lo, ci_hi],
        "resolution_half_width": half,
        "units": units,
        "excludes_zero": bool(ci_lo * ci_hi > 0),
    }
    if benchmark is not None:
        out["benchmark"] = benchmark
        out["benchmark_would_have_been_detected"] = bool(abs(benchmark) > half)
        out["verdict"] = (
            f"An effect of {benchmark:g} {units} would have been outside this interval, so the null "
            "rules it out."
            if abs(benchmark) > half
            else f"An effect of {benchmark:g} {units} would have fit inside this interval, so the null "
            "does NOT rule it out. The design cannot see effects this small."
        )
    return out
