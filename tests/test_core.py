"""Unit tests for the shared layer. No corpus or engine required."""

from __future__ import annotations

import chess
import numpy as np
import pytest

from deadlost import openings, stats
from deadlost.engine import MoveEval, clamp, score_to_cp
from deadlost.ingest_twic import _iso_date, _year_from_date, iter_pgn_games
from deadlost.schema import (
    GameRecord,
    SchemaError,
    classify_time_control,
    clean_movetext,
    iter_boards,
    parse_increment_code,
    rating_band,
    result_score,
    stable_game_id,
    validate_record,
)

# --------------------------------------------------------------------------
# movetext cleaning
# --------------------------------------------------------------------------


def test_clean_movetext_strips_numbers_and_result():
    assert clean_movetext("1. e4 e5 2. Nf3 Nc6 1-0") == "e4 e5 Nf3 Nc6"


def test_clean_movetext_strips_comments_and_nags():
    txt = "1. e4 {best by test} e5 $1 2. Nf3!? Nc6?! *"
    assert clean_movetext(txt) == "e4 e5 Nf3 Nc6"


def test_clean_movetext_strips_nested_variations():
    txt = "1. e4 (1. d4 d5 (1... Nf6 2. c4)) 1... e5 2. Nf3"
    assert clean_movetext(txt) == "e4 e5 Nf3"


def test_clean_movetext_handles_black_ellipsis():
    assert clean_movetext("1... e5 2. Nf3") == "e5 Nf3"


def test_clean_movetext_normalises_zero_castling():
    # Some PGN writers emit 0-0 rather than O-O.
    out = clean_movetext("1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. 0-0 0-0")
    assert out.endswith("O-O O-O")


def test_clean_movetext_empty():
    assert clean_movetext("*") == ""


# --------------------------------------------------------------------------
# move replay
# --------------------------------------------------------------------------


def test_iter_boards_yields_each_ply():
    moves = "e4 e5 Nf3 Nc6"
    out = list(iter_boards(moves))
    assert len(out) == 4
    assert out[0][0] == 0
    assert out[0][1].turn == chess.WHITE
    assert out[1][1].turn == chess.BLACK


def test_iter_boards_rejects_illegal_move_with_ply_index():
    with pytest.raises(SchemaError) as exc:
        list(iter_boards("e4 e5 Qxf7"))
    assert "ply 2" in str(exc.value)


def test_iter_boards_respects_max_ply():
    assert len(list(iter_boards("e4 e5 Nf3 Nc6", max_ply=2))) == 2


# --------------------------------------------------------------------------
# derived fields
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "base,inc,expected",
    [
        (15, 0, "ultrabullet"),
        (60, 0, "bullet"),
        (180, 0, "blitz"),
        (600, 0, "rapid"),
        (1800, 0, "classical"),
        (300, 5, "blitz"),  # 300 + 200 = 500s -> rapid boundary check
        (None, None, "unknown"),
    ],
)
def test_classify_time_control(base, inc, expected):
    got = classify_time_control(base, inc)
    if base == 300 and inc == 5:
        assert got == "rapid"  # 500s falls in [480, 1500)
    else:
        assert got == expected


def test_parse_increment_code():
    assert parse_increment_code("15+2") == (900, 2)
    assert parse_increment_code("10+0") == (600, 0)
    assert parse_increment_code("garbage") == (None, None)


def test_rating_band_edges():
    assert rating_band(1199) == "0-1200"
    assert rating_band(1200) == "1200-1400"
    assert rating_band(2199) == "2000-2200"
    assert rating_band(2200) == "2200+"
    assert rating_band(None) is None


def test_result_score_colour_symmetry():
    assert result_score("1-0", "white") == 1.0
    assert result_score("1-0", "black") == 0.0
    assert result_score("1/2-1/2", "white") == 0.5
    assert result_score("0-1", "black") == 1.0


