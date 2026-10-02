"""Run an estimate across every defensible analytic choice, not just one.

THE PROBLEM THIS ADDRESSES. Building the earlier tracks required dozens of
judgement calls: where a blunder threshold sits, how many opening plies count
as book, whether centipawn loss is winsorised and at what level, how long a
game has to be to count, where rating bands are cut. Each was defensible.
Reporting one path through them is still a garden of forking paths, and the
reader has no way to tell whether a finding is robust or whether it is the one
combination that produced it.

A specification curve fixes that by refusing to choose. Enumerate the
reasonable settings for each decision, run every combination, and report the
whole distribution of answers. Three things then become visible that a single
specification hides:

1. **Sign stability.** What share of defensible specifications agree with the
   headline? A finding that holds in 98% of them is different from one that
   holds in 55%.
2. **Which decisions matter.** Variance in the estimate is attributed back to
   the choices that drove it. If one arbitrary threshold explains most of the
   spread, that threshold deserved an argument rather than a default.
3. **Whether the reported specification is typical or extreme.** Its percentile
   rank within the curve answers directly whether the headline was cherry-picked,
   even unintentionally.

WHAT THIS IS NOT. A specification curve does not fix a confound, and it does
not make an underpowered null informative: every specification runs on the same
data, so the results are heavily correlated and the spread is not a confidence
interval. It answers "does this survive my arbitrary choices", not "is this
true".
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Decision:
    """One analytic choice and the settings considered defensible for it."""

    name: str
    options: Sequence
    rationale: str = ""

    def as_dict(self) -> dict:
        return {"name": self.name, "options": list(self.options), "rationale": self.rationale}


def enumerate_specs(decisions: Sequence[Decision]) -> list[dict]:
    """Cartesian product of all decisions, as a list of setting dicts."""
    keys = [d.name for d in decisions]
    return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*[d.options for d in decisions])]


def run_curve(
    decisions: Sequence[Decision],
    estimator: Callable[[dict], float | None],
    headline: dict | None = None,
) -> dict:
    """Evaluate `estimator` over every specification and summarise the spread.

    `estimator` receives one settings dict and returns a scalar, or None when
    that combination leaves too little data to estimate. Returning None is
    expected and is counted separately rather than treated as zero.
    """
    specs = enumerate_specs(decisions)
    rows = []
    for spec in specs:
        try:
            val = estimator(spec)
        except Exception:  # noqa: BLE001
            val = None
        rows.append({**spec, "estimate": val})
    df = pd.DataFrame(rows)
    ok = df[df.estimate.notna()].copy()

    if ok.empty:
        return {"error": "no specification produced an estimate", "n_specs": len(specs)}

    vals = ok.estimate.values.astype(float)
    med = float(np.median(vals))
    sign = np.sign(med)
    share_same_sign = float((np.sign(vals) == sign).mean())

    headline_val = None
    headline_pct = None
    if headline is not None:
        match = ok
        for k, v in headline.items():
            if k in match.columns:
                match = match[match[k] == v]
        if len(match) == 1:
            headline_val = float(match.estimate.iloc[0])
            headline_pct = float((vals <= headline_val).mean())

    return {
        "n_specs": len(specs),
        "n_estimated": int(len(ok)),
        "n_undefined": int(len(df) - len(ok)),
        "median": med,
        "mean": float(vals.mean()),
        "min": float(vals.min()),
        "max": float(vals.max()),
        "p05": float(np.percentile(vals, 5)),
        "p95": float(np.percentile(vals, 95)),
        "share_same_sign_as_median": share_same_sign,
        "share_positive": float((vals > 0).mean()),
        "headline_estimate": headline_val,
        "headline_percentile_in_curve": headline_pct,
        "decisions": [d.as_dict() for d in decisions],
        "variance_attribution": variance_attribution(ok, [d.name for d in decisions]),
        "estimates": ok.to_dict(orient="records"),
    }


def variance_attribution(df: pd.DataFrame, decision_names: Sequence[str]) -> dict:
    """How much of the spread does each decision account for?

    Uses the between-group sum of squares for each decision taken alone, as a
    share of total. Decisions are not orthogonal in general, so these shares do
    not sum to one and are a ranking rather than a partition. Reported that way
    on purpose: the useful question is "which knob moved the answer most",
    not an exact decomposition.
    """
    vals = df.estimate.values.astype(float)
    total_ss = float(((vals - vals.mean()) ** 2).sum())
    out = {}
    for name in decision_names:
        if name not in df.columns or df[name].nunique() < 2:
            continue
        between = 0.0
        for _, grp in df.groupby(name):
            g = grp.estimate.values.astype(float)
            between += len(g) * (g.mean() - vals.mean()) ** 2
        out[name] = float(between / total_ss) if total_ss > 0 else float("nan")
    return {
        "shares_of_total_variance": dict(sorted(out.items(), key=lambda kv: -kv[1])),
        "note": (
            "Between-group sum of squares per decision, as a share of total. Decisions are not "
            "orthogonal, so shares need not sum to 1. Use as a ranking of which choice moved the "
            "answer most."
        ),
    }


def curve_figure(curve: dict, decisions: Sequence[Decision], title: str, ylabel: str, path, note: str = ""):
    """Sorted estimates on top, the settings that produced them underneath.

    This is the standard specification-curve layout: every specification is one
    x position, ordered by its estimate, so the reader can see at a glance how
    much of the curve sits on either side of zero and which settings cluster
    where.
    """
    import matplotlib.pyplot as plt

    rows = pd.DataFrame(curve["estimates"]).sort_values("estimate").reset_index(drop=True)
    names = [d.name for d in decisions if d.name in rows.columns and rows[d.name].nunique() > 1]
    n_opts = sum(rows[n].nunique() for n in names)

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(9.0, 5.2 + 0.16 * n_opts), dpi=150,
        gridspec_kw={"height_ratios": [3, max(1.2, 0.11 * n_opts)]}, sharex=True,
    )
    x = np.arange(len(rows))
    colors = ["#c0504d" if v < 0 else "#1f4e79" for v in rows.estimate]
    ax.scatter(x, rows.estimate, s=7, c=colors)
    ax.axhline(0, color="#888888", lw=0.9, ls="--")
    if curve.get("headline_estimate") is not None:
        ax.axhline(curve["headline_estimate"], color="#b8860b", lw=1.1,
                   label=f"reported specification ({curve['headline_estimate']:.4g})")
        ax.legend(fontsize=8, frameon=False)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=11, loc="left")
    ax.grid(True, alpha=0.25, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    ticks, labels = [], []
    row_i = 0
    for name in names:
        for opt in sorted(rows[name].unique(), key=str):
            mask = (rows[name] == opt).values
            ax2.scatter(x[mask], np.full(mask.sum(), row_i), s=3, c="#333333")
            ticks.append(row_i)
            labels.append(f"{name}={opt}")
            row_i += 1
    ax2.set_yticks(ticks)
    ax2.set_yticklabels(labels, fontsize=6.5)
    ax2.set_ylim(-1, row_i)
    ax2.invert_yaxis()
    ax2.set_xlabel("Specification, ordered by estimate", fontsize=9)
    ax2.grid(True, axis="x", alpha=0.2, lw=0.5)
    for side in ("top", "right", "left"):
        ax2.spines[side].set_visible(False)

    if note:
        import textwrap

        wrapped = "\n".join(textwrap.wrap(note, 150))
        fig.text(0.012, 0.006, wrapped, fontsize=6.5, color="#555555", va="bottom")
        fig.tight_layout(rect=(0, 0.02 * (wrapped.count("\n") + 1) + 0.012, 1, 1))
    else:
        fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
