# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project versions its *findings* as well as its code: a released number is
pinned by a test and by an entry in `scripts/check_claims.py`, so any change to
a published result is a deliberate, reviewable event rather than drift.

## [1.0.0] - 2026-08-30

### Added since the first draft
- Track 11: the online/over-the-board save-rate gap is resignation norms, not
  chess skill. Matched on engine-measured skill rather than incomparable rating
  scales; the mechanism is measured directly rather than inferred.
- Track 10: specification curves over every defensible analytic choice.
- Track 9: save rates with playing format held constant.
- Probe P7: the ACPL skill anchor drifts because players stop playing earlier
  than they used to, in the same direction genuine inflation would. Tracks 4 and
  8 changed which specification they report as primary.
- Track 8's panel expanded from 34 to 100 players. The year coefficient changed
  sign, showing the original estimate carried no directional information.
- `chesslab` CLI, dataset export with data dictionary, power report, provenance
  manifest, engine-budget calibration, generated findings page.

## [0.1.0] - 2026-08-20

First public release. Ten tracks over 190,967 public games, 1,748 of them
engine-scored.

### Findings
- Blunder rate falls ~3.4x from 1200 to 2200; faster games blunder ~29% more
  (track 3), robust across all 180 analytic specifications tested (track 10).
- White's advantage grows with strength and draw rates are falling in
  over-the-board play, not rising (track 5).
- Engine-assessed opening quality does not predict practical results at any
  rating (track 2).
- No detectable rating inflation by two independent designs (tracks 4 and 8),
  neither of which is powered to rule out the drift rate commonly claimed.
- No save-rate gradient across 400 Elo of over-the-board play; the online/OTB
  gap looks like playing format rather than strength (track 9).

### Retracted before release
- **"Save rate falls monotonically with rating"** (track 6). An artifact of
  truncating evaluation at ply 120, which preferentially discarded long
  defensive games. Every game is now scored to its end.
- **"Amateurs save by winning, masters save by drawing"** (track 6). The
  contrast disappears once each group is normalised by its own base draw rate.
  Caught by falsification probe P1.

Both retractions are pinned by tests, and `scripts/check_claims.py` fails if
the retraction text is removed while the probe still fires.

### Bugs found and fixed during the build
- **Shared transposition table.** One Stockfish hash was reused across games, so
  results depended on how a resumable run was chunked (~19cp per move). Every
  search now passes a per-game key. Guarded by probe P6.
- **Endogenous time axis.** Dividing a time budget by a game's own length
  labelled long games "fast" and *reversed* the sign of the time effect.
- **Collinear regressor under fixed effects.** `career_year` and `year` are the
  same column after demeaning; the solver split one coefficient across two
  names and returned them equal to ten decimal places.
- **Censoring.** See retraction 1.
- **Broken console script.** `pyproject.toml` declared a `chesslab` entry point
  with no `cli` module, so installing gave a command that crashed on import.

### Infrastructure
- `chesslab` CLI: `findings`, `limits`, `status`, `verify`, `export`.
- `scripts/power_report.py`: minimum detectable effect for every null.
- `scripts/manifest.py`: content-hash provenance over code, results and data.
- `scripts/calibrate_nodes.py`: engine budget calibration, which refuses to
  recommend on noise-dominated input.
- `chesslab export`: 125,673 scored moves with a data dictionary.