def test_stable_game_id_is_deterministic():
    a = stable_game_id("twic", "Carlsen", "Nakamura", "2020.01.01", "1-0")
    b = stable_game_id("twic", "Carlsen", "Nakamura", "2020.01.01", "1-0")
    c = stable_game_id("twic", "Carlsen", "Nakamura", "2020.01.02", "1-0")
    assert a == b and a != c


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def _rec(**kw) -> GameRecord:
    base = dict(
        game_id="x:1",
        source="test",
        result="1-0",
        moves="e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7",
        ply_count=10,
    )
    base.update(kw)
    return GameRecord(**base)


def test_validate_accepts_clean_record():
    assert validate_record(_rec()) is None


def test_validate_rejects_ply_count_mismatch():
    # 12 tokens declared as 11 plies: long enough to clear the min_ply gate,
    # so the mismatch check is what fires rather than "too_short".
    moves = "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5"
    assert validate_record(_rec(moves=moves, ply_count=11)) == "ply_count_mismatch"


def test_validate_rejects_bad_result():
    assert validate_record(_rec(result="*")) == "result_not_decisive_or_drawn"


def test_validate_rejects_impossible_elo():
    assert validate_record(_rec(white_elo=50)) == "elo_out_of_range"


def test_validate_rejects_short_game():
    assert validate_record(_rec(moves="e4 e5", ply_count=2)) == "too_short"


# --------------------------------------------------------------------------
# PGN parsing
# --------------------------------------------------------------------------

PGN = """[Event "Test Open"]
[Site "Somewhere"]
[Date "2011.05.02"]
[White "A, Player"]
[Black "B, Player"]
[Result "1-0"]
[WhiteElo "2450"]
[BlackElo "2460"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0

[Event "Test Open"]
[Site "Somewhere"]
[Date "2011.05.03"]
[White "C, Player"]
[Black "D, Player"]
[Result "1/2-1/2"]

1. d4 d5 2. c4 e6 1/2-1/2
"""


def test_iter_pgn_games_splits_and_reads_headers(tmp_path):
    p = tmp_path / "t.pgn"
    p.write_text(PGN)
    games = list(iter_pgn_games(p))
    assert len(games) == 2
    assert games[0][0]["White"] == "A, Player"
    assert games[0][0]["WhiteElo"] == "2450"
    assert games[1][0]["Result"] == "1/2-1/2"
    assert clean_movetext(games[1][1]) == "d4 d5 c4 e6"


def test_twic_date_helpers():
    assert _year_from_date("2011.05.02") == 2011
    assert _iso_date("2011.05.02") == "2011-05-02"
    assert _iso_date("2011.??.??") == "2011-01-01"
    assert _year_from_date("????.??.??") is None


# --------------------------------------------------------------------------
# engine scoring conventions
# --------------------------------------------------------------------------


def test_clamp_bounds():
    assert clamp(99999) == 1500
    assert clamp(-99999) == -1500
    assert clamp(42) == 42


def test_score_to_cp_mate_is_monotone_in_distance():
    near = score_to_cp(chess.engine.PovScore(chess.engine.Mate(1), chess.WHITE))
    far = score_to_cp(chess.engine.PovScore(chess.engine.Mate(12), chess.WHITE))
    assert near > far > 0


def test_score_to_cp_sign_follows_white_pov():
    black_mating = score_to_cp(chess.engine.PovScore(chess.engine.Mate(-3), chess.WHITE))
    assert black_mating < 0


def test_move_eval_loss_is_never_negative_and_colour_correct():
    # White to move, eval drops from +100 to -50: White lost 150cp.
    w = MoveEval("g", 10, "white", 100, -50, 6)
    assert w.loss_cp == 150
    # Black to move, eval rises from -50 to +100 (White POV): Black lost 150cp.
    b = MoveEval("g", 11, "black", -50, 100, 6)
    assert b.loss_cp == 150
    # An improvement is floored at zero, not counted as negative loss.
    good = MoveEval("g", 12, "white", 0, 80, 7)
    assert good.loss_cp == 0


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------


def test_wilson_ci_brackets_point_estimate():
    iv = stats.wilson_ci(30, 100)
    assert iv.lo < iv.point < iv.hi
    assert 0 <= iv.lo and iv.hi <= 1


