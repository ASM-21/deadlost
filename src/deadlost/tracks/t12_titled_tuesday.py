"""Track 12: an independent test of claim 9, and the clock-bet confound.

WHERE THIS CAME FROM. A literature and data review (September 2026) concluded
that claim 9 (lost positions are saved more online because over-the-board players
resign) appears to be new, and named its main remaining threat: in online blitz,
playing on is partly a bet on the opponent's clock. The evidence behind claim 9
could not address that, because TWIC carries no termination tag, so a loss
without checkmate might be a resignation or a time forfeit.

The same review located an archive of chess.com Titled Tuesday exports on GitHub.
Each game carries FIDE IDs, the time control, and each player's clock when the
game ended. That allows three things the existing evidence could not do:

  1. Split online losses into checkmate, time forfeit, and concession.
  2. Link the SAME players, by exact FIDE ID, to their over-the-board games in
     TWIC, a source that shares nothing with chess.com except the players.
  3. Match time control: the players' online blitz against their OVER-THE-BOARD
     BLITZ, so that the comparison isolates the medium rather than the speed.

WHAT IS AND IS NOT IDENTIFIED. Checkmate is unambiguous in both sources, so the
mate-share contrast is the clean result. "Conceded" is directly observed online
(no mate, clock above zero), but over the board TWIC still cannot separate
resignation from losing on time, so the over-the-board "non-mate" share is an
UPPER bound on over-the-board concession. Over-the-board blitz does produce time
forfeits, so the concession contrast against OTB blitz is an upper bound on its
magnitude. Both are reported as such.

Run:  python -m deadlost.tracks.t12_titled_tuesday
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import ingest_titled_tuesday as itt
from .. import paths, stats, viz
from ..eval_run import load_evals
from .t1_ingest import load_games

RAW = paths.RAW / "titled_tuesday"
DERIVED = paths.DERIVED / "titled_tuesday.parquet"
MIN_ONLINE_LOSSES = 5
MIN_OTB_LOSSES = {"classical": 5, "blitz_otb": 3}


def load_titled_tuesday(rebuild: bool = False) -> pd.DataFrame:
    if DERIVED.exists() and not rebuild:
        return pd.read_parquet(DERIVED)
    if not RAW.exists() or not any(RAW.glob("*.zip")):
        raise FileNotFoundError(
            f"no Titled Tuesday archives under {RAW}; run scripts/fetch_data.sh"
        )
    df = itt.ingest(RAW)
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DERIVED, index=False)
    return df


def termination_mix(tt: pd.DataFrame) -> dict:
    dec = tt[tt.result.isin(["1-0", "0-1"])]
    classified = dec[dec.loss_type.notna()]
    sens = {}
    for secs in (0, 1, 2, 5):
        lt = dec.apply(lambda r, s=secs: itt.classify_loss(r, s), axis=1).dropna()
        sens[f"flag_at_or_below_{secs}s"] = lt.value_counts(normalize=True).round(4).to_dict()
    return {
        "games": int(len(tt)),
        "events": int(tt.event_file.nunique()),
        "years": [int(tt.year.min()), int(tt.year.max())],
        "time_controls": tt.time_control.value_counts().head(4).to_dict(),
        "draw_rate": float((tt.result == "1/2-1/2").mean()),
        "decisive_games": int(len(dec)),
        "clock_tags_present": float(dec[["white_clock_s", "black_clock_s"]].notna().all(axis=1).mean()),
        "loser_fide_present": float(dec.loser_fide.notna().mean()),
        "loss_types": classified.loss_type.value_counts(normalize=True).round(4).to_dict(),
        "flag_threshold_sensitivity": sens,
    }


def source_agreement(tt: pd.DataFrame) -> dict:
    """Does an independent source reproduce TWIC's online checkmate share?"""
    g = load_games()
    tw_online = g[(g.source == "twic") & (g.format == "online") & (g.result != "1/2-1/2")]
    tw_share = float(tw_online.moves.str.split().str[-1].str.endswith("#").mean())
    dec = tt[tt.result.isin(["1-0", "0-1"])]
    return {
        "titled_tuesday_mate_share": float(dec.ends_in_mate.mean()),
        "twic_online_mate_share": tw_share,
        "difference": float(dec.ends_in_mate.mean() - tw_share),
        "note": (
            "Two sources with no shared pipeline: chess.com's own exports and TWIC's reports of online "
            "events. Agreement is evidence that the online figure is a property of the play, not of how "
            "either source records games."
        ),
    }


