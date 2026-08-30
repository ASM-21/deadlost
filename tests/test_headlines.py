"""Headline pins.

Every number this repo asserts in its README or FINDINGS is pinned here
against the committed `results/*.json`. These tests do not recompute the
analysis; they assert that the published numbers still say what the prose
claims they say. If a track is re-run and a headline moves, the test fails and
the prose has to be updated deliberately rather than drifting silently.

Tolerances are set to the precision actually claimed in the prose, not to
floating-point equality: the point is to catch a finding changing, not to
break on the last decimal place.

Tests skip (not fail) when a results file is absent, so a fresh clone without
the corpus can still run the suite.
"""

from __future__ import annotations

import json

import pytest

from chesslab import paths


def _load(name: str) -> dict:
    p = paths.RESULTS / name
    if not p.exists():
        pytest.skip(f"{name} not built; run scripts/build_all.sh")
    return json.loads(p.read_text())


# --------------------------------------------------------------------------
# track 1: ingestion scope
# --------------------------------------------------------------------------


def test_t1_corpus_sizes():
    d = _load("t1_validation.json")
    assert d["by_source"]["lichess2017"] == 18537
    assert d["by_source"]["twic"] == 172430
    assert d["rows"] == 190967


def test_t1_no_illegal_move_sequences_admitted():
    d = _load("t1_validation.json")
    li = d["reports"]["lichess2017"]
    assert li["legality_failed"] == 0
    assert li["legality_checked"] == li["admitted"]


def test_t1_twic_spans_the_claimed_years():
    d = _load("t1_validation.json")
    lo, hi = d["twic_year_span"]
    assert lo == 1998 and hi == 2026


def test_t1_lichess_is_overwhelmingly_slow():
    """The scope limitation that forced track 3 to be re-scoped."""
    d = _load("t1_validation.json")
    counts = d["lichess_tc_class_counts"]
    fast = counts.get("bullet", 0) + counts.get("ultrabullet", 0)
    assert fast / sum(counts.values()) < 0.02


# --------------------------------------------------------------------------
# track 2: openings
# --------------------------------------------------------------------------


def test_t2_engine_eval_range_is_narrow():
    """The claim: mainline openings differ by well under half a pawn."""
    d = _load("t2_openings.json")
    assert d["engine_eval_spread_cp"]["range"] < 50


def test_t2_no_band_survives_multiplicity_correction():
    """The headline null, stated correctly.

    One band (2600+) is nominally significant at p<0.05 with a NEGATIVE rho,
    i.e. pointing away from the folk claim. With six bands tested that is close
    to what chance produces, and it does not survive Holm-Bonferroni. The claim
    is 'nothing survives correction', not 'no band is nominally significant'.
    """
    d = _load("t2_openings.json")
    m = d["rank_agreement_multiplicity"]
    assert m["any_significant_after_correction"] is False
    assert m["n_nominally_significant"] <= 1
    assert m["prob_of_at_least_this_many_under_null"] > 0.05


def test_t2_rho_signs_flip_across_bands():
    """A real effect would not change sign from band to band."""
    d = _load("t2_openings.json")
    signs = {r["spearman_rho"] > 0 for r in d["rank_agreement_by_band"]}
    assert signs == {True, False}


def test_t2_gap_does_not_widen_at_lower_ratings_online():
    d = _load("t2_openings.json")
    tr = d["gap_trend_low_to_high_band_by_corpus"]["lichess2017"]
    assert tr["excludes_zero"] is False


# --------------------------------------------------------------------------
# track 3: blunders
# --------------------------------------------------------------------------


def test_t3_blunder_rate_falls_monotonically_with_rating():
    d = _load("t3_blunders.json")
    bands = d["by_rating_band"]
    order = sorted(bands, key=lambda b: int(b.split("-")[0]))
    rates = [bands[b]["blunder_rate"]["point"] for b in order]
    assert rates == sorted(rates, reverse=True), rates
    # And the endpoints are separated by more than a factor of three.
    assert rates[0] / rates[-1] > 3.0
    assert rates[0] == pytest.approx(0.0832, abs=0.002)
    assert rates[-1] == pytest.approx(0.0247, abs=0.002)


