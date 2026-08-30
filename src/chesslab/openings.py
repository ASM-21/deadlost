"""Opening classification from the lichess-org/chess-openings tables.

We classify openings ourselves from the move list rather than trusting each
corpus's own ECO tag. TWIC tags come from whatever software the tournament
reporter used and lichess tags come from lichess, so a shared analysis that
leaned on those tags would be comparing two different classifiers. Matching a
game's own moves against one table makes the two corpora comparable.

Matching rule: longest SAN prefix in the table that the game actually played.
The table's entries are opening *lines*, so the longest match is the most
specific named line reached, and its exit position is where "the opening ends"
for the purposes of engine evaluation.
"""

from __future__ import annotations

import csv
import functools
import re
from collections.abc import Iterable
from pathlib import Path

import chess

from . import paths

_MOVE_NUM = re.compile(r"\d+\.(\.\.)?")


def _tokens(pgn: str) -> tuple[str, ...]:
    return tuple(t for t in _MOVE_NUM.sub(" ", pgn).split() if t)


@functools.lru_cache(maxsize=1)
def load_table(raw_dir: Path | None = None) -> dict[tuple[str, ...], tuple[str, str]]:
    """Map SAN-token-prefix -> (eco, name). Cached; ~3.8k entries."""
    raw = raw_dir or paths.RAW
    table: dict[tuple[str, ...], tuple[str, str]] = {}
    for letter in "abcde":
        p = raw / f"eco_{letter}.tsv"
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                key = _tokens(row["pgn"])
                if key:
                    table[key] = (row["eco"], row["name"])
    if not table:
        raise FileNotFoundError(f"no eco_*.tsv under {raw}; run scripts/fetch_data.sh")
    return table


@functools.lru_cache(maxsize=1)
def _max_len() -> int:
    return max(len(k) for k in load_table())


def classify(moves: str) -> tuple[str | None, str | None, int]:
    """Return `(eco, name, book_ply)` for a SAN move string.

    `book_ply` is the number of plies consumed by the matched line, i.e. the
    ply index at which the named opening is complete.
    """
    toks = tuple(moves.split())
    table = load_table()
    upper = min(len(toks), _max_len())
    for n in range(upper, 0, -1):
        hit = table.get(toks[:n])
        if hit:
            return hit[0], hit[1], n
    return None, None, 0


def family(name: str | None) -> str | None:
    """Coarse family label: the part of the name before the first colon.

    "Sicilian Defense: Najdorf Variation" -> "Sicilian Defense". Variations
    split a corpus into thousands of thin cells; families are the level at
    which "is this opening good" is actually argued about.
    """
    if not name:
        return None
    return name.split(":")[0].strip()


def book_exit_fen(moves: str, book_ply: int) -> str | None:
    """FEN of the position after the matched book line. None if unplayable."""
    if book_ply <= 0:
        return None
    board = chess.Board()
    for tok in moves.split()[:book_ply]:
        try:
            board.push_san(tok)
        except Exception:  # noqa: BLE001
            return None
    return board.fen()


def classify_many(move_strings: Iterable[str]) -> list[tuple[str | None, str | None, int]]:
    return [classify(m) for m in move_strings]