def _bootstrap_mean(x: np.ndarray, n_boot: int = 2000, seed: int = stats.SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    draws = [rng.choice(x, size=len(x), replace=True).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(lo), float(hi)


def linked_within_player(tt: pd.DataFrame) -> dict:
    """The same FIDE IDs, online (chess.com) against over the board (TWIC)."""
    on = tt[tt.loss_type.notna() & tt.loser_fide.notna()]
    online = on.groupby("loser_fide").agg(
        n_online=("loss_type", "size"),
        mate_online=("loss_type", lambda x: (x == "checkmate").mean()),
        time_online=("loss_type", lambda x: (x == "time").mean()),
        conceded_online=("loss_type", lambda x: (x == "conceded").mean()),
    )

    g = load_games()
    t = g[(g.source == "twic") & (g.result != "1/2-1/2")].copy()
    t["mate"] = t.moves.str.split().str[-1].str.endswith("#")
    t["loser_fide"] = np.where(t.result == "1-0", t.black_fide, t.white_fide)
    t = t[pd.notna(t.loser_fide)]
    is_blitz_event = t.event.str.contains("blitz", case=False, na=False)
    t["otb_kind"] = np.where(
        t.format == "classical_otb", "classical",
        np.where((t.format == "fast_otb") & is_blitz_event, "blitz_otb", None),
    )
    t = t[t.otb_kind.notna()]

    out = {}
    for kind in ("classical", "blitz_otb"):
        otb = t[t.otb_kind == kind].groupby("loser_fide").agg(n_otb=("mate", "size"), mate_otb=("mate", "mean"))
        j = online.join(otb, how="inner")
        j = j[(j.n_online >= MIN_ONLINE_LOSSES) & (j.n_otb >= MIN_OTB_LOSSES[kind])]
        if len(j) < 20:
            continue
        mate_d = (j.mate_online - j.mate_otb).values
        conc_d = (j.conceded_online - (1 - j.mate_otb)).values
        mlo, mhi = _bootstrap_mean(mate_d)
        clo, chi = _bootstrap_mean(conc_d, seed=stats.SEED + 1)
        out[f"online_vs_{kind}"] = {
            "players": int(len(j)),
            "mate_share_online": float(j.mate_online.mean()),
            "mate_share_otb": float(j.mate_otb.mean()),
            "mate_difference": float(mate_d.mean()),
            "mate_ci_lo": mlo,
            "mate_ci_hi": mhi,
            "mate_excludes_zero": bool(mlo * mhi > 0),
            "online_time_forfeit_share": float(j.time_online.mean()),
            "online_conceded_share": float(j.conceded_online.mean()),
            "otb_non_mate_share": float(1 - j.mate_otb.mean()),
            "conceded_difference_bound": float(conc_d.mean()),
            "conceded_ci_lo": clo,
            "conceded_ci_hi": chi,
            "conceded_note": (
                "Over the board, non-mate losses include time forfeits, so 'OTB non-mate' is an upper bound "
                "on OTB concession and this difference is a bound on the concession gap, not an estimate."
            ),
        }
    return out


def lichess_save_mechanism() -> dict:
    """How do online lost positions actually get saved? (Lichess, engine-identified.)

    The review recommended separating saves that come from the opponent running
    out of time from saves earned on the board. Lichess carries a termination
    tag, so for every engine-identified lost position that was eventually saved,
    the route is observable.
    """
    from .t6_swindles import LOST_CP, _entries
    from .t6_swindles import _meta as meta_lichess

    e = _entries(load_evals("lichess"), meta_lichess("lichess"), LOST_CP)
    e = e[~e.censored]
    g = load_games().set_index("game_id")
    e = e.assign(termination=g.loc[e.game_id, "termination"].values)
    saved = e[e.saved]
    won = saved[saved.saved_win]
    routes = {
        "won_because_opponent_ran_out_of_time": float((won.termination == "outoftime").sum() / len(saved)),
        "won_on_the_board": float((won.termination != "outoftime").sum() / len(saved)),
        "drawn": float(saved.saved_draw.mean()),
    }
    lost = e[~e.saved]
    return {
        "lost_game_sides": int(len(e)),
        "saved": int(len(saved)),
        "save_routes": routes,
        "how_the_rest_lost": lost.termination.value_counts(normalize=True).round(4).to_dict(),
        "reading": (
            "A large share of online saves are wins on the clock, not on the board. That does not weaken the "
            "claim that saves depend on not conceding, since a player who resigns cannot win on time, but it "
            "changes what 'saving' means online: much of it is a successful bet on the opponent's clock."
        ),
    }


def overlap_with_twic_online(tt: pd.DataFrame) -> dict:
    """How many games do the two online samples actually share?

    Both draw on the same event series, chess.com's Titled Tuesday, so it would
    be easy to assume this track merely re-reads track 11's online games. It does
    not: TWIC was sampled one issue in 26 and this archive one event in five, so
    the samples land on different weeks. Games are matched on date, both FIDE IDs
    and result, which identifies a game uniquely within an event.
    """
    games = load_games()
    tw = games[(games.source == "twic") & (games.format == "online")].dropna(
        subset=["white_fide", "black_fide"]
    ).copy()
    tw["d"] = pd.to_datetime(tw.date, errors="coerce").dt.date
    t = tt.dropna(subset=["white_fide", "black_fide"]).copy()
    t["d"] = pd.to_datetime(t.date.str.replace(".", "-"), errors="coerce").dt.date

    def keys(df):
        return set(zip(df.d, df.white_fide.astype("int64"), df.black_fide.astype("int64"), df.result, strict=True))

    k_tw, k_tt = keys(tw), keys(t)
    shared = k_tw & k_tt
    return {
        "titled_tuesday_games_with_ids": len(k_tt),
        "twic_online_games_with_ids": len(k_tw),
        "games_in_both": len(shared),
        "share_of_titled_tuesday_sample": len(shared) / len(k_tt) if k_tt else None,
        "event_dates_shared": len(set(tw.d) & set(t.d)),
        "titled_tuesday_event_dates": len(set(t.d)),
        "reading": (
            "The two online samples are nearly disjoint at the level of games, so agreement between "
            "track 11 and this track is agreement between different games, not the same games read twice."
        ),
    }


def run() -> dict:
    tt = load_titled_tuesday()
    mix = termination_mix(tt)
    agree = source_agreement(tt)
    linked = linked_within_player(tt)
    lichess = lichess_save_mechanism()
    out = {
        "source": {
            "archive": "github.com/ianrastall/titled-tuesday-archive (chess.com exports; repository MIT-licensed)",
            "sampling": "every fifth event in the archive's link list, pinned in data/titled_tuesday_events.txt",
            "why": (
                "Carries FIDE IDs and final clocks, which TWIC lacks, so online losses can be split into "
                "checkmate, time forfeit and concession, and players can be linked exactly to their "
                "over-the-board games."
            ),
        },
        "termination_mix": mix,
        "source_agreement": agree,
        "linked_within_player": linked,
        "lichess_save_mechanism": lichess,
        "overlap_with_twic_online": overlap_with_twic_online(tt),
        "conclusion": (
            "Independent of TWIC's own online coverage, the same players' losses end in checkmate far more "
            "often online than over the board, and the gap survives matching on time control (online blitz "
            "against over-the-board blitz). Online, roughly half of these players' losses are conceded with "
            "time remaining and close to a third are time forfeits, so playing on is in large part a bet on "
            "the clock. Over the board, at least nine in ten losses end without mate."
        ),
        "limits": [
            "Over-the-board concession cannot be separated from over-the-board time forfeits, so concession "
            "contrasts are bounds; only the checkmate contrast is a clean estimate.",
            "A one-in-five sample of archived events; the archive itself is described by its maintainer as "
            "incomplete.",
            "Players active in both formats are a selected, mostly titled group.",
            "Online ratings in the export are chess.com ratings and are not used.",
        ],
    }
    (paths.RESULTS / "t12_titled_tuesday.json").write_text(json.dumps(out, indent=2, default=float))
    _figure(out)
    return out


def _figure(out: dict) -> None:
    linked = out["linked_within_player"]
    rows = [(k, lab) for k, lab in (("online_vs_classical", "classical"), ("online_vs_blitz_otb", "blitz"))
            if k in linked]
    if not rows:
        return
    fig, ax = viz.new_fig(8.8, 4.8)
    cats = ["checkmate", "time forfeit", "conceded with time left"]
    colors = [viz.PALETTE[1], viz.PALETTE[4], viz.PALETTE[0]]
    ylabels, y = [], 0
    for key, lab in rows:
        v = linked[key]
        on = [v["mate_share_online"], v["online_time_forfeit_share"], v["online_conceded_share"]]
        left = 0.0
        for val, col in zip(on, colors, strict=True):
            ax.barh(y, val * 100, left=left, color=col, height=0.6)
            left += val * 100
        ylabels.append(f"Online blitz\n({v['players']} players)")
        y += 1
        left = 0.0
        ax.barh(y, v["mate_share_otb"] * 100, left=0, color=colors[0], height=0.6)
        ax.barh(y, v["otb_non_mate_share"] * 100, left=v["mate_share_otb"] * 100, color="#9aa7b4", height=0.6)
        ylabels.append(f"Same players,\nover the board {lab}")
        y += 1.6
    ax.set_yticks([0, 1, 2.6, 3.6][: len(ylabels)])
    ax.set_yticklabels(ylabels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    handles = [plt_patch(c) for c in colors] + [plt_patch("#9aa7b4")]
    ax.legend(handles, cats + ["no mate (resigned or flagged; not separable OTB)"], fontsize=7.5,
              frameon=False, loc="center left", bbox_to_anchor=(0.42, 0.5), ncol=2)
    viz.finish(
        fig, ax,
        "How the same players' losses end: online versus over the board",
        "Share of losses (%)",
        "",
        paths.figure_path("t12_how_losses_end.png"),
        note=(
            "deadlost track 12. Online: chess.com Titled Tuesday exports. Over the board: TWIC. Players linked "
            "by FIDE ID. Online losses split by the loser's final clock; over the board, resignation and time "
            "forfeit cannot be separated."
        ),
        legend=False,
    )


def plt_patch(color: str):
    from matplotlib.patches import Patch

    return Patch(color=color)


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("source_agreement", "linked_within_player")}, indent=2, default=float)[:2500])
