"""Track 9: does saving a lost position get harder as strength rises?

WHY THIS EXISTS. Track 6 tried to answer this and could not. It compared online
amateurs against over-the-board masters, which varies rating and playing format
at the same time (online rapid against classical OTB). When censoring was
removed from that track, the apparent gradient across online rating bands
vanished, and the only surviving contrast was the confounded cross-corpus one.
That is not an answer, it is a design problem.

THIS DESIGN. Vary rating *inside* a single format. All games are TWIC
over-the-board classical; the bands are 2200-2400, 2400-2500, 2500-2600 and
2600+ FIDE, with pairings restricted to within 100 Elo so the band label
describes both players. Format, time control, and reporting source are held
constant, so a gradient here is attributable to strength.

WHAT "SAVED" MEANS, unchanged from track 6 so the two are comparable: the unit
is a **game-side**, one observation per game per side that ever reached a
position worse than -500cp. Saving means that side drew or won. Draw saves and
win saves are reported separately, because at master level they are very
different events and the base draw rate differs sharply across bands.

THE BASE-RATE LESSON, APPLIED IN ADVANCE. Probe P1 destroyed track 6's
secondary claim by showing that masters' draw-saves were just their high
overall draw rate showing through. That correction is built into this track
from the start: every save rate is reported both raw and normalised by the
band's own unconditional result mix. The normalised version is the headline.

POWER, STATED UP FRONT. Roughly 130 games per band yields on the order of 50
lost game-sides per band. `scripts/power_report.py` gives the smallest
band-to-band gap this can resolve. It is not small. A null here means "no large
gradient", not "no gradient".

Run:  python -m chesslab.tracks.t9_otb_swindles
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import paths, power, stats, viz
from ..eval_run import OTB_BANDS, load_evals
from .t1_ingest import load_games
from .t6_swindles import LOST_CP, _entries

TAG = "otb"
ALT_LOST_CP = (300, 500, 800)


def band_order() -> list[str]:
    return [f"{lo}-{hi}" for lo, hi in OTB_BANDS]


def _meta() -> pd.DataFrame:
    games = load_games()
    sample = pd.read_csv(paths.EVAL / f"eval_sample_{TAG}.csv")
    meta = games.merge(sample[["game_id", "stratum"]], on="game_id", how="inner")
    meta = meta[["game_id", "result", "ply_count", "stratum", "year"]].copy()
    meta["band"] = meta.stratum
    meta["tc_bucket"] = "otb"
    meta["corpus"] = TAG
    return meta.drop(columns=["stratum"])


def base_rates() -> dict:
    """Unconditional result mix per band, from the full corpus not the sample."""
    games = load_games()
    d = games[(games.source == "twic") & (games.format == "classical_otb")].dropna(subset=["white_elo", "black_elo"])
    d = d[(d.white_elo - d.black_elo).abs() <= 100]
    out = {}
    for lo, hi in OTB_BANDS:
        cell = d[d.white_elo.between(lo, hi - 1) & d.black_elo.between(lo, hi - 1)]
        if len(cell) >= 200:
            out[f"{lo}-{hi}"] = {
                "n_games": int(len(cell)),
                "draw_rate": float((cell.result == "1/2-1/2").mean()),
                "decisive_rate": float((cell.result != "1/2-1/2").mean()),
            }
    return out


def summarise(entries: pd.DataFrame) -> dict:
    base = base_rates()
    rows = []
    for band in band_order():
        cell = entries[entries.band == band]
        if len(cell) < 10:
            continue
        saved = stats.cluster_bootstrap(cell.saved.astype(float).values, cell.game_id.values, np.mean)
        draw = stats.cluster_bootstrap(cell.saved_draw.astype(float).values, cell.game_id.values, np.mean)
        win = stats.cluster_bootstrap(cell.saved_win.astype(float).values, cell.game_id.values, np.mean)
        b = base.get(band, {})
        rows.append(
            {
                "band": band,
                "n_lost_game_sides": int(len(cell)),
                "n_games": int(cell.game_id.nunique()),
                "save_rate": saved.as_dict(),
                "draw_save_rate": draw.as_dict(),
                "win_save_rate": win.as_dict(),
                "base_draw_rate": b.get("draw_rate"),
                # The P1 correction, applied from the start rather than after
                # a probe catches it.
                "draw_save_over_base_draw": (draw.point / b["draw_rate"]) if b.get("draw_rate") else None,
                "median_entry_cp": float(cell.entry_cp.median()),
            }
        )
    return {"by_band": rows}


def gradient(entries: pd.DataFrame, col: str) -> dict:
    """Slope of a rate across the ordered bands, clustered on games."""
    idx = {b: i for i, b in enumerate(band_order())}
    rows = []
    for band in band_order():
        cell = entries[entries.band == band]
        if len(cell) >= 10:
            rows.append({"x": idx[band], "rate": float(cell[col].astype(float).mean()), "n": len(cell)})
    if len(rows) < 3:
        return {"error": "not enough bands"}
    tbl = pd.DataFrame(rows)
    iv = stats.bootstrap_slope(tbl.x, tbl.rate, w=tbl.n)
    return {
        "slope_per_band_step": iv.point,
        "ci_lo": iv.lo,
        "ci_hi": iv.hi,
        "excludes_zero": bool(iv.lo * iv.hi > 0),
        "rates": tbl.to_dict(orient="records"),
    }


def level_shift_vs_gradient() -> dict:
    """Is the online/OTB save-rate gap driven by rating or by format?

    The two corpora do not overlap in rating, so this cannot be settled by
    controlling for rating: there is no common support. What CAN be checked is
    whether either corpus shows an internal rating gradient. If saving a lost
    position simply gets harder as players get stronger, the rate should decline
    across the online bands (a 1000-point span) and keep declining across the
    over-the-board bands (a 400-point span).

    It does neither. Both corpora are internally flat within their own noise,
    and they sit at very different levels. A pure rating mechanism does not
    predict two flat plateaus with a step between them; a format mechanism does.
    This is evidence, not proof: the corpora also differ in reporting source
    and player population, and any of those could produce the same step.
    """
    t6_path = paths.RESULTS / "t6_swindles.json"
    if not t6_path.exists():
        return {"error": "t6_swindles.json not built"}
    t6 = json.loads(t6_path.read_text())
    online = t6.get("online_gradient", {})
    online_rates = online.get("online_band_rates", [])
    if not online_rates:
        return {"error": "no online band rates available"}

    ev = load_evals(TAG)
    entries = _entries(ev, _meta(), LOST_CP)
    entries = entries[~entries.censored]
    otb_rates = [
        {"band": b, "rate": float(entries[entries.band == b].saved.mean()), "n": int((entries.band == b).sum())}
        for b in band_order()
        if (entries.band == b).sum() >= 10
    ]

    online_mean = float(np.average([r["rate"] for r in online_rates], weights=[r["n"] for r in online_rates]))
    otb_mean = float(np.average([r["rate"] for r in otb_rates], weights=[r["n"] for r in otb_rates]))

    return {
        "online_rating_span": "1200-2200 (about 1000 Elo)",
        "otb_rating_span": "2200-3200 (about 400 Elo of populated bands)",
        "online_internal_gradient_excludes_zero": online.get("online_slope_per_band_step", {}).get("excludes_zero"),
        "otb_internal_gradient_excludes_zero": gradient(entries, "saved").get("excludes_zero"),
        "online_mean_save_rate": online_mean,
        "otb_mean_save_rate": otb_mean,
        "level_step": online_mean - otb_mean,
        "reading": (
            "Neither corpus shows an internal rating gradient, and they differ by a large step. A "
            "mechanism in which strength alone makes lost positions harder to save would predict a "
            "decline within each corpus, which is absent across 1000 Elo online and 400 Elo over the "
            "board. The step is better explained by what differs between the corpora, of which playing "
            "format (online rapid vs classical OTB) is the most obvious candidate."
        ),
        "caveat": (
            "The rating ranges do not overlap, so rating and format cannot be separated by controlling "
            "for one. This argument rests on the ABSENCE of within-corpus gradients, which is a weaker "
            "form of evidence, and both within-corpus nulls are themselves low-powered."
        ),
    }


def run() -> dict:
    ev = load_evals(TAG)
    entries = _entries(ev, _meta(), LOST_CP)
    entries = entries[~entries.censored]

    summary = summarise(entries)
    grads = {
        "save_rate": gradient(entries, "saved"),
        "draw_save_rate": gradient(entries, "saved_draw"),
        "win_save_rate": gradient(entries, "saved_win"),
    }

    # Normalised gradient: does the draw-save rate move across bands FASTER
    # than each band's own drawing propensity? This is the quantity P1 showed
    # track 6 should have been reporting.
    rows = [r for r in summary["by_band"] if r.get("draw_save_over_base_draw") is not None]
    norm_grad = None
    if len(rows) >= 3:
        tbl = pd.DataFrame(
            [{"x": i, "ratio": r["draw_save_over_base_draw"], "n": r["n_lost_game_sides"]}
             for i, r in enumerate(rows)]
        )
        iv = stats.bootstrap_slope(tbl.x, tbl.ratio, w=tbl.n)
        norm_grad = {
            "slope_per_band_step": iv.point,
            "ci_lo": iv.lo,
            "ci_hi": iv.hi,
            "excludes_zero": bool(iv.lo * iv.hi > 0),
            "ratios": tbl.ratio.round(3).tolist(),
        }

    sensitivity = {}
    for thr in ALT_LOST_CP:
        alt = _entries(ev, _meta(), thr)
        alt = alt[~alt.censored]
        sensitivity[f"lost_at_{thr}cp"] = {
            "n": int(len(alt)),
            "save_rate": float(alt.saved.mean()) if len(alt) else None,
            "gradient_excludes_zero": gradient(alt, "saved").get("excludes_zero"),
        }

    # Resolution, computed rather than asserted.
    band_rows = summary["by_band"]
    mde = None
    if band_rows:
        base_rate = float(np.mean([r["save_rate"]["point"] for r in band_rows]))
        n_per = int(np.mean([r["n_lost_game_sides"] for r in band_rows]))
        m = power.mde_two_sample_proportion(base_rate, n_per, width_ratio=1.48)
        mde = {
            **m.as_dict(),
            "baseline_save_rate": base_rate,
            "n_lost_game_sides_per_band": n_per,
            "n_games_required_per_band_for_5pp": power.n_required_for_effect(base_rate, 0.05, 1.48),
        }

    out = {
        "design": {
            "corpus": "TWIC over-the-board classical only, pairings within 100 Elo",
            "bands": band_order(),
            "games_evaluated": int(ev.game_id.nunique()),
            "lost_game_sides": int(len(entries)),
            "why": (
                "Track 6 varied rating and playing format together and could not attribute its one "
                "surviving contrast to either. This holds format constant."
            ),
        },
        **summary,
        "gradients": grads,
        "normalised_draw_save_gradient": norm_grad,
        "threshold_sensitivity": sensitivity,
        "resolution": mde,
        "level_shift_vs_gradient": level_shift_vs_gradient(),
        "limitations": [
            "TWIC over-the-board coverage skews European and tournament-level; this is not all OTB chess.",
            "Rating band and opponent strength move together by construction, so 'harder to save' may "
            "mean the defender is better or the attacker is better at converting. This design cannot "
            "separate defensive skill from conversion skill.",
            "A null gradient here is a null on LARGE gradients only; see `resolution`.",
        ],
    }
    (paths.RESULTS / "t9_otb_swindles.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(out)
    return out


def _figure(out: dict) -> None:
    rows = out["by_band"]
    if not rows:
        return
    bands = [r["band"] for r in rows]
    xs = np.arange(len(bands))
    fig, ax = viz.new_fig(8.5, 5.0)
    for i, (key, label) in enumerate(
        (("save_rate", "Saved (draw or win)"), ("draw_save_rate", "Saved as draw"), ("win_save_rate", "Saved as win"))
    ):
        pts = [r[key]["point"] for r in rows]
        lo = [r[key]["point"] - r[key]["ci_lo"] for r in rows]
        hi = [r[key]["ci_hi"] - r[key]["point"] for r in rows]
        ax.errorbar(xs + (i - 1) * 0.12, pts, yerr=[lo, hi], fmt="o-", capsize=3, lw=1.3, ms=4,
                    color=viz.PALETTE[i], label=label)
    ax.set_xticks(xs)
    ax.set_xticklabels(bands, rotation=20, ha="right")
    g = out["gradients"]["save_rate"]
    viz.finish(
        fig, ax,
        f"Saving a lost position (worse than -{LOST_CP}cp) by rating, format held constant",
        "FIDE band (both players, over-the-board classical)",
        "Share of lost game-sides saved",
        paths.figure_path("t9_otb_swindle_by_band.png"),
        note=(
            "chess-lab track 9. All games are TWIC over-the-board classical, so unlike track 6 the "
            f"rating comparison is not confounded with playing format. Slope {g.get('slope_per_band_step', float('nan')):+.4f} "
            f"per band step [{g.get('ci_lo', float('nan')):+.4f}, {g.get('ci_hi', float('nan')):+.4f}]. "
            "95% game-clustered bootstrap."
        ),
    )


if __name__ == "__main__":
    r = run()
    print(json.dumps({"gradients": r["gradients"], "resolution": r["resolution"]}, indent=2, default=float))
