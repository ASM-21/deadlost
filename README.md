<p align="center">
  <img src="assets/banner.svg" alt="chess-lab" width="100%">
</p>

<p align="center">
  <a href="https://github.com/ASM-21/chess-lab/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/ASM-21/chess-lab/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="tests" src="https://img.shields.io/badge/tests-137-1f4e79">
  <img alt="claims retracted" src="https://img.shields.io/badge/claims%20retracted-7-c0504d">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue">
  <img alt="licence" src="https://img.shields.io/badge/licence-Apache--2.0-green">
</p>

# chess-lab

**Nine claims about chess, tested on 190,967 public games with Stockfish 16 and
replicated on 165,852 more from an independent source, positioned against the
published literature, and attacked by a track whose only job is to break the
others.**

**The sharpest result.** Lost positions are saved far more often online than over
the board, and it is not because online players defend better. It is because
over-the-board players concede. Linking the same 730 titled players by FIDE ID across
two unrelated sources, 16.6% of their online losses end in checkmate against 4.3% of
their classical ones, and the gap holds when both sides are blitz. Online, about
30% of their losses are time forfeits: playing on is partly a bet on the clock. No
prior study comparing this across formats turned up in two literature searches;
its closest relative studies resignation online only.

**The most useful thing it did.** Reading the literature after the results
existed caught an error no test had: from 2020, the tournament corpus is mostly
online blitz, and a headline built on it had the wrong sign. Seven claims have now
been withdrawn, each pinned by a test so it cannot quietly return.

```bash
pip install -e ".[dev]" && sudo apt-get install stockfish
./scripts/fetch_data.sh && ./scripts/build_all.sh   # ~150 MB, then ~1h of engine time, resumable
chesslab findings                                     # or read FINDINGS.md
```

**[Findings](FINDINGS.md)** · **[Literature review](docs/LITERATURE.md)** · **[FAQ](docs/FAQ.md)** · **[Changelog](CHANGELOG.md)** · **[Contributing](CONTRIBUTING.md)** · **[Roadmap](ROADMAP.md)**

## Results

Status labels: **New** (no prior study found), **Replicates** (known result
reproduced), **Consistent** (agrees with prior work, not an independent test),
**Borderline** (direction stable, significance depends on analytic choices),
**Null** (no effect, reported with its resolution).

| # | Claim | Status | Evidence | Prior work |
|---|---|---|---|---|
| 1 | Blunder rate falls steeply with rating | Replicates | 8.3% of moves at 1200-1400 to 2.5% at 2000-2200; survives all 180 analytic specifications jointly (p = 0.002) | McIlroy-Young et al. 2020 |
| 2 | Faster time controls produce more blunders | Borderline | 29% more at the reported specification, but joint p = 0.052 across specifications | Chabris & Hearst 2003 |
| 3 | Thinking time is a small effect in large noise | Consistent | Time budget explains almost none of the between-game variance | Anderson et al. 2016; Sunde et al. 2026 |
| 4 | White's edge grows with strength | Replicates | 0.533 at 2200-2400 to 0.558 at 2600+ | Adorján 2004; Brams & Ismail 2021 |
| 5 | Classical draw rates are rising | Consistent | +3.1% per decade; +4.0% after 2020 | Ben-Moshe & Genesove 2026 |
| 6 | Engine opening evaluations don't predict practical results | Consistent | No band survives multiplicity correction | Park 2026 |
| 7 | No detectable rating drift at fixed rating | Null, replicates | −0.71 cp/decade, resolution ±1.48 | Regan & Haworth 2011; Sonas 2023 |
| 8 | Calendar time and ageing can't be separated within a career | Replicates | Curvature term uninformative at any panel size | Fosse & Winship 2019 |
| 9 | Lost positions are saved online because OTB players concede | **New**, partially anticipated | Same players by FIDE ID: +12.4% of losses end in mate online; +10.7% blitz vs blitz | Purohit & Srivastava 2026 (online only) |

Full argument, scope conditions and the seven retractions: [FINDINGS.md](FINDINGS.md).

## Why you can trust the numbers, and how far