def test_t3_slower_time_controls_blunder_less():
    d = _load("t3_blunders.json")
    b = d["by_time_bucket"]
    fast = b["fast_<600s"]["blunder_rate"]
    slow = b["slow_900s+"]["blunder_rate"]
    assert fast["point"] > slow["point"]
    # Tested on the difference, not by eyeballing interval overlap: the two
    # separate intervals DO overlap slightly, which is why the direct test
    # exists. Overlap is a conservative and misleading proxy.
    diff = d["fast_vs_slow_difference"]
    assert diff["excludes_zero"] is True
    assert diff["difference_fast_minus_slow"] > 0
    assert diff["relative_increase"] == pytest.approx(0.293, abs=0.02)


def test_t3_ordering_survives_every_blunder_threshold():
    d = _load("t3_blunders.json")
    for thr, v in d["threshold_sensitivity"].items():
        rates = v["ordering_fast_to_slow"]
        assert rates == sorted(rates, reverse=True), f"{thr} breaks the ordering"


def test_t3_time_explains_almost_none_of_between_game_variance():
    """Guards the caveat, not the effect: the R^2 is near zero on purpose."""
    d = _load("t3_blunders.json")
    assert abs(d["shape_test"]["linear_adj_r2"]) < 0.05
    assert d["shape_test"]["quadratic_excludes_zero"] is False


def test_t3_endogenous_axis_would_have_destroyed_the_effect():
    """Pins the methodological finding, which is worth as much as the result."""
    d = _load("t3_blunders.json")
    clean = d["shape_test"]["linear_slope_per_10s"]
    endo = d["shape_test"]["endogenous_axis_check"]["slope_per_10s"]
    assert clean < 0, "clean axis should show fewer blunders with more time"
    assert endo > 0, "endogenous axis should show the wrong sign"


# --------------------------------------------------------------------------
# track 4: rating inflation
# --------------------------------------------------------------------------


def test_t4_is_a_null_result():
    """No detectable ACPL drift at fixed nominal rating."""
    d = _load("t4_inflation.json")
    assert d["trend_winsorised_acpl"]["excludes_zero"] is False
    assert d["trend_adjusted"]["excludes_zero"] is False


def test_t4_null_is_reported_with_its_bound():
    """A null is only meaningful with a stated precision."""
    d = _load("t4_inflation.json")
    ci = d["trend_adjusted"]
    width = ci["ci_hi_per_decade"] - ci["ci_lo_per_decade"]
    assert 0 < width < 10, "adjusted ACPL trend bound should be a few cp per decade"


def test_t4_sharpness_control_matters():
    """Sharper positions really do produce more centipawn loss, which is why
    the control is in the model rather than assumed away."""
    d = _load("t4_inflation.json")
    assert d["trend_adjusted"]["sharpness_coefficient"] > 5


# --------------------------------------------------------------------------
# track 5: colour
# --------------------------------------------------------------------------


def test_t5_white_scores_above_parity_everywhere_in_otb():
    d = _load("t5_color.json")
    for band, v in d["twic_by_elo_band"].items():
        assert v["white_score"]["point"] > 0.5, band


def test_t5_white_edge_grows_with_strength_otb():
    d = _load("t5_color.json")
    bands = d["twic_by_elo_band"]
    order = sorted(bands, key=lambda b: int(b.split("-")[0]))
    scores = [bands[b]["white_score"]["point"] for b in order]
    assert scores[-1] > scores[0]


def test_t5_draw_rate_trend_is_the_composition_warning():
    """Unrestricted pool shows a large draw-rate slope; the fixed band shows a
    smaller one. The gap between them is the composition artifact this repo
    warns about, so both must remain present."""
    d = _load("t5_color.json")
    loose = d["twic_time_trends"]["draw_rate"]["slope_per_decade"]
    fixed = d["twic_time_trends_fixed_band_2400_2499"]["draw_rate"]["slope_per_decade"]
    assert loose < fixed < 0
    assert abs(loose - fixed) > 0.01


def test_t5_headline_uses_the_fixed_band():
    d = _load("t5_color.json")
    assert "2400-2499" in d["headline"]["basis"]


# --------------------------------------------------------------------------
# track 6: swindles, and its retraction
# --------------------------------------------------------------------------


def test_t6_online_bands_are_NOT_distinguishable():
    """Retraction guard.

    An earlier build reported a monotone decline in save rate across online
    rating bands. That was an artifact of censoring long games. With every game
    evaluated to its end the online bands are flat within noise, and this test
    pins the weaker, correct claim so the stronger one cannot creep back.
    """
    d = _load("t6_swindles.json")
    g = d["online_gradient"]
    assert g["online_slope_per_band_step"]["excludes_zero"] is False


