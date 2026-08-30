"""Local engine ground truth.

This repo does not consume any upstream evaluation file. Every centipawn
number here comes from Stockfish run locally at a **fixed node budget**, which
matters more than it sounds: a fixed *time* budget would make evaluation
quality depend on machine load, so blunder rates measured on a busy day would
differ from blunder rates measured on an idle one. Fixed nodes makes the
measurement reproducible on any machine, at the cost of wall-clock variance.

**Hash isolation.** Stockfish keeps a transposition table across searches. If
one process evaluates many games back to back, each game inherits hash entries
from the previous one, and results then depend on the order games were
evaluated in and on how a resumable run happened to be chunked. Measured on
this corpus that was worth about 19cp per move, enough to move a blunder across
a 300cp threshold. Every `analyse` call therefore passes a `game` key, which
makes python-chess emit `ucinewgame` whenever the key changes, so each game is
searched from a clean table. Verified by
`tests/test_core.py::test_evaluator_is_order_independent`.

Convention throughout: evaluations are in centipawns **from White's point of
view**, clamped to +/- `MATE_CP`. A mate score is mapped to `MATE_CP` minus the
distance to mate, so "mate in 1" outranks "mate in 12" and the ordering stays
monotone with position quality.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass

import chess
import chess.engine

MATE_CP = 10_000
#: Evaluations are clamped before any arithmetic. Without this, one lost queen
#: in a position already +40 pawns would register as a huge "eval swing" and
#: dominate every average.
CLAMP_CP = 1500

DEFAULT_NODES = 25_000
DEFAULT_SKIP_OPENING_PLY = 8
DEFAULT_MAX_PLY = 256  # covers the longest game in either corpus; nothing is censored


def find_engine() -> str | None:
    """Locate a Stockfish binary. `CHESSLAB_ENGINE` overrides the search."""
    env = os.environ.get("CHESSLAB_ENGINE")
    if env and os.path.exists(env):
        return env
    for name in ("stockfish", "stockfish16", "stockfish15"):
        p = shutil.which(name)
        if p:
            return p
    for p in ("/usr/games/stockfish", "/usr/local/bin/stockfish", "/opt/homebrew/bin/stockfish"):
        if os.path.exists(p):
            return p
    return None


def score_to_cp(score: chess.engine.PovScore) -> int:
    """PovScore -> centipawns from White's point of view, mate-aware."""
    white = score.white()
    mate = white.mate()
    if mate is not None:
        if mate == 0:
            return -MATE_CP if white.is_mate() and mate == 0 else MATE_CP
        sign = 1 if mate > 0 else -1
        return sign * (MATE_CP - min(abs(mate), 99))
    cp = white.score()
    return 0 if cp is None else int(cp)


def clamp(cp: int, limit: int = CLAMP_CP) -> int:
    return max(-limit, min(limit, cp))


@dataclass
class MoveEval:
    game_id: str
    ply: int
    mover: str  # "white" | "black"
    cp_before: int  # White POV, clamped
    cp_after: int  # White POV, clamped, i.e. after the move actually played
    fullmove: int

    @property
    def loss_cp(self) -> int:
        """Centipawns thrown away by the mover. Never negative.

        Measured as the drop in the position's evaluation from the mover's
        point of view. A move that "gains" evaluation means the previous
        search was shallow, not that the mover found something better than
        best play, so gains are floored at zero.
        """
        if self.mover == "white":
            return max(0, self.cp_before - self.cp_after)
        return max(0, (-self.cp_before) - (-self.cp_after))


class Evaluator:
    """Thin wrapper that keeps one engine process alive across many games."""

    def __init__(self, nodes: int = DEFAULT_NODES, threads: int = 1, hash_mb: int = 64, path: str | None = None):
        self.path = path or find_engine()
        if not self.path:
            raise RuntimeError(
                "No Stockfish binary found. Install it (apt-get install stockfish, "
                "brew install stockfish) or set CHESSLAB_ENGINE."
            )
        self.nodes = nodes
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
        self.engine.configure({"Threads": threads, "Hash": hash_mb})
        self.limit = chess.engine.Limit(nodes=nodes)

    def eval_board(self, board: chess.Board, game: object | None = None) -> int:
        """Evaluate one position. `game` isolates the transposition table.

        Pass a stable key per logical unit of work (a game id, an opening line
        name). python-chess sends `ucinewgame` when the key changes, so results
        do not depend on what was searched before.
        """
        if board.is_game_over(claim_draw=False):
            outcome = board.outcome()
            if outcome is None or outcome.winner is None:
                return 0
            return MATE_CP if outcome.winner == chess.WHITE else -MATE_CP
        info = self.engine.analyse(board, self.limit, game=game)
        return score_to_cp(info["score"])

    def eval_game(
        self,
        game_id: str,
        moves: str,
        skip_opening_ply: int = DEFAULT_SKIP_OPENING_PLY,
        max_ply: int = DEFAULT_MAX_PLY,
    ) -> Iterator[MoveEval]:
        """Evaluate the position before and after every non-book move.

        The first `skip_opening_ply` plies are skipped because opening-book
        moves say nothing about a player's over-the-board judgement and would
        drag every average toward zero by the same amount in every group.
        `max_ply` defaults high enough to cover every game in both corpora, so
        no game is truncated. An earlier version stopped at ply 120 to save
        engine time and dropped the unfinished games from track 6; falsification
        probe P5 showed the resulting ordering did not survive worst-case bounds
        on those drops. Resuming a truncated game was tried and rejected: it
        restarts the transposition table mid-game, so an extended game's endgame
        is searched with a colder table than an uninterrupted one, which
        reintroduces exactly the chunk-dependence the `game` key removes.
        Evaluating every game to its end costs about 10% more and censors
        nothing.
        """
        board = chess.Board()
        tokens = moves.split()
        cp_prev: int | None = None

        for i, tok in enumerate(tokens):
            if i >= max_ply:
                break
            move = board.parse_san(tok)
            if i < skip_opening_ply:
                board.push(move)
                cp_prev = None
                continue
            cp_before = self.eval_board(board, game=game_id) if cp_prev is None else cp_prev
            mover = "white" if board.turn == chess.WHITE else "black"
            fullmove = board.fullmove_number
            board.push(move)
            cp_after = self.eval_board(board, game=game_id)
            cp_prev = cp_after
            yield MoveEval(
                game_id=game_id,
                ply=i,
                mover=mover,
                cp_before=clamp(cp_before),
                cp_after=clamp(cp_after),
                fullmove=fullmove,
            )

    def close(self) -> None:
        try:
            self.engine.quit()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self) -> Evaluator:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def engine_id() -> str:
    """UCI `id name` string of the located engine, for the run manifest."""
    path = find_engine()
    if not path:
        return "none"
    try:
        e = chess.engine.SimpleEngine.popen_uci(path)
        name = e.id.get("name", "unknown")
        e.quit()
        return str(name)
    except Exception:  # noqa: BLE001
        return "unknown"