**Nothing is claimed beyond the data.** The online corpus is one 2017 Lichess
scrape; the over-the-board corpus is The Week In Chess, filtered to classical
games. From 2020 TWIC is 55% online, against 95.5% classical before, and TWIC has
no time-control tag, so format is inferred from event and site headers and every
classical analysis filters on it. Probe P8 checks the filter holds.

**Unanimity across specifications is not treated as evidence.** Track 10 runs
every defensible combination of analytic choices and then does joint inference
across the whole curve (Simonsohn, Simmons & Nelson 2020). That is what showed
claim 2 is borderline even though all 180 specifications agree in sign: they all
use the same games.

**Every null states what it could have missed.** `chesslab limits` prints the
resolution of each null. None is powered against a 50 Elo per decade drift, and
the documents say so.

**Moves are not treated as independent.** Intervals resample whole games or
players. Treating moves as independent would make them 1.48x too narrow.

**Eight probes try to break the other tracks.** One fires today (P1, behind
retraction 2). Three others record bugs that were real: a censoring rule that
invented a trend, a shared engine hash table that made results depend on run
order, and the format contamination above.

**Every published number is pinned**, by a test in `tests/test_headlines.py` and
by `scripts/check_claims.py`, which also fails if a number in this README has no
registered source, if a result reverses sign, or if a firing probe goes
unanswered in the retractions table.

**The literature was searched after the results, and it changed them.**
[docs/LITERATURE.md](docs/LITERATURE.md) opens with a table of the ten things it
changed, including four claims that turned out to be replications.

## Using it without reading the source

```bash
chesslab findings           # one line per track
chesslab limits             # resolution bounds, retractions, confounds
chesslab status             # what is built and whether it has drifted
chesslab verify             # tests + claims check + manifest check
chesslab export             # 125k engine-scored moves + data dictionary
make tracks                 # re-run all analysis from cached engine output (seconds)
```

The engine evaluations are the only expensive artifact. `chesslab export`
writes them with a data dictionary that documents four traps, three of which
produced real errors during this build.

## Open blocker

`database.lichess.org`, `lichess.org` and `theweekinchess.com` were unreachable
from the build environment, so both corpora come from GitHub mirrors. This
leaves three questions open: whether errors jump at a bullet or blitz threshold,
how errors depend on the remaining clock, and the exact split between
resignation and time forfeits over the board. Pointing `scripts/fetch_data.sh` at
a Lichess monthly dump answers the first two. Nothing else depends on the mirrors.

## Contributing

The most wanted contribution is a **challenge to a finding**, and there is an
issue template for it. Two good first contributions for a stranger:

1. **Position-level reanalysis of track 2.** Park (2026) works position by
   position; track 2 aggregates whole opening families.
2. **A clock-data track.** With a Lichess dump containing `[%clk]` annotations,
   test whether blunders rise as the remaining clock falls, using the
   exogenous-budget approach track 3 already uses.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Data and licence

| Source | Used for | Licence |
|---|---|---|
| datasnaek Lichess 2017 scrape, via ogreowl/chess-analysis | online corpus | CC0 |
| The Week In Chess issues 210-1649, via rozim/ChessData | over-the-board corpus | move scores are facts; see NOTICE |
| chess.com Titled Tuesday exports, via ianrastall/titled-tuesday-archive | independent online corpus (track 12) | archive MIT; game scores are facts; fetched, not redistributed |
| lichess-org/chess-openings | opening classification | CC0 |
| Stockfish 16 | evaluations | GPL-3.0, run as a separate process |

Code is Apache-2.0, copyright 2026 Andrew Morrissey. Third-party data keeps its
own terms, listed in [NOTICE](NOTICE). Stockfish is neither bundled nor linked.

## Citing

See [CITATION.cff](CITATION.cff). If you cite a null, cite its resolution with
it. If you cite claim 9, cite the checkmate contrast, which is the clean estimate:
concession contrasts are bounds, because over the board resignation and time
forfeit cannot be separated. Online TWIC is mostly blitz, so its online-versus-fast
comparison still carries some speed difference; track 12's blitz-against-blitz
comparison is the cleaner test. The players compared are a selected, mostly
titled group.

<sub>Topics: chess, stockfish, lichess, reproducible-research, falsification,
specification-curve, open-data, statistics, python</sub>