def test_t6_only_surviving_contrast_is_online_vs_otb():
    d = _load("t6_swindles.json")
    c = d["online_gradient"]["online_vs_otb_contrast"]
    assert c["excludes_zero"] is True
    assert c["online_minus_otb"] == pytest.approx(0.096, abs=0.02)


def test_t6_nothing_is_censored_any_more():
    d = _load("t6_swindles.json")
    assert d["censoring"]["censored_share"] == 0.0
    assert d["censoring"]["censored_excluded"] == 0


def test_t6_threshold_sensitivity_is_monotone():
    d = _load("t6_swindles.json")
    s = d["threshold_sensitivity"]
    assert s["lost_at_300cp"]["swindle_rate"] > s["lost_at_500cp"]["swindle_rate"] > s["lost_at_800cp"]["swindle_rate"]


# --------------------------------------------------------------------------
# track 7: the falsification probes, including the ones that fire
# --------------------------------------------------------------------------


def test_t7_base_rate_probe_still_fires_against_track_6():
    """This is a retraction, pinned so it cannot quietly disappear.

    If this test ever passes-as-not-fired, the FINDINGS entry retracting the
    'masters save by drawing' claim must be revisited, not deleted.
    """
    d = _load("t7_falsify.json")
    p1 = next(p for p in d["probes"] if p["probe"].startswith("P1"))
    assert p1["fired"] is True


def test_t7_depth_probe_passes():
    d = _load("t7_falsify.json")
    p2 = next(p for p in d["probes"] if p["probe"].startswith("P2"))
    assert p2["fired"] is False
    assert p2["n_games_paired"] >= 50
    assert p2["gradient_sign_preserved"] is True
    assert p2["meaningful_flips"] == []


def test_t7_permutation_probe_passes():
    d = _load("t7_falsify.json")
    p3 = next(p for p in d["probes"] if p["probe"].startswith("P3"))
    assert p3["fired"] is False
    assert p3["permutation_p_value"] < 0.01


def test_t7_clustering_cost_is_reported():
    d = _load("t7_falsify.json")
    p4 = next(p for p in d["probes"] if p["probe"].startswith("P4"))
    assert p4["mean_width_ratio"] == pytest.approx(1.48, abs=0.08)


def test_t7_censoring_probe_now_passes():
    """P5 fired against the old build. It passes now because the cause was
    removed (every game is evaluated to its end) rather than bounded."""
    d = _load("t7_falsify.json")
    p5 = next(p for p in d["probes"] if p["probe"].startswith("P5"))
    assert p5["fired"] is False


def test_t7_determinism_probe_passes():
    """Guards a bug that shipped: a shared transposition table made results
    depend on how a resumable run was chunked."""
    d = _load("t7_falsify.json")
    p6 = next(p for p in d["probes"] if p["probe"].startswith("P6"))
    assert p6["fired"] is False
    assert p6["order_independent_within_process"] is True
    assert p6["matches_fresh_process"] is True
    assert p6["moves_differing"] == 0


def test_t7_summary_lists_exactly_the_fired_probes():
    d = _load("t7_falsify.json")
    fired = {p["probe"] for p in d["probes"] if p.get("fired") is True}
    assert set(d["summary"]["fired"]) == fired
    # P1 (base-rate confound in track 6) and P7 (behavioural drift in the skill
    # anchor). Both forced a change to what a track is allowed to claim.
    assert len(fired) == 2


# --------------------------------------------------------------------------
# track 8: within-player panel
# --------------------------------------------------------------------------


def test_t8_is_a_null_consistent_with_track_4():
    """Both inflation designs now point the same way and both span zero.

    The pinned value changed sign when the panel grew from 34 to 100 players.
    That is recorded deliberately: see the sign-instability test below.
    """
    d = _load("t8_player_panel.json")
    y = d["within_player_fit"]["year"]
    assert y["excludes_zero"] is False
    assert y["coefficient"] * 10 == pytest.approx(1.32, abs=0.25)


def test_t8_records_that_the_small_panel_flipped_sign():
    """The 34-player estimate was -0.65 and the 100-player estimate is +1.32.
    Both are nulls, but the earlier point estimate carried no information about
    direction, and the repo must keep saying so."""
    d = _load("t8_player_panel.json")["sign_instability_of_the_34_player_version"]
    assert d["old_year_coefficient_per_decade"] < 0
    assert d["new_year_coefficient_per_decade"] > 0
    assert d["new_panel_players"] == 100


