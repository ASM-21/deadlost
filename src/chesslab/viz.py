"""Minimal shared plot styling so every figure in the repo reads the same."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PALETTE = ["#1f4e79", "#c0504d", "#4f7942", "#7b3f99", "#b8860b", "#2f6f7f"]


def new_fig(width: float = 8.0, height: float = 5.0):
    fig, ax = plt.subplots(figsize=(width, height), dpi=150)
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return fig, ax


def finish(fig, ax, title: str, xlabel: str, ylabel: str, path: Path, note: str | None = None, legend: bool = True):
    ax.set_title(title, fontsize=11, loc="left")
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(labelsize=8)
    if legend and ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=8, frameon=False)
    if note:
        import textwrap

        # Wrap to the figure width. An unwrapped note silently runs off the
        # right edge, which is how caveats get lost.
        chars = int(fig.get_size_inches()[0] * 21)
        wrapped = "\n".join(textwrap.wrap(note, chars))
        n_lines = wrapped.count("\n") + 1
        fig.text(0.012, 0.006, wrapped, fontsize=6.5, color="#555555", va="bottom")
        fig.tight_layout(rect=(0, 0.018 * n_lines + 0.015, 1, 1))
    else:
        fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