def test_wilson_ci_handles_zero_total():
    iv = stats.wilson_ci(0, 0)
    assert iv.n == 0


def test_cluster_bootstrap_is_wider_than_naive_when_clustered():
    """The whole reason clustering exists: perfectly correlated within-cluster
    data carries far less information than its row count suggests."""
    rng = np.random.default_rng(0)
    cluster_means = rng.random(30)
    values, clusters = [], []
    for i, m in enumerate(cluster_means):
        values.extend([m] * 40)  # 40 identical rows per cluster
        clusters.extend([i] * 40)
    values = np.array(values)
    clustered = stats.cluster_bootstrap(values, np.array(clusters), np.mean, n_boot=400)
    naive = stats.cluster_bootstrap(values, np.arange(len(values)), np.mean, n_boot=400)
    assert (clustered.hi - clustered.lo) > 3 * (naive.hi - naive.lo)


def test_cluster_bootstrap_recovers_the_mean():
    rng = np.random.default_rng(1)
    v = rng.normal(5, 1, 500)
    iv = stats.cluster_bootstrap(v, np.arange(500), np.mean, n_boot=300)
    assert abs(iv.point - v.mean()) < 1e-9
    assert iv.lo < v.mean() < iv.hi


def test_ols_slope_recovers_known_line():
    x = np.arange(20)
    y = 3.0 + 2.5 * x
    slope, intercept = stats.ols_slope(x, y)
    assert slope == pytest.approx(2.5)
    assert intercept == pytest.approx(3.0)


def test_ols_slope_handles_degenerate_x():
    slope, _ = stats.ols_slope([1, 1, 1], [1, 2, 3])
    assert np.isnan(slope)


def test_bootstrap_slope_interval_contains_truth():
    rng = np.random.default_rng(2)
    x = rng.uniform(0, 10, 200)
    y = 1.0 + 0.5 * x + rng.normal(0, 0.5, 200)
    iv = stats.bootstrap_slope(x, y, n_boot=400)
    assert iv.lo < 0.5 < iv.hi


# --------------------------------------------------------------------------
# opening classification
# --------------------------------------------------------------------------


def _eco_or_skip():
    """The ECO tables are fetched, not committed. Without them these tests must
    SKIP rather than fail: CI runs the suite on a fresh clone with no corpus,
    and a hard failure there makes the whole suite red for a missing optional
    input. This was caught by installing into a clean venv."""
    from deadlost import paths

    if not (paths.RAW / "eco_a.tsv").exists():
        pytest.skip("ECO tables not fetched; run scripts/fetch_data.sh")


def test_classify_finds_longest_matching_line():
    _eco_or_skip()
    eco, name, ply = openings.classify("e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6")
    assert eco == "B90"
    assert "Najdorf" in name
    assert ply == 10


def test_classify_returns_none_for_nonsense_opening():
    _eco_or_skip()
    eco, name, ply = openings.classify("a3 h6 h3 a6")
    # Table has entries for odd first moves, so assert only on consistency.
    assert (eco is None) == (name is None)
    assert ply >= 0


def test_family_strips_variation():
    assert openings.family("Sicilian Defense: Najdorf Variation") == "Sicilian Defense"
    assert openings.family(None) is None


def test_book_exit_fen_is_playable_and_matches_ply():
    # No ECO tables needed: this exercises move replay only.
    moves = "e4 e5 Nf3 Nc6 Bb5"
    fen = openings.book_exit_fen(moves, 5)
    board = chess.Board(fen)
    assert board.turn == chess.BLACK
    assert board.fullmove_number == 3


# --------------------------------------------------------------------------
# engine determinism (requires a Stockfish binary)
# --------------------------------------------------------------------------


def _engine_or_skip():
    from deadlost.engine import find_engine

    path = find_engine()
    if not path:
        pytest.skip("no Stockfish binary available")
    return path


GAME_A = "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3 Na5 Bc2 c5 d4 Qc7"
GAME_B = "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5 O-O Nc6 a3 Bxc3 bxc3 dxc4 Bxc4 Qc7"