def test_t8_engine_budget_was_disentangled_from_panel_size():
    """Panel size and node budget changed together, so the confound had to be
    ruled out before the sign change could be attributed to sampling."""
    d = _load("t8_player_panel.json")["engine_budget_invariance"]
    assert d["checked"] is True
    assert d["budget_ratio_trend_excludes_zero"] is False
    assert abs(d["acpl_year_trend_at_20000_nodes"] - d["acpl_year_trend_at_5000_nodes"]) < 0.2


def test_t8_larger_panel_still_cannot_identify_curvature():
    """ROADMAP predicted 100 players would make this spec informative. It did
    not, because the obstacle is collinearity rather than sample size."""
    d = _load("t8_player_panel.json")
    lad = d["specification_ladder"]["with_career_curvature"]
    assert lad["career_year_sq"]["excludes_zero"] is False
    bare_w = d["specification_ladder"]["with_sharpness"]["year"]["ci_hi"] - d["specification_ladder"]["with_sharpness"]["year"]["ci_lo"]
    curv_w = lad["year"]["ci_hi"] - lad["year"]["ci_lo"]
    assert curv_w > 2 * bare_w


def test_t8_recovers_a_within_player_rating_gradient():
    """The thing track 4 had to borrow from a different population."""
    d = _load("t8_player_panel.json")
    e = d["within_player_fit"]["elo"]
    assert e["excludes_zero"] is True
    assert e["coefficient"] < 0, "more rating should mean less centipawn loss"


def test_t8_does_not_include_the_collinear_career_term():
    """career_year is collinear with year after the within-transformation.
    An earlier version included it and the solver split one coefficient across
    two names. It must not come back."""
    d = _load("t8_player_panel.json")
    assert "career_year" not in d["within_player_fit"]
    assert "identification_warning" in d["design"]


def test_t8_curvature_spec_is_reported_as_underpowered():
    d = _load("t8_player_panel.json")
    ladder = d["specification_ladder"]
    bare_w = ladder["with_sharpness"]["year"]["ci_hi"] - ladder["with_sharpness"]["year"]["ci_lo"]
    curv_w = ladder["with_career_curvature"]["year"]["ci_hi"] - ladder["with_career_curvature"]["year"]["ci_lo"]
    assert curv_w > 3 * bare_w


def test_t8_elo_equivalent_is_refused_not_guessed():
    """A ratio of two noisy coefficients must not be quoted as a number."""
    d = _load("t8_player_panel.json")
    e = d["within_player_fit"]["elo_equivalent_drift_per_decade"]
    assert e["estimable"] is False
    assert e["reason"]


# --------------------------------------------------------------------------
# track 9: format-controlled swindle rate
# --------------------------------------------------------------------------


def test_t9_holds_format_constant():
    d = _load("t9_otb_swindles.json")
    assert d["design"]["bands"] == ["2200-2400", "2400-2500", "2500-2600", "2600-3200"]
    assert "over-the-board" in d["design"]["corpus"]


def test_t9_finds_no_rating_gradient():
    d = _load("t9_otb_swindles.json")
    assert d["gradients"]["save_rate"]["excludes_zero"] is False


def test_t9_reports_its_own_resolution():
    """A null is only meaningful with a stated minimum detectable effect, and
    this one is large: the design cannot see the gaps it is looking for."""
    d = _load("t9_otb_swindles.json")
    r = d["resolution"]
    assert r["mde"] > 0.1, "if this shrinks, the null became informative; update FINDINGS"
    assert r["n_games_required_per_band_for_5pp"] > 500


def test_t9_applies_the_base_rate_correction_up_front():
    """Probe P1 caught this omission in track 6. Track 9 must not repeat it."""
    d = _load("t9_otb_swindles.json")
    for row in d["by_band"]:
        assert row["base_draw_rate"] is not None
        assert row["draw_save_over_base_draw"] is not None
    assert d["normalised_draw_save_gradient"]["excludes_zero"] is False


def test_t9_level_shift_argument_rests_on_two_internal_nulls():
    d = _load("t9_otb_swindles.json")["level_shift_vs_gradient"]
    assert d["online_internal_gradient_excludes_zero"] is False
    assert d["otb_internal_gradient_excludes_zero"] is False
    assert d["level_step"] > 0.05
    assert "do not overlap" in d["caveat"]


# --------------------------------------------------------------------------
# power: every null carries a resolution bound
# --------------------------------------------------------------------------


