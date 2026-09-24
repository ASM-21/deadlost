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
#: (label, literal as written in prose, source path, tolerance, expected sign)
#:
#: Expected sign is "+" or "-". Prose states magnitudes ("falls 0.71 cp per
#: decade", "rises 3.1 points"), so literals are unsigned and the sign is
#: declared here. An earlier version compared absolute values instead, which
#: meant a result that REVERSED direction but kept its magnitude would have
#: passed. That is the failure a claims check most needs to catch: the retracted
#: "draws falling" headline and its classical replacement differ in sign.
CLAIMS: list[tuple[str, str, str, float, str]] = [
    ("games ingested", "190,967", "t1_validation.json:rows", 0, "+"),
    ("lichess games", "18,537", "t1_validation.json:by_source.lichess2017", 0, "+"),
    ("twic games", "172,430", "t1_validation.json:by_source.twic", 0, "+"),
    ("classical twic games", "119,794", "t1_validation.json:twic_format_counts.classical_otb", 0, "+"),
    ("blunder rate 1200-1400", "8.3%", "t3_blunders.json:by_rating_band.1200-1400.blunder_rate.point", 0.002, "+"),
    ("blunder rate 2000-2200", "2.5%", "t3_blunders.json:by_rating_band.2000-2200.blunder_rate.point", 0.002, "+"),
    ("fast-vs-slow relative increase", "29%", "t3_blunders.json:fast_vs_slow_difference.relative_increase", 0.02, "+"),
    ("C1 specifications", "180", "t10_multiverse.json:C1_blunder_gradient_across_bands.n_estimated", 0, "+"),
    ("C1 joint p", "0.002", "t10_multiverse.json:C1_blunder_gradient_across_bands.joint_inference.p_value_two_sided", 0.004, "+"),
    ("C2 joint p", "0.052", "t10_multiverse.json:C2_fast_minus_slow_blunder_rate.joint_inference.p_value_two_sided", 0.02, "+"),
    ("C3 joint p", "0.064", "t10_multiverse.json:C3_acpl_drift_per_decade.joint_inference.p_value_two_sided", 0.03, "+"),
    ("blunder threshold variance share", "94%",
     "t10_multiverse.json:C1_blunder_gradient_across_bands.variance_attribution.shares_of_total_variance.blunder_cp", 0.01, "+"),
    ("white score 2200-2400", "0.533", "t5_color.json:twic_by_elo_band.2200-2400.white_score.point", 0.003, "+"),
    ("white score 2600+", "0.558", "t5_color.json:twic_by_elo_band.2600-3200.white_score.point", 0.003, "+"),
    ("classical draw trend per decade", "3.1%",
     "t5_color.json:twic_time_trends_fixed_band_2400_2499.draw_rate.slope_per_decade", 0.004, "+"),
    ("post-2020 draw step", "4.0%", "t5_color.json:post_2020_draw_step.2400-2499.difference", 0.004, "+"),
    ("opening eval spread", "25.3", "t2_openings.json:engine_eval_spread_cp.range", 0.3, "+"),
    ("t4 drift per decade", "0.71", "t4_inflation.json:trend_undecided_only.slope_per_decade", 0.03, "-"),
    ("t4 resolution", "1.48", "power_report.json:nulls.t4_inflation_acpl_per_decade.resolution_half_width", 0.03, "+"),
    ("t8 drift per decade", "0.47", "t8_player_panel.json:sign_instability_of_the_34_player_version.new_year_coefficient_per_decade", 0.03, "-"),
    ("t8 resolution", "1.53", "power_report.json:nulls.t8_within_player_acpl_per_decade.resolution_half_width", 0.03, "+"),
    ("panel players", "96", "t8_player_panel.json:design.players", 0, "+"),
    ("panel player-years", "470", "t8_player_panel.json:design.player_years", 0, "+"),
    ("online minus OTB save contrast", "12.9%", "t6_swindles.json:online_gradient.online_vs_otb_contrast.online_minus_otb", 0.004, "+"),
    ("t9 lost game-sides", "123", "t9_otb_swindles.json:design.lost_game_sides", 0, "+"),
    ("t9 otb mean save rate", "7.3%", "t9_otb_swindles.json:level_shift_vs_gradient.otb_mean_save_rate", 0.004, "+"),
    ("t9 online mean save rate", "18.9%", "t9_otb_swindles.json:level_shift_vs_gradient.online_mean_save_rate", 0.004, "+"),
    ("t11 raw gap", "11.3%", "t11_matched_skill.json:raw_gap_online_minus_otb", 0.004, "+"),
    ("t11 matched gap", "16.5%", "t11_matched_skill.json:stratified_contrast.stratified_difference", 0.004, "+"),
    ("t11 odds ratio", "2.47", "t11_matched_skill.json:logistic_model.online.odds_ratio", 0.03, "+"),
    ("t11 online played to mate", "32.0%", "t11_matched_skill.json:resignation_rate.by_corpus.online.played_to_mate", 0.004, "+"),
    ("t11 otb played to mate", "3.5%", "t11_matched_skill.json:resignation_rate.by_corpus.otb.played_to_mate", 0.004, "+"),
    ("t11 mate-rate difference", "28.5%", "t11_matched_skill.json:resignation_rate.difference.played_to_mate_online_minus_otb", 0.004, "+"),
    ("clustering width ratio", "1.48", "t7_falsify.json:probes[3].mean_width_ratio", 0.03, "+"),
    ("TWIC online share from 2020", "55%", "t1_validation.json:twic_format_by_era.2020_on.online", 0.006, "+"),
    ("TWIC classical share before 2020", "95.5%", "t1_validation.json:twic_format_by_era.pre_2020.classical_otb", 0.002, "+"),
    ("clustering design effect", "2.18", "power_report.json:clustering.implied_design_effect_on_sample_size", 0.03, "+"),
]


