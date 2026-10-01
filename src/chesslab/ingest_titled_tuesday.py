"""Ingest chess.com Titled Tuesday exports as an independent online corpus.

WHY THIS CORPUS. Claim 9 compares how often players play a lost game to
checkmate online versus over the board. Its online evidence came from two
places that both had a gap. The 2017 Lichess scrape carries a termination tag
but is an amateur, rapid-only population. TWIC's online events are elite and
blitz, but TWIC carries no termination tag at all, so a loss that did not end in
checkmate could have been a resignation or a time forfeit, and the two mean
different things. A literature and data review (September 2026) named exactly
this as the main threat to the claim: playing on in online blitz is partly a bet
on the opponent's clock.

This archive of chess.com Titled Tuesday exports fills the gap. Each game carries:

  - `WhiteFideId` / `BlackFideId`: exact identity, linkable to TWIC's own FIDE
    IDs (present in TWIC from about 2011), so the same person can be compared
    across an online source and an over-the-board source that share nothing else;
  - `TimeControl` (3+1 blitz throughout);
  - `WhiteClock` / `BlackClock`: each player's clock when the game ended;
  - per-move `[%clk]` annotations.

There is no Termination tag, but none is needed. A loss is classified as:

  checkmate   the final move carries a `#` suffix (validated elsewhere in this
              repository at 100% agreement with a board replay);
  time        no checkmate, and the loser's final clock is at or below a small
              threshold (default 1 second; sensitivity reported);
  conceded    neither: the loser stopped with time on the clock and no mate on
              the board, which is resignation (or, rarely, abandonment).

Source: github.com/ianrastall/titled-tuesday-archive (chess.com exports, renamed
and sorted; the repository is MIT-licensed). Fetched at build time from a pinned event list
and not redistributed. Game scores are facts; see NOTICE.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd

from .schema import clean_movetext

_HEADER = re.compile(r'^\[(\w+)\s+"(.*)"\]\s*$')

#: Loser's final clock at or below this many seconds, with no checkmate, counts
#: as a time forfeit. chess.com rounds the displayed clock, so a flagged player
#: can show 0:00:01. Sensitivity to 0, 2 and 5 seconds is reported downstream.
FLAG_SECONDS = 1


def _clock_seconds(s: str | None) -> float | None:
    if not s:
        return None
    parts = s.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    sec = 0.0
    for n in nums:
        sec = sec * 60 + n
    return sec


def iter_games(pgn_text: str):
    """Yield (headers, movetext) from PGN text. Tolerates CRLF line endings."""
    headers: dict[str, str] = {}
    moves: list[str] = []
    in_moves = False
    for raw in pgn_text.splitlines():
        line = raw.rstrip("\r")
        m = _HEADER.match(line)
        if m:
            if in_moves:
                if headers:
                    yield headers, " ".join(moves)
                headers, moves, in_moves = {}, [], False
            headers[m.group(1)] = m.group(2)
            continue
        if line.strip():
            in_moves = True
            moves.append(line.strip())
    if headers and moves:
        yield headers, " ".join(moves)


def _int(v: str | None) -> int | None:
    try:
        return int(v) if v not in (None, "", "0") else None
    except ValueError:
        return None


def parse_zip(path: Path) -> list[dict]:
    rows = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.endswith(".pgn"):
                continue
            text = io.TextIOWrapper(zf.open(name), encoding="utf-8", errors="replace").read()
            event_file = Path(name).stem
            for h, movetext in iter_games(text):
                result = h.get("Result", "")
                san = clean_movetext(movetext)
                n_ply = len(san.split()) if san else 0
                rows.append(
                    {
                        "event_file": event_file,
                        "date": h.get("Date"),
                        "result": result,
                        "time_control": h.get("TimeControl"),
                        "white_fide": _int(h.get("WhiteFideId")),
                        "black_fide": _int(h.get("BlackFideId")),
                        "white_title": h.get("WhiteTitle"),
                        "black_title": h.get("BlackTitle"),
                        "white_elo": _int(h.get("WhiteElo")),
                        "black_elo": _int(h.get("BlackElo")),
                        "white_clock_s": _clock_seconds(h.get("WhiteClock")),
                        "black_clock_s": _clock_seconds(h.get("BlackClock")),
                        "ply_count": n_ply,
                        "ends_in_mate": bool(san) and san.split()[-1].endswith("#"),
                    }
                )
    return rows


def classify_loss(row: pd.Series, flag_seconds: float = FLAG_SECONDS) -> str | None:
    """'checkmate', 'time', 'conceded', or None for draws and unusable games."""
    if row["result"] not in ("1-0", "0-1"):
        return None
    if row["ends_in_mate"]:
        return "checkmate"
    loser_clock = row["black_clock_s"] if row["result"] == "1-0" else row["white_clock_s"]
    if loser_clock is None or pd.isna(loser_clock):
        return None
    return "time" if loser_clock <= flag_seconds else "conceded"


#: The pinned event list. Ingestion reads exactly these events and nothing else.
EVENTS_FILE = Path(__file__).resolve().parents[2] / "data" / "titled_tuesday_events.txt"


def pinned_events(events_file: Path = EVENTS_FILE) -> list[str]:
    """ZIP file names in the pinned sample, in list order."""
    return [
        line.strip().rsplit("/", 1)[-1]
        for line in events_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def ingest(raw_dir: Path, events_file: Path = EVENTS_FILE) -> pd.DataFrame:
    """Parse exactly the pinned events.

    An earlier version globbed every ZIP in `raw_dir` and silently skipped any
    that failed to open. Both made the sample depend on the state of the disk
    rather than on the pinned list: an extra file from another download would
    enter the analysis, and a truncated download would quietly leave it, and in
    neither case would anything say so. Now any pinned event that is missing or
    corrupt is an error, and files not in the list are ignored.
    """
    names = pinned_events(events_file)
    missing = [n for n in names if not (raw_dir / n).is_file()]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} pinned Titled Tuesday events are missing under {raw_dir}, "
            f"e.g. {missing[:3]}; run scripts/fetch_data.sh"
        )
    rows: list[dict] = []
    corrupt: list[str] = []
    for n in names:
        try:
            rows.extend(parse_zip(raw_dir / n))
        except zipfile.BadZipFile:
            corrupt.append(n)
    if corrupt:
        raise ValueError(
            f"{len(corrupt)} pinned Titled Tuesday events are corrupt, e.g. {corrupt[:3]}; "
            "delete them and re-run scripts/fetch_data.sh"
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Zero- and one-move games are forfeits and no-shows, not chess.
    df = df[df.ply_count >= 2].reset_index(drop=True)
    df["year"] = pd.to_numeric(df.date.str[:4], errors="coerce")
    df["loss_type"] = df.apply(classify_loss, axis=1)
    df["loser_fide"] = df.apply(
        lambda r: r.black_fide if r.result == "1-0" else (r.white_fide if r.result == "0-1" else None), axis=1
    )
    return df