def test_power_report_covers_every_null():
    d = _load("power_report.json")
    for key in (
        "t4_inflation_acpl_per_decade",
        "t8_within_player_acpl_per_decade",
        "t2_opening_slope",
        "t6_online_band_contrast",
    ):
        assert key in d["nulls"], f"{key} has no stated resolution"


def test_power_inflation_nulls_do_not_rule_out_claimed_inflation():
    """The correction that matters: neither inflation null is powered against
    the effect size people actually claim. If this ever flips, the FINDINGS
    wording must be strengthened deliberately."""
    d = _load("power_report.json")
    for key in ("t4_inflation_acpl_per_decade", "t8_within_player_acpl_per_decade"):
        assert d["nulls"][key]["benchmark_would_have_been_detected"] is False


def test_power_accounts_for_clustering():
    d = _load("power_report.json")
    c = d["clustering"]
    assert c["implied_design_effect_on_sample_size"] > 2.0


# --------------------------------------------------------------------------
# track 10: specification curves
# --------------------------------------------------------------------------


def test_t10_blunder_gradient_survives_every_specification():
    """Track 3's strongest claim, audited across 180 analytic combinations."""
    d = _load("t10_multiverse.json")["C1_blunder_gradient_across_bands"]
    assert d["share_same_sign_as_median"] == 1.0
    assert d["max"] < 0, "every specification must find a negative gradient"
    assert d["n_estimated"] >= 150


def test_t10_fast_vs_slow_survives_every_specification():
    d = _load("t10_multiverse.json")["C2_fast_minus_slow_blunder_rate"]
    assert d["share_same_sign_as_median"] == 1.0
    assert d["min"] > 0, "every specification must find faster games blundering more"


def test_t10_reported_specifications_are_not_cherry_picked():
    """The published choice should sit inside the bulk of the curve, not at an
    extreme that flatters the finding."""
    d = _load("t10_multiverse.json")
    for key in ("C1_blunder_gradient_across_bands", "C2_fast_minus_slow_blunder_rate", "C3_acpl_drift_per_decade"):
        pct = d[key]["headline_percentile_in_curve"]
        assert pct is not None, f"{key} headline did not match any specification"
        assert 0.1 < pct < 0.9, f"{key} reported specification sits at percentile {pct}"


def test_t10_blunder_threshold_is_the_dominant_choice():
    """Worth knowing and worth stating: one arbitrary cutoff drives most of the
    spread in the gradient, so it deserved an argument rather than a default."""
    d = _load("t10_multiverse.json")["C1_blunder_gradient_across_bands"]
    shares = d["variance_attribution"]["shares_of_total_variance"]
    assert max(shares, key=shares.get) == "blunder_cp"
    assert shares["blunder_cp"] > 0.5


def test_t10_warns_that_sign_consistency_is_not_significance():
    d = _load("t10_multiverse.json")
    assert "sign_consistency_is_not_significance" in d
    assert "C3_audits_the_unadjusted_trend" in d


# --------------------------------------------------------------------------
# node calibration
# --------------------------------------------------------------------------


def test_calibration_refuses_to_recommend_on_noisy_data():
    """The guard that matters: attenuation must be monotone in the node budget,
    because a deeper search cannot distort a group estimate further from its own
    deeper self. Non-monotone means noise, and the script must decline rather
    than recommend the cheapest option."""
    d = _load("node_calibration.json")
    if d.get("attenuation_monotone") is False:
        assert d["recommendation"]["nodes"] is None
        assert "REFUSED" in d["recommendation"]["reasoning"]
    else:
        assert d["recommendation"]["nodes"] in (5000, 10000, 20000, None)


def test_calibration_cost_measurements_are_monotone():
    """Cost, unlike accuracy, is measured reliably even on few games: more
    nodes must take longer."""
    d = _load("node_calibration.json")
    spg = {int(k): v for k, v in d["seconds_per_game"].items() if v}
    keys = sorted(spg)
    assert [spg[k] for k in keys] == sorted(spg[k] for k in keys)


# --------------------------------------------------------------------------
# track 11: matched-skill contrast and the resignation mechanism
# --------------------------------------------------------------------------


def test_t11_matches_on_measured_skill_not_rating():
    """Rating scales are not comparable across these corpora; engine-measured
    centipawn loss is one instrument applied identically to both."""
    d = _load("t11_matched_skill.json")
    assert "centipawn loss" in d["design"]["matching_variable"]
    assert d["design"]["common_support_window_acpl"] == [20, 40]


