"""Shared game schema for chess-lab.

Every track reads the same table. One row is one game. `moves` is a
space-separated SAN token string with move numbers, annotations and comments
already stripped, which keeps the table human-readable and lets any consumer
replay a game with `iter_boards`.

Two corpora live in this table, distinguished by `source`:

  lichess2017 : online rated+casual games, all rating bands, all time controls,
                a single scrape window in 2017. Has time control, has no useful
                multi-year span.
  twic        : over-the-board tournament games reported by The Week In Chess,
                sampled across 1998-2026. Has a multi-decade span and FIDE
                Elo, has essentially no time-control variation (all classical).

No track may mix the two without saying so, because they answer different
questions: `lichess2017` is the only corpus here with rating bands below
master level and real time-control variation, and `twic` is the only one with
a time axis.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field

import chess

SCHEMA_VERSION = "1.0.0"

RESULTS = ("1-0", "0-1", "1/2-1/2")

#: Ordered, mutually exclusive time-control classes.
#: Lichess derives the class from an estimated game duration of
#: base_seconds + 40 * increment_seconds.
TC_CLASSES = ("ultrabullet", "bullet", "blitz", "rapid", "classical", "otb", "unknown")

#: Rating band edges, closed-open, in Elo. `>=2200` is the top open band.
RATING_BANDS = ((0, 1200), (1200, 1400), (1400, 1600), (1600, 1800), (1800, 2000), (2000, 2200), (2200, 10000))

COLUMNS = [
    "game_id",
    "source",
    "date",
    "year",
    "rated",
    "white_id",
    "black_id",
    "white_elo",
    "black_elo",
    "result",
    "termination",
    "time_control",
    "tc_class",
    "base_seconds",
    "increment_seconds",
    "eco",
    "opening_name",
    "ply_count",
    "moves",
]


@dataclass
class GameRecord:
    """One game. Field meanings match `COLUMNS` above."""

    game_id: str
    source: str
    result: str
    moves: str
    ply_count: int
    date: str | None = None
    year: int | None = None
    rated: bool | None = None
    white_id: str | None = None
    black_id: str | None = None
    white_elo: int | None = None
    black_elo: int | None = None
    termination: str | None = None
    time_control: str | None = None
    tc_class: str = "unknown"
    base_seconds: int | None = None
    increment_seconds: int | None = None
    eco: str | None = None
    opening_name: str | None = None

    def as_row(self) -> dict:
        d = asdict(self)
        return {c: d[c] for c in COLUMNS}


class SchemaError(ValueError):
    """Raised when a record cannot be admitted to the shared table."""


# --------------------------------------------------------------------------
# move handling
# --------------------------------------------------------------------------

_MOVE_NUM = re.compile(r"\d+\.(\.\.)?")
_COMMENT = re.compile(r"\{[^}]*\}")
_VARIATION = re.compile(r"\([^()]*\)")
_NAG = re.compile(r"\$\d+")
_RESULT_TOKEN = re.compile(r"^(1-0|0-1|1/2-1/2|\*)$")
_SAN_OK = re.compile(r"^(O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?)[+#]?$")


def clean_movetext(movetext: str) -> str:
    """Strip PGN decoration and return a space-separated SAN token string.

    Handles move numbers, `{}` comments, `$n` NAGs, `?!`-style suffixes and
    nested recursive variations. Returns `""` for a game with no moves.
    """
    txt = _COMMENT.sub(" ", movetext)
    # Recursive annotation variations can nest; peel innermost-first.
    for _ in range(8):
        new = _VARIATION.sub(" ", txt)
        if new == txt:
            break
        txt = new
    txt = _NAG.sub(" ", txt)
    txt = _MOVE_NUM.sub(" ", txt)
    out = []
    for tok in txt.split():
        if _RESULT_TOKEN.match(tok):
            continue
        tok = tok.rstrip("?!")
        tok = tok.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
        if not tok:
            continue
        out.append(tok)
    return " ".join(out)


def looks_like_san(tokens: Iterable[str]) -> bool:
    """Cheap shape check on SAN tokens. Not a legality check."""
    return all(_SAN_OK.match(t) for t in tokens)


def iter_boards(moves: str, max_ply: int | None = None) -> Iterator[tuple[int, chess.Board, chess.Move]]:
    """Yield `(ply_index, board_before_move, move)` for each SAN token.

    `ply_index` is 0-based, so ply 0 is White's first move. Raises
    `SchemaError` on the first illegal or unparseable token, with the ply
    index in the message, which is what the ingestion validator reports on.
    """
    board = chess.Board()
    for i, tok in enumerate(moves.split()):
        if max_ply is not None and i >= max_ply:
            return
        try:
            move = board.parse_san(tok)
        except Exception as exc:  # noqa: BLE001 - python-chess raises several types
            raise SchemaError(f"illegal or unparseable SAN at ply {i}: {tok!r} ({exc})") from exc
        yield i, board.copy(stack=False), move
        board.push(move)


def final_board(moves: str) -> chess.Board:
    board = chess.Board()
    for tok in moves.split():
        board.push_san(tok)
    return board


# --------------------------------------------------------------------------
# derived fields
# --------------------------------------------------------------------------


def classify_time_control(base_seconds: int | None, increment_seconds: int | None) -> str:
    """Lichess time-control class from base + increment.

    Uses lichess's own estimator: a game is treated as lasting
    `base + 40 * increment` seconds.
    """
    if base_seconds is None or increment_seconds is None:
        return "unknown"
    est = base_seconds + 40 * increment_seconds
    if est < 30:
        return "ultrabullet"
    if est < 180:
        return "bullet"
    if est < 480:
        return "blitz"
    if est < 1500:
        return "rapid"
    return "classical"


def parse_increment_code(code: str) -> tuple[int | None, int | None]:
    """Parse a lichess `"15+2"` style code into `(base_seconds, increment_seconds)`."""
    if not isinstance(code, str) or "+" not in code:
        return (None, None)
    base, inc = code.split("+", 1)
    try:
        return (int(float(base) * 60), int(float(inc)))
    except ValueError:
        return (None, None)


def rating_band(elo: float | None) -> str | None:
    """Label for the band an Elo falls in, e.g. `"1600-1800"` or `"2200+"`."""
    if elo is None or (isinstance(elo, float) and elo != elo):
        return None
    for lo, hi in RATING_BANDS:
        if lo <= elo < hi:
            return f"{lo}+" if hi >= 10000 else f"{lo}-{hi}"
    return None


def band_order() -> list[str]:
    return [f"{lo}+" if hi >= 10000 else f"{lo}-{hi}" for lo, hi in RATING_BANDS]


def result_score(result: str, color: str) -> float | None:
    """Score from one side's point of view: 1.0 win, 0.5 draw, 0.0 loss."""
    if result not in RESULTS:
        return None
    if result == "1/2-1/2":
        return 0.5
    white_won = result == "1-0"
    return 1.0 if (color == "white") == white_won else 0.0


