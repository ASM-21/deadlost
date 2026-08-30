"""Uncertainty helpers.

The one thing that matters most here: **moves are not independent
observations.** A single game contributes 60 correlated moves and a single
player contributes many correlated games. Treating moves as independent makes
every confidence interval in this repo roughly three to five times too narrow
and turns noise into findings. Every interval below that is used on move-level
data resamples whole *games*, not moves.

`wilson_ci` is the exception and is only used where the unit of observation
genuinely is the unit of clustering, i.e. one game -> one outcome.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

DEFAULT_BOOT = 2000
SEED = 20260810


@dataclass(frozen=True)
class Interval:
    point: float
    lo: float
    hi: float
    n: int

    def as_dict(self) -> dict:
        return {"point": self.point, "ci_lo": self.lo, "ci_hi": self.hi, "n": self.n}

    def __str__(self) -> str:
        return f"{self.point:.4g} [{self.lo:.4g}, {self.hi:.4g}] (n={self.n})"


def wilson_ci(successes: float, total: int, z: float = 1.96) -> Interval:
    """Wilson score interval for a proportion of independent trials."""
    if total == 0:
        return Interval(float("nan"), float("nan"), float("nan"), 0)
    p = successes / total
    denom = 1 + z ** 2 / total
    centre = (p + z ** 2 / (2 * total)) / denom
    half = z / denom * np.sqrt(p * (1 - p) / total + z ** 2 / (4 * total ** 2))
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half), total)


def cluster_bootstrap(
    values: np.ndarray,
    clusters: np.ndarray,
    stat: Callable[[np.ndarray], float],
    n_boot: int = DEFAULT_BOOT,
    seed: int = SEED,
    alpha: float = 0.05,
) -> Interval:
    """Percentile bootstrap CI resampling whole clusters with replacement.

    `values` and `clusters` are parallel arrays. `stat` maps a resampled value
    array to a scalar. Resampling clusters (games, players) rather than rows
    (moves) is what keeps the interval honest.
    """
    values = np.asarray(values)
    clusters = np.asarray(clusters)
    if len(values) == 0:
        return Interval(float("nan"), float("nan"), float("nan"), 0)

    uniq, inverse = np.unique(clusters, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    sorted_vals = values[order]
    counts = np.bincount(inverse, minlength=len(uniq))
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])

    rng = np.random.default_rng(seed)
    point = float(stat(values))
    draws = np.empty(n_boot, dtype=float)
    n_clusters = len(uniq)
    for b in range(n_boot):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        idx = np.concatenate([np.arange(starts[c], starts[c] + counts[c]) for c in pick])
        draws[b] = stat(sorted_vals[idx])
    lo, hi = np.nanpercentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return Interval(point, float(lo), float(hi), int(n_clusters))


def cluster_bootstrap_pairs(
    a_values: np.ndarray,
    b_values: np.ndarray,
    clusters: np.ndarray,
    stat: Callable[[np.ndarray, np.ndarray], float],
    n_boot: int = DEFAULT_BOOT,
    seed: int = SEED,
    alpha: float = 0.05,
) -> Interval:
    """Cluster bootstrap for a statistic of two parallel value arrays.

    Used for ratio-style statistics (mean loss per move = sum(loss)/count)
    where numerator and denominator must be resampled together.
    """
    a_values = np.asarray(a_values, dtype=float)
    b_values = np.asarray(b_values, dtype=float)
    clusters = np.asarray(clusters)
    if len(a_values) == 0:
        return Interval(float("nan"), float("nan"), float("nan"), 0)

    uniq, inverse = np.unique(clusters, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    sa, sb = a_values[order], b_values[order]
    counts = np.bincount(inverse, minlength=len(uniq))
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])

    rng = np.random.default_rng(seed)
    point = float(stat(a_values, b_values))
    draws = np.empty(n_boot, dtype=float)
    n_clusters = len(uniq)
    for b in range(n_boot):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        idx = np.concatenate([np.arange(starts[c], starts[c] + counts[c]) for c in pick])
        draws[b] = stat(sa[idx], sb[idx])
    lo, hi = np.nanpercentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return Interval(point, float(lo), float(hi), int(n_clusters))


def ols_slope(x: Sequence[float], y: Sequence[float], w: Sequence[float] | None = None) -> tuple[float, float]:
    """Weighted least-squares slope and intercept. Returns `(slope, intercept)`."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.ones_like(x) if w is None else np.asarray(w, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(w)
    x, y, w = x[mask], y[mask], w[mask]
    if len(x) < 2:
        return (float("nan"), float("nan"))
    W = w.sum()
    mx = (w * x).sum() / W
    my = (w * y).sum() / W
    sxx = (w * (x - mx) ** 2).sum()
    if sxx == 0:
        return (float("nan"), float("nan"))
    slope = (w * (x - mx) * (y - my)).sum() / sxx
    return (float(slope), float(my - slope * mx))


def bootstrap_slope(
    x: Sequence[float],
    y: Sequence[float],
    w: Sequence[float] | None = None,
    n_boot: int = DEFAULT_BOOT,
    seed: int = SEED,
    alpha: float = 0.05,
) -> Interval:
    """Percentile CI on a weighted OLS slope by resampling points."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.ones_like(x) if w is None else np.asarray(w, dtype=float)
    rng = np.random.default_rng(seed)
    point = ols_slope(x, y, w)[0]
    n = len(x)
    draws = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        draws[b] = ols_slope(x[idx], y[idx], w[idx])[0]
    lo, hi = np.nanpercentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return Interval(float(point), float(lo), float(hi), n)


def two_sided_p_from_boot(draws: np.ndarray, null: float = 0.0) -> float:
    """Bootstrap p-value for `stat != null`, floored at 1/n_boot."""
    draws = np.asarray(draws, dtype=float)
    n = len(draws)
    if n == 0:
        return float("nan")
    frac = min((draws <= null).mean(), (draws >= null).mean())
    return max(2 * frac, 1.0 / n)
