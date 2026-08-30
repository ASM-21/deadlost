"""Ingest the 20k-game Lichess CSV corpus into the shared schema.

Source: the widely mirrored `games.csv` scrape of lichess.org games collected
in 2017 (originally published on Kaggle by datasnaek, mirrored on GitHub).
It is the only corpus in this repo with rating bands below master level and
real time-control variation.

Two known warts in the upstream file, both handled and both counted in the
validation report:

1. `created_at` / `last_move_at` were written through a spreadsheet and are
   stored in scientific notation, so they carry about six significant figures.
   That is enough to recover the day but not the second. The whole file is a
   single 2017 scrape window regardless, so this corpus carries no usable
   time axis and `year` is informational only.
2. The file contains duplicate `id` values. We keep the first occurrence and
   count the rest.
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Iterator
from pathlib import Path

from .schema import (
    GameRecord,
    SchemaError,
    ValidationReport,
    classify_time_control,
    clean_movetext,
    iter_boards,
    parse_increment_code,
    validate_record,
)

SOURCE = "lichess2017"

VICTORY_STATUS = {"outoftime", "resign", "mate", "draw"}


def _winner_to_result(winner: str, status: str) -> str | None:
    winner = (winner or "").strip().lower()
    if winner == "white":
        return "1-0"
    if winner == "black":
        return "0-1"
    if winner == "draw" or status == "draw":
        return "1/2-1/2"
    return None


def _epoch_ms_to_year(value: str) -> int | None:
    try:
        ms = float(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    import datetime as _dt

    try:
        return _dt.datetime.utcfromtimestamp(ms / 1000.0).year
    except (OverflowError, OSError, ValueError):
        return None


def _epoch_ms_to_date(value: str) -> str | None:
    try:
        ms = float(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    import datetime as _dt

    try:
        return _dt.datetime.utcfromtimestamp(ms / 1000.0).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def read_rows(csv_path: Path) -> Iterator[dict]:
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as fh:
        yield from csv.DictReader(fh)


def ingest(csv_path: Path, check_legality: bool = True, limit: int | None = None):
    """Yield `(GameRecord | None, reason | None)` pairs and a report.

    Returns `(records, report)`.
    """
    report = ValidationReport(source=SOURCE)
    seen_ids: set[str] = set()
    records: list[GameRecord] = []

    for row in read_rows(csv_path):
        if limit is not None and report.admitted >= limit:
            break
        report.seen += 1

        gid = (row.get("id") or "").strip()
        if not gid:
            report.reject("missing_id")
            continue
        key = f"{SOURCE}:{gid}"
        if key in seen_ids:
            report.duplicates += 1
            continue

        result = _winner_to_result(row.get("winner", ""), (row.get("victory_status") or "").strip())
        if result is None:
            report.reject("unresolvable_result")
            continue

        moves = clean_movetext(row.get("moves", ""))
        ply = len(moves.split())

        base, inc = parse_increment_code((row.get("increment_code") or "").strip())
        rec = GameRecord(
            game_id=key,
            source=SOURCE,
            result=result,
            moves=moves,
            ply_count=ply,
            date=_epoch_ms_to_date(row.get("created_at", "")),
            year=_epoch_ms_to_year(row.get("created_at", "")),
            rated=(row.get("rated", "").strip().upper() in {"TRUE", "1"}),
            white_id=(row.get("white_id") or None),
            black_id=(row.get("black_id") or None),
            white_elo=_int_or_none(row.get("white_rating")),
            black_elo=_int_or_none(row.get("black_rating")),
            termination=(row.get("victory_status") or None),
            time_control=(row.get("increment_code") or None),
            tc_class=classify_time_control(base, inc),
            base_seconds=base,
            increment_seconds=inc,
            eco=(row.get("opening_eco") or None),
            opening_name=(row.get("opening_name") or None),
        )

        reason = validate_record(rec)
        if reason:
            report.reject(reason)
            continue

        if check_legality:
            report.legality_checked += 1
            try:
                for _ in iter_boards(rec.moves):
                    pass
            except SchemaError:
                report.legality_failed += 1
                report.reject("illegal_move_sequence")
                continue

        seen_ids.add(key)
        records.append(rec)
        report.admitted += 1

    return records, report


def _int_or_none(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":  # pragma: no cover
    recs, rep = ingest(Path(sys.argv[1]))
    print(rep.as_dict())
