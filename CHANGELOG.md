# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project versions its *findings* as well as its code: a released number is
pinned by a test and by an entry in `scripts/check_claims.py`, so any change to
a published result is a deliberate, reviewable event rather than drift.

## [1.2.0] - 2026-10-01

The audit release. Every citation was checked against its primary source, the
literature on claim 9 was searched specifically, and the main threat the search
identified was tested with new data.

### Added
- **Track 12**: an independent replication of claim 9 on 165,852 chess.com Titled
  Tuesday games, a source that shares nothing with TWIC except the players.
  Players are linked to their over-the-board games by exact FIDE ID, which TWIC
  records from about 2011 (now in the schema as `white_fide` / `black_fide`).
  The checkmate gap replicates (+12.4 points, 730 players) and survives
  matching on time control (+10.7, blitz against over-the-board blitz).
- Online losses split into checkmate, time forfeit and concession using each
  player's final clock. About 30% of online titled losses are time forfeits,
  so the mechanism is restated as concession plus clock betting.
- How lost positions are saved on Lichess: about a fifth by the opponent running
  out of time, about two thirds won on the board.
- Closest prior work for claim 9: Purohit & Srivastava (2026) and Künn, Seel &
  Zegners (2022). Claim 9 is now labelled new but partially anticipated.

### Retracted
- **Retraction 7.** An external check citing Siu & Istead (2026) for a 27-28%
  Lichess checkmate share. The figure could not be found in the paper.

### Corrected
- Park (2026): author Jesung Park; Stockfish 18; the "most variance within
  opening family" attribution could not be confirmed and was removed.
- Sonas (2023, 2024): titles and URLs; deflation is described across the whole
  rated pool, with FIDE's March 2024 correction applied only below 2000.
- ALLIE is an ICLR 2025 paper; full authors added. DOIs added for Guid & Bratko,
  Guid, Pérez & Bratko, Cameron & Miller and Wilson; JSTOR URL for Holm.

## [1.1.0] - 2026-09-24

The literature release. Results were positioned against published work after
they existed, and the search changed them. **1.0.0 should not be cited**: three
of its claims were artifacts of the error described first below.

### Fixed: format contamination
- The Week In Chess is majority online blitz from 2020 (55% online, 39%
  classical, against 95.5% classical before) and carries no TimeControl tag.
  1.0.0 treated every TWIC game as classical over-the-board play. Format is now
  inferred from Event and Site headers (`schema.classify_format`), every
  classical analysis filters on it at load time, and probe P8 guards the filter.
- Found by a literature search, not by any test: Ben-Moshe & Genesove (2026)
  report classical draw rates rising after 2020, while 1.0.0 reported them
  falling.

### Retracted
- **Draw rates are falling** (track 5). On classical games they rise, +3.1
  points per decade, consistent with the literature.
- **Players play on longer after a position is lost** (probe P7). Online blitz.
- **Enlarging the player panel flipped the sign of the drift estimate** (track 8).
  The enlarged panel contained online games.
- **A power-report benchmark citing "30-100 Elo/decade inflation" claims.**
  Never sourced; the documented recent concern is deflation.

### Reframed as replications or consistent results
- Track 4 replicates Regan & Haworth (2011) and Regan, Macieja & Haworth (2012),
  which used the same design and overlapping data.
- Track 5's "White's edge grows with strength" is established in the literature.
- Track 8's age-period-cohort limit is textbook (Fosse & Winship 2019).
- Track 2's null is consistent with Park (2026), whose results also expose track
  2's family-level aggregation as its main weakness.

### Added
- `docs/LITERATURE.md` and `docs/references.bib` (33 entries).
- Joint inference for specification curves (Simonsohn, Simmons & Nelson 2020,
  step 3). The time-control effect in track 3 is borderline under it (p = 0.052)
  despite unanimous sign across 180 specifications.
- Probe P8 (format contamination). `format`, `event` and `site` in the schema.
- Post-2020 classical draw comparison in track 5.
- Claims check now enforces the expected SIGN of every pinned number, and checks
  retractions structurally rather than by keyword.

- Claim 9 strengthened with a within-player comparison across formats: the same
  558 titled players end 11.6 points more of their losses in checkmate online than
  in classical over-the-board play (CI 10.3 to 12.9). Engine-free, using a
  checkmate detector validated at 100% agreement against board replay and
  Lichess's termination tags.

### Changed
- FINDINGS.md rewritten as nine numbered claims with status labels, scope
  conditions and prior work.
- Licence changed from MIT to Apache-2.0. Author metadata, ORCID and repository
  URLs filled in. Engine evaluations (`data/eval/`) are now committed.

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
