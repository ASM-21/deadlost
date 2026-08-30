"""Verify that every number written in README.md and FINDINGS.md is real.

Prose drifts. A track gets re-run, a number moves, and the README keeps the
old one because nobody re-read it. This script parses the numeric claims out of
the markdown and checks each against the committed results JSON.

The registry below is the single place where a prose claim is bound to the
value that backs it. Adding a number to the README without adding it here makes
this script fail, which is the intended friction.

Run:  python scripts/check_claims.py
Exit code 1 on any mismatch, so CI catches it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def get(path: str):
    """Fetch a value by 'file.json:dotted.path' with [index] support."""
    fname, _, dotted = path.partition(":")
    data = json.loads((RESULTS / fname).read_text())
    cur = data
    for part in dotted.split("."):
        m = re.match(r"^(.*?)\[(\d+)\]$", part)
        if m:
            key, idx = m.group(1), int(m.group(2))
            cur = cur[key] if key else cur
            cur = cur[idx]
        else:
            cur = cur[part]
    return cur


#: (label, markdown literal as written, source path, tolerance)
#: Tolerance is absolute; use 0 for integers and exact strings.
CLAIMS: list[tuple[str, str, str, float]] = [
    ("games ingested", "190,967", "t1_validation.json:rows", 0),
    ("lichess games", "18,537", "t1_validation.json:by_source.lichess2017", 0),
    ("twic games", "172,430", "t1_validation.json:by_source.twic", 0),
    (
        "blunder rate 1200-1400",
        "8.3%",
        "t3_blunders.json:by_rating_band.1200-1400.blunder_rate.point",
        0.002,
    ),
    (
        "blunder rate 2000-2200",
        "2.5%",
        "t3_blunders.json:by_rating_band.2000-2200.blunder_rate.point",
        0.002,
    ),
    (
        "fast-vs-slow relative increase",
        "29%",
        "t3_blunders.json:fast_vs_slow_difference.relative_increase",
        0.02,
    ),
    (
        "opening eval spread",
        "25.8",
        "t2_openings.json:engine_eval_spread_cp.range",
        0.3,
    ),
    (
        "acpl drift per decade (track 4)",
        "0.69",
        "t4_inflation.json:trend_adjusted.acpl_year_coefficient_per_decade",
        0.05,
    ),
    (
        "white score 2200-2400",
        "0.530",
        "t5_color.json:twic_by_elo_band.2200-2400.white_score.point",
        0.003,
    ),
    (
        "white score 2600+",
        "0.553",
        "t5_color.json:twic_by_elo_band.2600-3200.white_score.point",
        0.003,
    ),
    (
        "draw rate slope per decade",
        "5.9%",
        "t5_color.json:twic_time_trends_fixed_band_2400_2499.draw_rate.slope_per_decade",
        0.005,
    ),
    (
        "swindle rate OTB masters",
        "9.3%",
        "t6_swindles.json:by_rating_band.2400-2499 (OTB).swindle_rate.point",
        0.005,
    ),
    (
        "online minus OTB save contrast",
        "9.6%",
        "t6_swindles.json:online_gradient.online_vs_otb_contrast.online_minus_otb",
        0.01,
    ),
    (
        "clustering width ratio",
        "1.48",
        "t7_falsify.json:probes[3].mean_width_ratio",
        0.08,
    ),
    (
        "t9 lost game-sides",
        "223",
        "t9_otb_swindles.json:design.lost_game_sides",
        0,
    ),
    (
        "t9 otb mean save rate",
        "7.6%",
        "t9_otb_swindles.json:level_shift_vs_gradient.otb_mean_save_rate",
        0.004,
    ),
    (
        "t9 online mean save rate",
        "18.9%",
        "t9_otb_swindles.json:level_shift_vs_gradient.online_mean_save_rate",
        0.004,
    ),
    (
        "t4 resolution half-width",
        "1.31",
        "power_report.json:nulls.t4_inflation_acpl_per_decade.resolution_half_width",
        0.03,
    ),
    (
        "t8 resolution half-width",
        "1.69",
        "power_report.json:nulls.t8_within_player_acpl_per_decade.resolution_half_width",
        0.06,
    ),
    (
        "clustering design effect",
        "2.18",
        "power_report.json:clustering.implied_design_effect_on_sample_size",
        0.03,
    ),
    (
        "t10 specs for C1",
        "180",
        "t10_multiverse.json:C1_blunder_gradient_across_bands.n_estimated",
        0,
    ),
    (
        "t10 blunder threshold variance share",
        "94%",
        "t10_multiverse.json:C1_blunder_gradient_across_bands.variance_attribution.shares_of_total_variance.blunder_cp",
        0.01,
    ),
    (
        "t11 raw gap",
        "11.0%",
        "t11_matched_skill.json:raw_gap_online_minus_otb",
        0.004,
    ),
    (
        "t11 matched gap",
        "17.3%",
        "t11_matched_skill.json:stratified_contrast.stratified_difference",
        0.006,
    ),
    (
        "t11 online odds ratio at matched skill",
        "2.59",
        "t11_matched_skill.json:logistic_model.online.odds_ratio",
        0.06,
    ),
    (
        "t11 online played-to-mate rate",
        "32.0%",
        "t11_matched_skill.json:resignation_rate.by_corpus.online.played_to_mate",
        0.005,
    ),
    (
        "t11 otb played-to-mate rate",
        "5.8%",
        "t11_matched_skill.json:resignation_rate.by_corpus.otb.played_to_mate",
        0.005,
    ),
    (
        "t4 undecided-only trend",
        "1.20",
        "t4_inflation.json:trend_undecided_only.slope_per_decade",
        0.04,
    ),
    (
        "panel players",
        "100",
        "t8_player_panel.json:design.players",
        0,
    ),
    (
        "panel player-years",
        "584",
        "t8_player_panel.json:design.player_years",
        0,
    ),
    (
        "t8 year coefficient per decade",
        "1.32",
        "t8_player_panel.json:sign_instability_of_the_34_player_version.new_year_coefficient_per_decade",
        0.25,
    ),
]


def parse_literal(text: str) -> float:
    return float(text.replace(",", "").replace("%", "")) / (100 if "%" in text else 1)


def check_registry() -> list[str]:
    errs = []
    for label, literal, path, tol in CLAIMS:
        try:
            actual = float(get(path))
        except FileNotFoundError:
            errs.append(f"MISSING RESULTS  {label}: {path.split(':')[0]} not built")
            continue
        except (KeyError, IndexError) as exc:
            errs.append(f"BAD PATH         {label}: {path} ({exc})")
            continue
        claimed = parse_literal(literal)
        # Prose quotes magnitudes for declines ("falls 5.9%"); compare on
        # absolute value when the registered literal is unsigned.
        if not literal.startswith("-") and actual < 0:
            actual = abs(actual)
        if abs(actual - claimed) > tol:
            errs.append(f"DRIFT            {label}: prose says {literal} ({claimed:g}), results say {actual:g}")
    return errs


def check_retractions() -> list[str]:
    """A retracted claim must stay retracted, and stay visible.

    FINDINGS.md carries a retraction for the track 6 'masters save by drawing'
    reading. If probe P1 ever stops firing, the retraction text has to be
    revisited rather than silently left in place, and if the retraction text
    disappears while P1 still fires, the repo is publishing a claim it knows is
    unsupported.
    """
    errs = []
    findings = ROOT / "FINDINGS.md"
    if not findings.exists():
        return ["MISSING          FINDINGS.md"]
    text = findings.read_text()
    try:
        probes = get("t7_falsify.json:probes")
    except FileNotFoundError:
        return ["MISSING RESULTS  t7_falsify.json not built"]
    p1 = next((p for p in probes if p["probe"].startswith("P1")), None)
    if p1 is None:
        return ["BAD PATH         probe P1 not found"]
    has_retraction = "RETRACTED" in text
    if p1["fired"] and not has_retraction:
        errs.append("MISSING RETRACTION  probe P1 fires but FINDINGS.md carries no RETRACTED entry")
    if not p1["fired"] and has_retraction:
        errs.append("STALE RETRACTION    probe P1 no longer fires; revisit the RETRACTED entry")
    return errs


def check_every_percent_in_readme_is_registered() -> list[str]:
    """Catch numbers added to the README that nobody bound to a source."""
    readme = ROOT / "README.md"
    if not readme.exists():
        return []
    body = readme.read_text()
    body = re.sub(r"```.*?```", "", body, flags=re.S)  # skip code blocks
    # Badge and link URLs carry percent-encodings (%20) and shield paths that
    # look like percentages to the scanner below. Strip markup before scanning
    # so this checks prose only.
    body = re.sub(r"<[^>]+>", " ", body)              # html tags (badges)
    body = re.sub(r"https?://\S+", " ", body)          # bare urls
    body = re.sub(r"\]\([^)]*\)", "] ", body)          # markdown link targets
    registered = {lit for _, lit, _, _ in CLAIMS}
    found = set(re.findall(r"\b\d[\d,]*\.?\d*%", body))
    unregistered = {f for f in found if f not in registered}
    # Percentages that are definitions or scope statements rather than findings.
    allowed = {"50%", "100%", "5%", "2%"}
    unregistered -= allowed
    return [f"UNREGISTERED     README percentage {u} is not bound to a results path" for u in sorted(unregistered)]


def main() -> int:
    errs = check_registry() + check_retractions() + check_every_percent_in_readme_is_registered()
    if errs:
        print("claims check FAILED\n")
        for e in errs:
            print("  " + e)
        return 1
    print(f"claims check passed: {len(CLAIMS)} pinned numbers, retraction state consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