def test_t11_skill_matching_does_not_shrink_the_gap():
    """The core result. A strength explanation predicts the gap collapses once
    both sides are compared at equal measured playing quality. It widens."""
    d = _load("t11_matched_skill.json")
    raw = d["raw_gap_online_minus_otb"]
    matched = d["stratified_contrast"]["stratified_difference"]
    assert raw > 0 and matched > 0
    assert matched > raw, "matching on skill should not have reduced the gap"
    assert d["stratified_contrast"]["excludes_zero"] is True


def test_t11_logistic_control_agrees():
    d = _load("t11_matched_skill.json")
    m = d["logistic_model"]
    assert m["online"]["excludes_zero"] is True
    assert m["online"]["odds_ratio"] > 1.5


def test_t11_resignation_gap_vanishes_when_games_are_played_out():
    """The mechanism: over-the-board players resign lost positions and online
    players grind them out. Restricted to game-sides that kept playing, the
    save rates converge."""
    d = _load("t11_matched_skill.json")["resignation_mechanism"]
    rows = d["by_threshold"]
    assert rows[0]["gap"] > 0.08
    assert abs(rows[-1]["gap"]) < 0.05, "gap should close at high play-on thresholds"
    dur = d["duration"]
    assert dur["median_moves_after_entry_online"] > dur["median_moves_after_entry_otb"]


def test_t11_flags_the_collider_rather_than_claiming_a_decomposition():
    """Conditioning on how long a game continued conditions on a post-treatment
    collider. The module must say so and must not report a share explained."""
    d = _load("t11_matched_skill.json")["resignation_mechanism"]
    assert "collider" in d["why_this_is_not_proof"]
    assert "share_explained" not in d
    assert "how_to_settle_it" in d


def test_t11_mate_detector_agrees_with_the_independent_termination_tag():
    """The detector is validated on the corpus that has tags before being
    applied to the corpus that does not. Replaying the moves must recover the
    same mate rate the tag reports."""
    d = _load("t11_matched_skill.json")["resignation_rate"]
    online = d["by_corpus"]["online"]
    tag_rate = online["termination_tags"]["mate"]
    assert online["played_to_mate"] == pytest.approx(tag_rate, abs=0.001)


def test_t11_resignation_rate_is_the_clean_test():
    """Measured on all lost-and-lost game-sides, conditioning on nothing
    post-treatment, unlike the play-on threshold analysis."""
    d = _load("t11_matched_skill.json")["resignation_rate"]
    on = d["by_corpus"]["online"]["stopped_early"]
    otb = d["by_corpus"]["otb"]["stopped_early"]
    assert otb > on, "over-the-board players should stop early more often"
    assert otb > 0.9
    assert d["difference"]["excludes_zero"] is True
    assert d["difference"]["played_to_mate_online_minus_otb"] > 0.2


def test_t11_separates_the_clean_test_from_the_collider_one():
    """Both analyses are reported, and the module must not blur which is which."""
    d = _load("t11_matched_skill.json")
    assert "why_this_is_the_clean_test" in d["resignation_rate"]
    assert "collider" in d["resignation_mechanism"]["why_this_is_not_proof"]


# --------------------------------------------------------------------------
# probe P7 and the corrected skill anchor
# --------------------------------------------------------------------------


def test_t7_anchor_drift_probe_fires():
    """Found only after track 11 showed how large resignation effects are.
    Moves played in a decided position are not competitive chess, and players
    play more of them now than they used to."""
    d = _load("t7_falsify.json")
    p7 = next(p for p in d["probes"] if p["probe"].startswith("P7"))
    assert p7["fired"] is True
    assert p7["decided_move_share_last_year"] > p7["decided_move_share_first_year"]


def test_t4_headline_uses_the_uncontaminated_anchor():
    """The contaminant points the same direction as the hypothesis under test,
    so the uncorrected trend must not be the headline."""
    d = _load("t4_inflation.json")
    assert d["headline_specification"] == "trend_undecided_only"
    assert d["trend_undecided_only"]["excludes_zero"] is False


def test_t4_composition_drift_is_real_and_reported():
    d = _load("t4_inflation.json")
    c = d["composition_drift"]
    assert c["excludes_zero"] is True
    assert c["slope_per_decade"] > 0


def test_t4_correction_reduces_the_trend_toward_zero():
    d = _load("t4_inflation.json")
    raw = d["trend_winsorised_acpl"]["slope_per_decade"]
    corrected = d["trend_undecided_only"]["slope_per_decade"]
    assert 0 < corrected < raw