@pytest.mark.slow
def test_evaluator_is_order_independent():
    """Evaluating another game in between must not change a game's result.

    Stockfish keeps a transposition table across searches. Without an explicit
    per-game key, a resumable run's results depend on how it was chunked, which
    silently breaks reproducibility. This test is the guard on that fix.
    """
    _engine_or_skip()
    from deadlost.engine import Evaluator

    with Evaluator(nodes=15000) as ev:
        first = [m.loss_cp for m in ev.eval_game("A", GAME_A, max_ply=999)]
        _ = [m.loss_cp for m in ev.eval_game("B", GAME_B, max_ply=999)]
        again = [m.loss_cp for m in ev.eval_game("A", GAME_A, max_ply=999)]
    assert first == again


@pytest.mark.slow
def test_evaluator_matches_a_fresh_process():
    """A game evaluated mid-run must equal the same game evaluated alone."""
    _engine_or_skip()
    from deadlost.engine import Evaluator

    with Evaluator(nodes=15000) as ev:
        _ = [m.loss_cp for m in ev.eval_game("B", GAME_B, max_ply=999)]
        mid_run = [m.loss_cp for m in ev.eval_game("A", GAME_A, max_ply=999)]
    with Evaluator(nodes=15000) as ev:
        alone = [m.loss_cp for m in ev.eval_game("A", GAME_A, max_ply=999)]
    assert mid_run == alone


# --------------------------------------------------------------------------
# CLI and export
# --------------------------------------------------------------------------


def test_cli_entry_point_imports():
    """pyproject declares a `deadlost` console script. It shipped for several
    commits pointing at a module that did not exist, so anyone who installed
    the package got a command that crashed on import."""
    from deadlost.cli import main

    assert callable(main)


def test_cli_runs_with_no_arguments():
    from deadlost.cli import main

    assert main([]) == 0


def test_cli_findings_lists_every_track():
    from deadlost.cli import TRACKS

    assert set(TRACKS) == set(range(1, 13))
    for _, (fname, summary) in TRACKS.items():
        assert fname.endswith(".json")
        assert summary and "{" not in summary, "summary must not leak a format placeholder"


def test_cli_summaries_hedge_the_weak_tracks():
    """A CLI that overstates is worse than none. The tracks this repo does not
    trust must say so in their one-line summary."""
    from deadlost.cli import TRACKS

    assert "underpowered" in TRACKS[4][1].lower()
    assert "retracted" in TRACKS[6][1].lower()


def test_cli_unknown_track_is_an_error_not_a_crash():
    from deadlost.cli import main

    assert main(["findings", "--track", "99"]) == 1


def test_export_data_dictionary_documents_the_traps():
    """The dictionary ships with the data because three of the errors made
    building this repo came from misreading a column."""
    from deadlost.export import DATA_DICTIONARY

    lowered = DATA_DICTIONARY.lower()
    for phrase in ("not independent", "endogenous", "floored at zero", "confounded"):
        assert phrase in lowered, f"data dictionary must warn about: {phrase}"


def test_export_documents_every_sample():
    from deadlost.export import DATA_DICTIONARY, TAGS

    for tag in TAGS:
        assert f"`{tag}`" in DATA_DICTIONARY


# --------------------------------------------------------------------------
# what ships: identity, licence, placeholders
# --------------------------------------------------------------------------

from pathlib import Path as _P  # noqa: E402

_ROOT = _P(__file__).resolve().parents[1]


def test_licence_is_apache_with_the_right_holder():
    text = (_ROOT / "LICENSE").read_text()
    assert "Apache License" in text and "Version 2.0" in text
    assert "Copyright 2026 Andrew Morrissey" in text


def test_citation_identifies_the_author():
    text = (_ROOT / "CITATION.cff").read_text()
    assert "family-names: Morrissey" in text
    assert "0009-0004-8758-2687" in text
    assert "github.com/ASM-21/deadlost" in text
    assert "license: Apache-2.0" in text