def stable_game_id(source: str, *parts: object) -> str:
    """Deterministic id for corpora without one (TWIC). Stable across runs."""
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]
    return f"{source}:{h}"


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


@dataclass
class ValidationReport:
    source: str
    seen: int = 0
    admitted: int = 0
    rejected: dict = field(default_factory=dict)
    duplicates: int = 0
    legality_checked: int = 0
    legality_failed: int = 0

    def reject(self, reason: str) -> None:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "schema_version": SCHEMA_VERSION,
            "seen": self.seen,
            "admitted": self.admitted,
            "duplicates_dropped": self.duplicates,
            "rejected": dict(sorted(self.rejected.items(), key=lambda kv: -kv[1])),
            "legality_checked": self.legality_checked,
            "legality_failed": self.legality_failed,
        }


def validate_record(rec: GameRecord, min_ply: int = 10) -> str | None:
    """Return a rejection reason, or None if the record is admissible."""
    if rec.result not in RESULTS:
        return "result_not_decisive_or_drawn"
    if rec.ply_count < min_ply:
        return "too_short"
    if rec.ply_count != len(rec.moves.split()):
        return "ply_count_mismatch"
    if not rec.moves:
        return "no_moves"
    for elo in (rec.white_elo, rec.black_elo):
        if elo is not None and not (400 <= elo <= 3200):
            return "elo_out_of_range"
    if rec.tc_class not in TC_CLASSES:
        return "bad_tc_class"
    if rec.year is not None and not (1850 <= rec.year <= 2100):
        return "year_out_of_range"
    return None
