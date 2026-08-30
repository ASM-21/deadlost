"""Track 6: how often is a clearly lost position actually saved?

QUESTION. Take positions the engine judges as decisively lost. How often does
the losing side still draw or win, and does that rate vary by rating band and
time control?

DEFINITION. A game "enters a lost state" for a side at the first evaluated
move where the position sits at or beyond `LOST_CP` against them. The unit of
analysis is a **game-side**, not a position: a game where White is lost on
move 20 and again on move 34 contributes one observation, not two. Counting
positions would weight long grinds more heavily than sharp collapses and would
badly overstate the sample size.

WHAT COUNTS AS A SAVE. Drawing or winning from that point. Both are reported
separately, because a draw from a lost position and a win from a lost position
are very different events and lumping them hides which one is moving.

THE ATTRIBUTION LIMIT. The track prompt asked whether we can separate
"opponent blundered back" from "defender found hard moves". The eval
trajectory can tell us *where the evaluation moved*, but attributing that to
defensive brilliance rather than to the opponent losing the thread requires
knowing what the opponent could see, which no post-hoc eval provides. What is
reported instead is a purely descriptive split: whether the recovery came in
one large swing on a single opponent move, or accumulated over several. That
is a fact about the eval trace, not a claim about who deserves credit.

CENSORING, WHICH MATTERS. Evaluation stops at `max_ply` (120 by default), so
a game still running at that point has an unobserved ending. Those game-sides
are excluded and counted, rather than being silently treated as losses, which
would bias the swindle rate downward.

Run:  python -m chesslab.tracks.t6_swindles
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import paths, stats, viz
from ..eval_run import load_evals
from .t1_ingest import load_games

LOST_CP = 500
ALT_LOST_CP = (300, 500, 800)


def _entries(ev: pd.DataFrame, meta: pd.DataFrame, lost_cp: int) -> pd.DataFrame:
    """One row per (game, side) that ever reached a lost position."""
    df = ev.merge(meta, on="game_id", how="inner")
    rows = []
    for gid, cell in df.groupby("game_id"):
        cell = cell.sort_values("ply")
        m = cell.iloc[0]
        last_ply_evaluated = int(cell.ply.max())
        game_last_ply = int(m.ply_count) - 1
        censored = last_ply_evaluated < game_last_ply

        for side in ("white", "black"):
            sign = 1 if side == "white" else -1
            # Evaluation is White-POV; side is lost when sign*cp <= -lost_cp.
            lost = cell[sign * cell.cp_before <= -lost_cp]
            if lost.empty:
                continue
            first = lost.iloc[0]
            saved_draw = m.result == "1/2-1/2"
            saved_win = (m.result == "1-0" and side == "white") or (m.result == "0-1" and side == "black")

            after = cell[cell.ply >= first.ply]
            evals = (sign * after.cp_before).values
            recovered = evals.max() if len(evals) else np.nan
            # Largest single-move improvement for the lost side after entry.
            deltas = np.diff(evals) if len(evals) > 1 else np.array([0.0])
            rows.append(
                {
                    "game_id": gid,
                    "side": side,
                    "entry_ply": int(first.ply),
                    "entry_cp": float(sign * first.cp_before),
                    "result": m.result,
                    "saved": bool(saved_draw or saved_win),
                    "saved_draw": bool(saved_draw),
                    "saved_win": bool(saved_win),
                    "censored": bool(censored),
                    "best_recovery_cp": float(recovered),
                    "largest_single_swing_cp": float(deltas.max()) if len(deltas) else 0.0,
                    "moves_after_entry": int(len(after)),
                    "band": m.get("band"),
                    "tc_bucket": m.get("tc_bucket"),
                    "year": m.get("year"),
                    "corpus": m.get("corpus"),
                }
            )
    return pd.DataFrame(rows)


def _meta(tag: str) -> pd.DataFrame:
    games = load_games()
    sample = pd.read_csv(paths.EVAL / f"eval_sample_{tag}.csv")
    meta = games.merge(sample[["game_id", "stratum"]], on="game_id", how="inner")
    meta = meta[["game_id", "result", "ply_count", "stratum", "white_band", "year"]].copy()
    if tag == "lichess":
        meta["band"] = meta.white_band
        meta["tc_bucket"] = meta.stratum.str.split("|").str[1]
    else:
        meta["band"] = "2400-2499 (OTB)"
        meta["tc_bucket"] = "otb"
    meta["corpus"] = tag
    return meta.drop(columns=["white_band", "stratum"])


def rate(d: pd.DataFrame, col: str) -> dict:
    if d.empty:
        return {}
    # Cluster on game: White-lost and Black-lost in the same game are not
    # independent observations.
    return stats.cluster_bootstrap(d[col].astype(float).values, d.game_id.values, np.mean).as_dict()


def summarise(entries: pd.DataFrame, group: str | None) -> dict:
    live = entries[~entries.censored]
    if group is None:
        cells = {"all": live}
    else:
        cells = {str(k): v for k, v in live.groupby(group)}
    out = {}
    for key, cell in cells.items():
        if len(cell) < 10:
            continue
        out[key] = {
            "n_lost_game_sides": int(len(cell)),
            "n_games": int(cell.game_id.nunique()),
            "swindle_rate": rate(cell, "saved"),
            "draw_save_rate": rate(cell, "saved_draw"),
            "win_save_rate": rate(cell, "saved_win"),
            "median_entry_cp": float(cell.entry_cp.median()),
        }
    return out


def online_gradient(entries: pd.DataFrame) -> dict:
    """Is there a real trend across the ONLINE bands, or only an online/OTB gap?

    With censoring removed the online band rates stopped being monotone, so the
    earlier "falls with rating" reading has to be tested rather than read off
    the point estimates. This fits a slope across the online bands only, and
    separately tests the online-vs-OTB contrast, because those are two different
    claims and only one of them survives.
    """
    live = entries[~entries.censored]
    online = live[live.band.str.contains("-") & ~live.band.str.contains("OTB")]
    order = sorted(online.band.unique(), key=lambda b: int(b.split("-")[0]))
    idx = {b: i for i, b in enumerate(order)}

    rows = []
    for band in order:
        cell = online[online.band == band]
        rows.append({"band": band, "x": idx[band], "rate": float(cell.saved.mean()), "n": len(cell)})
    tbl = pd.DataFrame(rows)
    slope = stats.bootstrap_slope(tbl.x, tbl.rate, w=tbl.n)

    otb = live[live.band.str.contains("OTB")]
    contrast = None
    if len(otb) >= 10 and len(online) >= 10:
        pooled = pd.concat([online.assign(grp=1.0), otb.assign(grp=0.0)])

        def stat(vals, grps):
            a, b = vals[grps == 1], vals[grps == 0]
            return float(a.mean() - b.mean()) if len(a) and len(b) else np.nan

        iv = stats.cluster_bootstrap_pairs(
            pooled.saved.astype(float).values, pooled.grp.values, pooled.game_id.values, stat
        )
        contrast = {
            "online_minus_otb": iv.point,
            "ci_lo": iv.lo,
            "ci_hi": iv.hi,
            "excludes_zero": bool(iv.lo * iv.hi > 0),
        }

    return {
        "online_band_rates": tbl.to_dict(orient="records"),
        "online_slope_per_band_step": {
            "point": slope.point,
            "ci_lo": slope.lo,
            "ci_hi": slope.hi,
            "excludes_zero": bool(slope.lo * slope.hi > 0),
        },
        "online_vs_otb_contrast": contrast,
        "reading": (
            "The online bands are not distinguishable from one another: every interval overlaps every "
            "other and the fitted slope across them includes zero. The separation that does survive is "
            "online amateur versus over-the-board master, which conflates rating with playing "
            "conditions (rapid online vs classical OTB) and cannot be attributed to rating alone."
        ),
    }


def run() -> dict:
    frames = []
    for tag in ("lichess", "twic"):
        try:
            ev = load_evals(tag)
        except FileNotFoundError:
            continue
        frames.append(_entries(ev, _meta(tag), LOST_CP))
    if not frames:
        raise FileNotFoundError("no engine evaluations available for track 6")
    entries = pd.concat(frames, ignore_index=True)

    censoring = {
        "total_lost_game_sides": int(len(entries)),
        "censored_excluded": int(entries.censored.sum()),
        "censored_share": float(entries.censored.mean()),
        "note": (
            "Censored game-sides reached a lost position but the game was still running when "
            "evaluation stopped at max_ply. Excluding them is conservative in an unknown direction; "
            "keeping them as losses would bias the swindle rate down."
        ),
    }

    live = entries[~entries.censored]
    # Descriptive recovery shape, NOT an attribution of credit.
    recovered = live[live.saved]
    shape = {
        "note": (
            "Descriptive only. A large single swing means the evaluation moved mostly on one "
            "opponent move; it does not establish that the opponent blundered rather than that "
            "the defender set a problem. This repo does not claim to separate those."
        ),
        "median_largest_single_swing_cp": float(recovered.largest_single_swing_cp.median()) if len(recovered) else None,
        "share_of_saves_with_swing_over_300cp": float((recovered.largest_single_swing_cp >= 300).mean())
        if len(recovered)
        else None,
        "median_moves_after_entry": float(recovered.moves_after_entry.median()) if len(recovered) else None,
    }

    sensitivity = {}
    for thr in ALT_LOST_CP:
        alt = []
        for tag in ("lichess", "twic"):
            try:
                alt.append(_entries(load_evals(tag), _meta(tag), thr))
            except FileNotFoundError:
                continue
        a = pd.concat(alt, ignore_index=True)
        a = a[~a.censored]
        sensitivity[f"lost_at_{thr}cp"] = {
            "n": int(len(a)),
            "swindle_rate": float(a.saved.mean()) if len(a) else None,
        }

    out = {
        "definitions": {
            "lost_cp": LOST_CP,
            "unit": "game-side (a game where one side reached a lost position), not position",
            "saved": "that side drew or won the game",
        },
        "censoring": censoring,
        "overall": summarise(entries, None),
        "by_rating_band": summarise(entries, "band"),
        "by_time_bucket": summarise(entries, "tc_bucket"),
        "by_corpus": summarise(entries, "corpus"),
        "online_gradient": online_gradient(entries),
        "recovery_shape": shape,
        "threshold_sensitivity": sensitivity,
    }
    (paths.RESULTS / "t6_swindles.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(out)
    return out


def _figure(out: dict) -> None:
    bands = {k: v for k, v in out["by_rating_band"].items() if k != "2400-2499 (OTB)"}
    order = sorted(bands, key=lambda b: int(b.split("-")[0]))
    if "2400-2499 (OTB)" in out["by_rating_band"]:
        order.append("2400-2499 (OTB)")
        bands["2400-2499 (OTB)"] = out["by_rating_band"]["2400-2499 (OTB)"]
    if not order:
        return
    fig, ax = viz.new_fig(8.0, 5.0)
    xs = np.arange(len(order))
    for i, (key, label) in enumerate((("draw_save_rate", "Saved as draw"), ("win_save_rate", "Saved as win"))):
        pts = [bands[b][key]["point"] for b in order]
        lo = [bands[b][key]["point"] - bands[b][key]["ci_lo"] for b in order]
        hi = [bands[b][key]["ci_hi"] - bands[b][key]["point"] for b in order]
        ax.errorbar(xs + (i - 0.5) * 0.12, pts, yerr=[lo, hi], fmt="o", capsize=3, color=viz.PALETTE[i], label=label)
    ax.set_xticks(xs)
    ax.set_xticklabels(order, rotation=25, ha="right")
    viz.finish(
        fig,
        ax,
        f"Rate of saving a position the engine scores as lost (worse than -{LOST_CP}cp)",
        "Rating band",
        "Share of lost game-sides saved",
        paths.figure_path("t6_swindle_rate.png"),
        note="chess-lab track 6. Unit is game-side. Censored game-sides excluded. 95% game-clustered bootstrap.",
    )


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("overall", "censoring", "threshold_sensitivity")}, indent=2, default=float))