def parse_literal(text: str) -> float:
    return float(text.replace(",", "").replace("%", "")) / (100 if "%" in text else 1)


def check_registry() -> list[str]:
    errs = []
    for label, literal, path, tol, sign in CLAIMS:
        try:
            actual = float(get(path))
        except FileNotFoundError:
            errs.append(f"MISSING RESULTS  {label}: {path.split(':')[0]} not built")
            continue
        except (KeyError, IndexError) as exc:
            errs.append(f"BAD PATH         {label}: {path} ({exc})")
            continue
        claimed = parse_literal(literal)
        if sign == "-" and actual >= 0:
            errs.append(f"SIGN REVERSED    {label}: prose describes a decline, results say {actual:+g}")
            continue
        if sign == "+" and actual < 0:
            errs.append(f"SIGN REVERSED    {label}: prose describes an increase, results say {actual:+g}")
            continue
        if abs(abs(actual) - claimed) > tol:
            errs.append(f"DRIFT            {label}: prose says {literal}, results say {actual:g}")
    return errs


def check_retractions() -> list[str]:
    """Every probe that fires must be answered in FINDINGS.md's retractions table.

    An earlier version searched for the word "RETRACTED" anywhere in the file,
    which any stray use of the word would satisfy. This checks structure instead:
    a "## Retractions" section must exist, and each firing probe's identifier
    must appear inside it.
    """
    findings = ROOT / "FINDINGS.md"
    if not findings.exists():
        return ["MISSING          FINDINGS.md"]
    text = findings.read_text()
    if "## Retractions" not in text:
        return ["MISSING SECTION  FINDINGS.md has no '## Retractions' section"]
    section = text.split("## Retractions", 1)[1].split("\n## ", 1)[0]
    try:
        probes = get("t7_falsify.json:probes")
    except FileNotFoundError:
        return ["MISSING RESULTS  t7_falsify.json not built"]
    errs = []
    for pr in probes:
        pid = pr["probe"].split()[0]
        if pr.get("fired") is True and pid not in section:
            errs.append(f"UNANSWERED PROBE {pid} fires but the retractions table does not mention it")
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
    registered = {lit for _, lit, _, _, _ in CLAIMS}
    found = set(re.findall(r"\b\d[\d,]*\.?\d*%", body))
    unregistered = {f for f in found if f not in registered}
    # Percentages that are definitions or scope statements rather than findings.
    allowed = {"50%", "100%", "5%", "2%"}
    unregistered -= allowed
    return [f"UNREGISTERED     README percentage {u} is not bound to a results path" for u in sorted(unregistered)]


#: Caveats that must survive editing. Each qualifies a claim that would be
#: overstated without it. Deleting one fails the build, which is the point: a
#: caveat removed during a "tidy-up" is the commonest way a careful document
#: turns into an overclaiming one.
REQUIRED_CAVEATS = {
    "FINDINGS.md": [
        "not an independent confirmation",      # claim 5 vs Ben-Moshe & Genesove
        "joint inference across the curve",     # claim 2 is borderline, not established
        "is a bound",                           # claim 9: resignation vs time forfeit
        "itself borderline",                    # claim 9: matched-skill contrast
        "rules out only very large drift",      # claim 7: resolution
        "not a new\nresult",                   # claim 8: textbook APC
        "found by reading a paper",             # retractions 3-5 provenance
    ],
    "README.md": [
        "No prior study comparing this across formats",
        "rests on a narrow skill overlap",
    ],
}

#: Words that overclaim for an observational repository. Allowed only inside a
#: line that also negates or scopes them.
OVERCLAIM = ("proves", "proven", "definitive", "first ever", "groundbreaking", "conclusively")


def check_caveats_and_overclaiming() -> list[str]:
    errs = []
    for fname, phrases in REQUIRED_CAVEATS.items():
        path = ROOT / fname
        if not path.exists():
            continue
        text = " ".join(path.read_text().split())
        for ph in phrases:
            needle = " ".join(ph.replace("\\n", " ").split())
            if needle not in text:
                errs.append(f"CAVEAT DELETED   {fname}: missing required caveat '{needle}'")
    for fname in ("README.md", "FINDINGS.md", "docs/LITERATURE.md"):
        path = ROOT / fname
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            low = line.lower()
            for word in OVERCLAIM:
                # Word boundaries: "improves" must not match "proves".
                if re.search(r"\b" + re.escape(word) + r"\b", low) and not any(
                    neg in low for neg in ("not ", "no ", "never", "cannot")
                ):
                    errs.append(f"OVERCLAIM        {fname}:{i} uses '{word}'")
    return errs


def main() -> int:
    errs = (
        check_registry()
        + check_retractions()
        + check_every_percent_in_readme_is_registered()
        + check_caveats_and_overclaiming()
    )
    if errs:
        print("claims check FAILED\n")
        for e in errs:
            print("  " + e)
        return 1
    print(f"claims check passed: {len(CLAIMS)} pinned numbers, retraction state consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
