# Findings

Nine claims about chess, tested on 190,967 public games with Stockfish 16 as the
measuring instrument, and positioned against the published literature. This
document is the citable summary. The reasoning behind each number is in the
track modules; the literature is reviewed in [docs/LITERATURE.md](docs/LITERATURE.md).

Every number here is pinned by a test and bound to a results file by
`scripts/check_claims.py`. Six earlier claims have been withdrawn; they are
listed in [Retractions](#retractions) rather than deleted.

## Reading this document

Each claim carries one status label.

| Label | Meaning |
|---|---|
| **New** | No prior study of this found in the literature search |
| **Replicates** | Known result, reproduced on these data |
| **Consistent** | Agrees with prior work but is not an independent test of it |
| **Borderline** | Direction is stable; significance depends on how analytic choices are handled |
| **Null** | No effect detected, reported with the smallest effect that could have been |

## At a glance

| # | Claim | Status | Key number |
|---|---|---|---|
| 1 | Blunder rate falls steeply with rating | Replicates | 8.3% of moves at 1200-1400 to 2.5% at 2000-2200; joint p = 0.002 |
| 2 | Faster time controls produce more blunders | Borderline | +29% at the reported specification; joint p = 0.052 |
| 3 | Thinking time is a small effect in a large amount of noise | Consistent | Time budget explains ~0% of between-game variance |
| 4 | White's edge grows with playing strength | Replicates | White scores 0.533 at 2200-2400, 0.558 at 2600+ |
| 5 | Classical draw rates are rising | Consistent | +3.1 points per decade at 2400-2499 |
| 6 | Engine opening evaluations do not predict practical results | Consistent | No rating band survives multiplicity correction |
| 7 | No detectable rating drift at a fixed rating | Null, replicates | −0.71 cp/decade, resolution ±1.48 |
| 8 | Within a career, calendar time and ageing cannot be separated | Replicates (textbook) | Curvature term interval ±6.2 cp/decade |
| 9 | Lost positions are saved far more online, because over-the-board players resign | **New** | Same 558 players: +11.6 points more of their losses end in mate online |

Claim 9 is the one result this repository can defend as new. Claims 1 and 4 are
robust replications. Claims 5 through 8 agree with or reproduce prior work and
add a resolution bound or a scope condition. Claim 2 is where honest handling of
analytic choices turned an apparently unanimous result into a borderline one.

---

## Scope

|  | Online corpus | Over-the-board corpus |
|---|---|---|
| Source | 2017 lichess.org scrape (CC0) | The Week In Chess, issues 210-1649 |
| Games | 18,537 | 119,794 classical (of 172,430) |
| Ratings | 1200-2200 in the engine sample | Mostly 2200+ FIDE |
| Time controls | Rapid and slow; under 2% bullet or blitz | Classical only, after filtering |
| Years | One scrape, no usable time axis | 1998-2026 |
| Engine-evaluated games | 480 | 292 + 378 + 926 across three samples |

**TWIC changed format in 2020.** Before 2020 it is 95.5% classical
over-the-board play. From 2020 onward it is 55% online (dominated by chess.com
"Titled Tuesday" blitz) and only 39% classical. TWIC carries no time-control tag,
so format is derived from event and site headers (`schema.classify_format`), and
every analysis that describes classical play filters to it. Probe P8 checks that
the filter holds. An earlier build had no such filter; see retractions 3 to 5.

**Engine settings.** Stockfish 16 NNUE, single thread, fixed node budget (20,000
nodes per position for most samples, 5,000 for the player panel after
calibration showed no loss of accuracy for group estimates), transposition table
reset per game, every game evaluated to its end, evaluations clamped to ±1500cp,
first 8 plies treated as book.

---

## The argument

### 1. Blunder rate falls steeply with rating

**Evidence.** In online rapid play, the share of moves losing at least 300
centipawns falls monotonically from 8.3% at 1200-1400 to 2.5% at 2000-2200,
a factor of 3.4. Across all 180 defensible combinations of blunder threshold,
book-move cutoff, minimum game length and endgame truncation, the gradient is
negative every time, and a permutation test across the whole specification curve
gives p = 0.002. A label-permutation null (probe P3) and a fourfold-deeper engine
search (probe P2) both leave it intact.

**Scope.** Online rapid, 1200-2200, one 2017 scrape.

**Prior work.** The skill-error relationship is well established; Maia
(McIlroy-Young et al. 2020) models it move by move. This is a coarse, model-free
reproduction and the most robust single result in the repository.

**Worth knowing.** One arbitrary choice, where the blunder threshold is set,
accounts for 94% of the variation in the gradient's magnitude across
specifications. It never changes the sign.

### 2. Faster time controls produce more blunders, borderline

**Evidence.** At the reported specification, games with under 600 seconds of
estimated total time blunder 29% more often per move than games with 900 seconds
or more, and the difference excludes zero when tested directly. All 180
specifications agree in sign. But every specification uses the same games, so
agreement costs them nothing, and joint inference across the curve (step 3 of
Simonsohn, Simmons & Nelson 2020) gives **p = 0.052**.

**Scope.** Roughly 12 to 33 seconds per move. The corpus contains almost no
bullet or blitz, so whether errors jump at some threshold is untestable here.

**Prior work.** Chabris & Hearst (2003) found clearly more and larger blunders
when the same grandmasters played with about a fifth of the thinking time. A
fivefold contrast produces a clear effect; the narrow range available here does
not produce one that survives accounting for analytic flexibility.

### 3. Thinking time is a small effect in a large amount of noise

**Evidence.** The time budget explains essentially none of the variance in
blunder rate between games (adjusted R² ≈ 0.001), even though group means differ.
Which two players sat down matters far more than the clock.

**A methodological trap, measured.** A per-move time axis built by dividing a
game's time budget by the moves actually played reverses the sign of the time
effect, because long games are labelled "fast" for having lasted. The axis used
here depends only on the time control.

**Prior work.** Anderson, Kleinberg & Mullainathan (2016) found position
difficulty predicts errors far better than skill or time. Sunde, Zegners &
Strittmatter (2026) found faster moves are associated with higher quality
because time spent reflects perceived difficulty, the same endogeneity from
the other direction.

### 4. White's edge grows with playing strength

**Evidence.** In classical over-the-board play with opponents within 50 Elo,
White scores 0.533 at 2200-2400 and 0.558 at 2600+, above parity in every band.
Online, the edge is near 0.51 and not monotone across bands.

**Prior work.** Established in database studies (Adorján 2004, summarised by
Brams & Ismail 2021; González-Díaz & Palacios-Huerta 2016). **Replication.**

### 5. Classical draw rates are rising

**Evidence.** Among classical games between 2400-2499 players within 50 Elo, the
draw rate rises 3.1 points per decade over 1999-2026 (interval +0.7 to +4.9).
Comparing 2015-2019 with 2021-2025, it rises 4.0 points, from 52.1% to 56.1%,
with an interval of −1.5 to +9.6.

**Prior work.** Ben-Moshe & Genesove (2026) report classical draw rates rose about
four points after neural-network engines became freely available in 2020, in 3.9
million rated classical games. The post-2020 point estimate here is almost
identical, on a sample about three thousand times smaller whose interval includes
zero. **Consistent, not an independent confirmation.**

**This claim replaced its opposite.** An earlier build reported draws falling,
and that was the result the literature search contradicted. See retraction 3.

### 6. Engine opening evaluations do not predict practical results

**Evidence.** Across the 12 most-played opening families, the rank correlation
between Stockfish's evaluation at the end of book and White's practical score
is non-significant in every rating band after Holm correction, and its sign flips
between bands. Every mainline family evaluates within a 25.3 centipawn range, so
there is little variation for evaluation to explain.

**Scope.** Family-level aggregation. Players choose openings they know, so a
line's score partly measures who plays it; no observational design removes that.

**Prior work.** Park (2026) finds engine evaluation is not a sufficient statistic
for human outcomes across 16.1 million position occurrences, with most of the
unexplained variance *within* opening families. That supports the null and
identifies its weakness: family-level aggregation discards the level of detail
where the signal lives.

### 7. No detectable rating drift at a fixed rating

**Evidence.** Holding rating fixed at 2400-2499 in classical over-the-board
play and measuring average centipawn loss on moves made before the position was
decided, the drift is −0.71 cp per decade (interval −1.90 to +0.41). Following
96 individual players over 470 player-years gives −0.47 (interval −1.98 to +1.09).
Two designs with different weaknesses agree: no detectable drift, with point
estimates leaning toward better play at a fixed rating.

**Resolution.** The designs could only have detected drift of roughly ±1.5 cp per
decade, which is about ±140 Elo per decade at the within-player rating gradient.
That rules out only very large drift in either direction.

**Prior work.** Regan & Haworth (2011) and Regan, Macieja & Haworth (2012) used
the same design, engine-measured error at fixed rating over time, on overlapping
data including TWIC, and found little or no inflation. **Replication.** The
live policy concern is the opposite: FIDE-commissioned analysis documented rating
deflation over the past decade, concentrated below 2000 (Sonas 2023, 2024),
well below the band studied here.

### 8. Within a career, calendar time and ageing cannot be separated

**Evidence.** In the player panel, adding a career-curvature term widens the year
coefficient's interval to about ±6.2 cp per decade, and the curvature term
itself does not exclude zero. Enlarging the panel did not help.

**Why.** Within one person, calendar year and career stage move together one for
one, so their linear effects are not separately identifiable without an
assumption. That is the standard age-period-cohort problem (Mason et al. 1973;
Fosse & Winship 2019), rediscovered here in a within-player setting, not a new
result. Strittmatter, Sunde & Zegners (2020) go further with birth years and a
125-year span; TWIC has neither.

### 9. Lost positions are saved far more often online, because over-the-board players resign

**The question.** Once a position is clearly lost (worse than −500 centipawns),
how often is it still drawn or won? Online, about 19% of the time. Over the board
in classical play, about 7%. Tracks 6 and 9 could not say why, because the two
corpora differ in rating, format and population at once.

**The behaviour, measured directly.** Checkmate can be read from the final move's
`#` suffix. That witness agrees with a full board replay in all 4,000 games of a
random sample (351 of them checkmates) and with Lichess's own termination tag in
all 18,537 Lichess games, which is what licenses using it on TWIC, where no
termination tags exist. Among engine-identified lost positions that went on to
lose, 32.0% of online players played to checkmate against 3.5% in classical
over-the-board play, a difference of 28.5 points (interval 22.2 to 34.9) on 114
over-the-board games. A resigned game cannot be saved.

**The same players, compared with themselves.** The engine-based comparison
involves different people. TWIC names its players, and many titled players appear
both in classical tournaments and in online events such as Titled Tuesday. Taking
each player's decisive losses and comparing them with that same player's losses
in another format holds skill, rating and population fixed by construction:

| Same players | Players | Losses ending in mate | Within-player difference |
|---|---|---|---|
| Online vs classical over the board | 558 | 15.6% vs 4.0% | **+11.6 points** (10.3 to 12.9) |
| Fast over the board vs classical | 149 | 5.7% vs 2.1% | +3.6 points (2.2 to 5.1) |
| Online vs fast over the board | 99 | 15.7% vs 6.0% | **+9.7 points** (6.6 to 12.8) |

The two groups in the first row have almost the same median rating (2,382 online,
2,365 classical). Speeding the game up at a board adds a little; moving it online
adds much more. Across all decisive games the pattern is the same: 4.3% end in
mate in classical over-the-board play, 6.3% in fast over-the-board play, 18.6% in
TWIC's online events and 33.5% on Lichess.

**Matching on engine-measured skill points the same way.** Strong online players
and weaker over-the-board players overlap at 20-40 cp of pre-entry centipawn loss.
At matched skill the gap does not shrink (11.3 to 16.5 points), though that
contrast is itself borderline (interval −0.3 to +28.3). The within-player result
makes it unnecessary to lean on.

**Scope and limits.** Online TWIC is mostly 3+1 blitz, while fast over-the-board
play mixes rapid and blitz, so the online-versus-fast contrast still carries some
speed difference and is an upper bound on the effect of the medium alone. Losing
on time ends a game without mate and is far more common online, which pushes the
online figures down, so the contrasts are if anything understated. For the
engine-based measure, "stopped early" combines resignation with time forfeits,
which cannot be separated over the board; 96.5% is close to a resignation rate but
is a bound. Players active in both formats are a selected, mostly titled group.

**Prior work.** No study comparing resignation or playing-to-mate across formats
was found. Siu & Istead (2026) report checkmate ending about 27-28% of Lichess
games at scale; the 33.5% of decisive Lichess games here is consistent, given a
rapid-only corpus with fewer time forfeits. Zhang et al. (2024) model resignation
as a learned human behaviour, the framing this result supports. **New as far as
the search could determine.**

**What it means for tracks 6 and 9.** "Saving lost positions" measures whether
playing on is the norm in a setting, not defensive skill.

---

## Retractions

Each is pinned by a test that fails if the withdrawn claim returns.

| # | Withdrawn claim | Why | How it was caught |
|---|---|---|---|
| 1 | Save rate falls monotonically with rating (track 6) | Artifact of stopping evaluation at ply 120, which discarded long defensive games | Censoring bounds, probe P5 |
| 2 | Amateurs save by winning, masters save by drawing (track 6) | Masters draw far more of all games; normalised by that base rate, masters save as draws at 0.12x it versus 0.43x for amateurs | Base-rate probe P1 |
| 3 | Draw rates are falling in master chess (track 5) | TWIC is majority online blitz from 2020; blitz has few draws | Literature search (Ben-Moshe & Genesove 2026) |
| 4 | Players now play on longer after a position is lost (probe P7) | Same contamination: online blitz players play on | Re-run after the format fix |
| 5 | Enlarging the player panel flipped the sign of the drift estimate (track 8) | Same contamination in the enlarged panel | Re-run after the format fix |
| 6 | Power-report benchmark justified by "commonly repeated claims of 30-100 Elo/decade inflation" | Never sourced; the documented concern is deflation | Literature search (Sonas 2023, 2024) |

Retractions 3 to 5 share one cause and were found by reading a paper, not by any
test. Every probe and specification curve had run on the contaminated data and
passed. Probe P8 now guards against it.

---

## How much the nulls can say

| Null | Resolution | Illustrative effect | Ruled out? |
|---|---|---|---|
| Rating drift, fixed rating (claim 7) | ±1.48 cp/decade | 0.5 cp/decade (≈50 Elo) | No |
| Rating drift, within player (claim 7) | ±1.53 cp/decade | 0.5 cp/decade | No |
| Opening evaluation vs results (claim 6) | ±0.40 score per pawn | 0.05 score per pawn | No |

The illustrative effects are this repository's own choices, not literature
figures. Clustering moves within games widens intervals by 1.48x compared with
treating moves as independent, a 2.18x penalty in effective sample size, and
every bound above carries it.

## Guards

| Probe | Checks | Result |
|---|---|---|
| P1 | Base-rate confound in save rates | **Fires**, retraction 2 |
| P2 | Engine depth (4x nodes, paired games) | Passes |
| P3 | Rating gradient against a label-permutation null | Passes |
| P4 | Cost of ignoring clustering | 1.48x wider intervals |
| P5 | Censoring bounds | Passes (cause removed) |
| P6 | Engine determinism across run order | Passes |
| P7 | Drift in the composition of scored moves | Passes (was retraction 4) |
| P8 | Non-classical games reaching classical analyses | Passes |

## Open

Lichess's official database and TWIC's own site are unreachable from the build
environment, so both corpora come from GitHub mirrors. That leaves three
questions open: whether errors jump at a bullet or blitz threshold, how errors
depend on the remaining clock within a game, and the exact split between
resignation and time forfeits over the board. Pointing `scripts/fetch_data.sh`
at a Lichess monthly dump would address the first two.

## References

Author-year citations above are listed in full in
[docs/references.bib](docs/references.bib) and discussed in
[docs/LITERATURE.md](docs/LITERATURE.md).
