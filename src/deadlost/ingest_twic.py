"""Ingest a sample of The Week In Chess PGN issues into the shared schema.

Source: the `Twic/` directory of the rozim/ChessData GitHub PGN mirror, which
carries TWIC issues 210-1649 (roughly September 1998 through mid 2026). We
take every 26th issue, so about two issues per year, which is what gives this
repo a time axis at all.

TWIC is over-the-board tournament chess. Nearly every game is classical, the
rating floor is high (most games are 2200+ FIDE), and coverage is heavily
weighted toward European events. Every claim built on this corpus is a claim
about reported tournament chess, not about chess.

Parsing note: we use a hand-rolled PGN splitter rather than
`chess.pgn.read_game` because we need headers for ~140k games but movetext for
only the few thousand we actually evaluate, and full parsing of the whole
sample costs minutes for no benefit. Legality is verified with python-chess for
every game whose moves are used downstream (see `validate_moves`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from .schema import (
    GameRecord,
    SchemaError,
    ValidationReport,
    classify_format,
    clean_movetext,
    iter_boards,
    stable_game_id,
    validate_record,
)

SOURCE = "twic"

_HEADER = re.compile(r'^\[(\w+)\s+"(.*)"\]\s*$')


def iter_pgn_games(path: Path) -> Iterator[tuple[dict, str]]:
    """Yield `(headers, movetext)` for each game in a PGN file."""
    headers: dict[str, str] = {}
    movetext: list[str] = []
    in_moves = False

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            m = _HEADER.match(line)
            if m:
                if in_moves:
                    if headers:
                        yield headers, " ".join(movetext)
                    headers, movetext, in_moves = {}, [], False
                headers[m.group(1)] = m.group(2)
                continue
            if not stripped:
                if in_moves and movetext:
                    continue
                continue
            in_moves = True
            movetext.append(stripped)

    if headers and movetext:
        yield headers, " ".join(movetext)


def _year_from_date(date: str | None) -> int | None:
    if not date:
        return None
    head = date.split(".")[0]
    try:
        y = int(head)
    except ValueError:
        return None
    return y if 1850 <= y <= 2100 else None


def _iso_date(date: str | None) -> str | None:
    if not date:
        return None
    parts = date.replace("-", ".").split(".")
    if len(parts) != 3:
        return None
    y, m, d = parts
    if not y.isdigit():
        return None
    m = m if m.isdigit() else "01"
    d = d if d.isdigit() else "01"
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return None


def _elo(v: str | None) -> int | None:
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _fide(v: str | None) -> int | None:
    try:
        n = int(v) if v else 0
    except ValueError:
        return None
    return n if n > 0 else None


def ingest(paths: Iterable[Path], min_ply: int = 10):
    """Ingest TWIC issues. Returns `(records, report)`.

    Deduplication key is (white, black, date, result, first 20 plies), which
    catches the same game reported in two issues without collapsing genuine
    repeat pairings.
    """
    report = ValidationReport(source=SOURCE)
    records: list[GameRecord] = []
    seen: set[str] = set()

    for path in paths:
        for headers, movetext in iter_pgn_games(path):
            report.seen += 1

            result = headers.get("Result", "").strip()
            moves = clean_movetext(movetext)
            ply = len(moves.split())

            # Chess960 and other variants carry a SetUp/FEN tag; the shared
            # schema assumes the standard start position.
            if headers.get("FEN") or headers.get("SetUp") == "1":
                report.reject("non_standard_start_position")
                continue
            if headers.get("Variant") and headers["Variant"].lower() not in {"standard", "normal"}:
                report.reject("non_standard_variant")
                continue

            date = headers.get("Date")
            dedup = stable_game_id(
                SOURCE,
                headers.get("White", ""),
                headers.get("Black", ""),
                date or "",
                result,
                " ".join(moves.split()[:20]),
            )
            if dedup in seen:
                report.duplicates += 1
                continue

            rec = GameRecord(
                game_id=dedup,
                source=SOURCE,
                result=result,
                moves=moves,
                ply_count=ply,
                date=_iso_date(date),
                year=_year_from_date(date),
                rated=True,
                white_id=headers.get("White") or None,
                black_id=headers.get("Black") or None,
                white_elo=_elo(headers.get("WhiteElo")),
                black_elo=_elo(headers.get("BlackElo")),
                termination=headers.get("Termination") or None,
                time_control=headers.get("TimeControl") or None,
                tc_class="otb",
                base_seconds=None,
                increment_seconds=None,
                eco=headers.get("ECO") or None,
                opening_name=headers.get("Opening") or None,
                event=headers.get("Event") or None,
                site=headers.get("Site") or None,
                format=classify_format(headers.get("Event"), headers.get("Site")),
                # FIDE IDs appear in TWIC from roughly 2011. They allow exact
                # identity linkage to other sources that carry them.
                white_fide=_fide(headers.get("WhiteFideId")),
                black_fide=_fide(headers.get("BlackFideId")),
            )

            reason = validate_record(rec, min_ply=min_ply)
            if reason:
                report.reject(reason)
                continue

            seen.add(dedup)
            records.append(rec)
            report.admitted += 1

    return records, report


def validate_moves(records: Iterable[GameRecord], report: ValidationReport | None = None) -> list[GameRecord]:
    """Full legality check. Applied to every game whose moves are used."""
    ok = []
    for rec in records:
        if report is not None:
            report.legality_checked += 1
        try:
            for _ in iter_boards(rec.moves):
                pass
        except SchemaError:
            if report is not None:
                report.legality_failed += 1
            continue
        ok.append(rec)
    return ok