def test_no_placeholders_ship():
    for rel in ("README.md", "CITATION.cff", "pyproject.toml", "NOTICE", "FINDINGS.md",
                ".github/ISSUE_TEMPLATE/config.yml", "docs/FAQ.md"):
        text = (_ROOT / rel).read_text()
        for bad in ("OWNER/", "YOUR-USERNAME", "lorem ipsum", "TODO"):
            assert bad not in text, f"{rel} contains placeholder {bad!r}"


def test_versions_agree():
    import re as _re

    import deadlost

    pyproj = _re.search(r'^version = "([^"]+)"', (_ROOT / "pyproject.toml").read_text(), _re.M).group(1)
    cff = _re.search(r"^version: (\S+)", (_ROOT / "CITATION.cff").read_text(), _re.M).group(1)
    assert deadlost.__version__ == pyproj == cff


def test_classify_format_on_real_twic_headers():
    from deadlost.schema import classify_format

    assert classify_format("Titled Tuesday Blitz Jan 3rd Early", "chess.com INT") == "online"
    assert classify_format("Betsys ch-CZE On/L Blitz 2024", "Czech Republic CZE") == "online"
    assert classify_format("Tata Steel Masters", "Wijk aan Zee NED") == "classical_otb"
    assert classify_format("World Rapid 2023", "Samarkand UZB") == "fast_otb"
    assert classify_format("29th ECC Open 2013", "Rhodes GRE") == "classical_otb"


# --------------------------------------------------------------------------
# Titled Tuesday ingestion reads the pinned list, nothing more, nothing less
# --------------------------------------------------------------------------


def _tiny_tt_zip(path, result="1-0"):
    import zipfile as _zf

    pgn = (
        '[Event "t"]\n[Date "2024.01.02"]\n[White "A, B"]\n[Black "C, D"]\n'
        f'[Result "{result}"]\n[TimeControl "180+1"]\n[WhiteFideId "1"]\n[BlackFideId "2"]\n'
        '[WhiteClock "0:01:00"]\n[BlackClock "0:00:30"]\n\n'
        f"1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# {result}\n"
    )
    with _zf.ZipFile(path, "w") as z:
        z.writestr(path.stem + ".pgn", pgn)


def test_titled_tuesday_ingest_ignores_files_not_in_the_pinned_list(tmp_path):
    from deadlost import ingest_titled_tuesday as itt

    _tiny_tt_zip(tmp_path / "titled-tuesday_2024-01-02a.zip")
    _tiny_tt_zip(tmp_path / "titled-tuesday_2099-01-01a.zip")  # stray, not pinned
    events = tmp_path / "events.txt"
    events.write_text("https://example.invalid/2024/titled-tuesday_2024-01-02a.zip\n")
    df = itt.ingest(tmp_path, events_file=events)
    assert len(df) == 1


def test_titled_tuesday_ingest_fails_loudly_on_a_missing_pinned_event(tmp_path):
    from deadlost import ingest_titled_tuesday as itt

    events = tmp_path / "events.txt"
    events.write_text("https://example.invalid/2024/titled-tuesday_2024-01-02a.zip\n")
    with pytest.raises(FileNotFoundError):
        itt.ingest(tmp_path, events_file=events)


def test_titled_tuesday_ingest_fails_loudly_on_a_corrupt_pinned_event(tmp_path):
    from deadlost import ingest_titled_tuesday as itt

    (tmp_path / "titled-tuesday_2024-01-02a.zip").write_bytes(b"not a zip")
    events = tmp_path / "events.txt"
    events.write_text("https://example.invalid/2024/titled-tuesday_2024-01-02a.zip\n")
    with pytest.raises(ValueError):
        itt.ingest(tmp_path, events_file=events)


def test_pinned_event_list_matches_the_documented_sample():
    from deadlost import ingest_titled_tuesday as itt

    names = itt.pinned_events()
    assert len(names) == 90 and len(set(names)) == 90
    assert all(n.startswith("titled-tuesday_") and n.endswith(".zip") for n in names)
