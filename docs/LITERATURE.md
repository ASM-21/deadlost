# Literature review

This review was written **after** the results existed, deliberately. The aim
was not to decorate findings with references but to find out which of them were
already known, which contradicted published work, and which, if any, were new.
The search changed the repository substantially: it caught a data error that had
produced a false headline, it turned several "findings" into replications, and
it exposed a missing step in the multiverse analysis. Those changes are listed
first, because they are the useful part.

Full bibliographic entries are in [`references.bib`](references.bib). Sources
were located in a first search in September 2026 and then **audited against
primary sources in a second pass**, which corrected several details and found
the closest prior work to claim 9. Anything still resting on a secondary source
is flagged where it is used.

---

## 1. What the search changed

| # | Before the search | What was found | What changed |
|---|---|---|---|
| 1 | Track 5: draw rates in master chess are **falling**, contrary to the usual claim | Ben-Moshe & Genesove (2026) report classical draw rates **rose** about four points after neural-network engines spread in 2020, in 3.9M rated classical games | Chasing the contradiction showed TWIC is majority **online blitz** from 2020 and carries no time-control tag. The ingester had labelled every game classical. Headline **retracted**; on classical games draws are rising (+3.1 pp/decade) |
| 2 | Probe P7: players now play on longer after a position is lost, drifting the skill anchor | Same root cause as 1 | **Retracted**. Online blitz players play on; classical players did not change |
| 3 | Track 8: enlarging the panel from 34 to 100 players **flipped the sign** of the year coefficient | Same root cause as 1 | **Retracted**. The enlarged panel contained online games; on classical games both estimates share a sign |
| 4 | Power report benchmark justified by "commonly repeated claims of 30-100 Elo/decade inflation" | The documented concern of the last decade is **deflation** across the rated pool (Sonas 2023, 2024); engine-anchored studies find little drift either way (Regan & Haworth 2011) | Unsourced claim **removed**. Benchmark relabelled as an illustrative, symmetric magnitude |
| 5 | Track 4 presented as a test of rating inflation | Regan & Haworth (2011) and Regan, Macieja & Haworth (2012) used the same design (engine-measured error at fixed rating across time) and **the same TWIC corpus** | Track 4 reframed as a **replication**. Its own contribution is narrower: a decided-position filter and an explicit resolution bound |
| 6 | Track 5: White's edge grows with playing strength, presented as a finding | Established in database studies (Adorján 2004, as summarised by Brams & Ismail 2021; González-Díaz & Palacios-Huerta 2016) | Reframed as a **replication** |
| 7 | Track 8: "only curvature is separately identifiable" presented as a discovery | Textbook age-period-cohort result (Mason et al. 1973; reviewed by Fosse & Winship 2019) | Reframed as a **known identification limit**, rediscovered in a within-player setting |
| 8 | Track 10 implemented specification curves | Simonsohn, Simmons & Nelson (2020) define a third step, **joint inference** across all specifications, which was missing | Implemented. Result: the rating gradient survives (p = 0.002), the time effect is **borderline** (p = 0.052), the ACPL drift is a null (p = 0.064) |
| 9 | Track 2: engine evaluation does not predict practical opening results | Park (2026): engine evaluation is not a sufficient statistic for human outcomes, across 16.1M position occurrences, analysed at the level of individual positions | **Consistent**, and it exposes a limitation: track 2 aggregates at family level, coarser than the level where Park finds the signal |
| 10 | Track 11: online and over-the-board players differ in whether they play lost positions out | No prior comparison found. Closest prior work: Purohit & Srivastava (2026) model resignation on Lichess, online only; Künn, Seel & Zegners (2022) compare the same players online and over the board, but on move quality | Kept as **new, partially anticipated**. Strengthened twice: within-player in TWIC (558 players), then independently with FIDE-ID linkage to chess.com exports (track 12) |
| 11 | Track 11 cited Siu & Istead (2026) for a 27-28% Lichess checkmate share as an external check | The audit could not find that figure in the paper's main text | **Retracted** as a citation. Replaced by a genuinely independent check: chess.com Titled Tuesday exports give 18.1% against TWIC online's 18.6% |
| 12 | Claim 9 attributed the gap to resignation | The audit flagged the main threat: in online blitz, playing on is partly a bet on the opponent's clock | **Tested** in track 12. About 30% of online titled losses are time forfeits, so the mechanism is restated as concession plus clock betting. The checkmate gap survives matching on time control |

Four of the first ten came from one error, found by reading a single paper whose
result disagreed with this repository's. No test, probe or specification curve
had caught it, because every one of them ran on the contaminated data. A new
probe (P8) now guards against it.

---

## 2. Measuring chess skill with an engine

The central instrument here, average centipawn loss against a strong engine, has
a long lineage. **Guid & Bratko (2006)** compared world champions by the
difference between their moves and the evaluation of a chess program, and
**Guid, Pérez & Bratko (2008)** examined how far such comparisons depend on the
strength of the analysing engine. That concern is why this repository fixes the
engine budget in nodes rather than time and runs probe P2, which re-evaluates a
paired sample at four times the search depth.

**Regan & Haworth (2011)** developed "intrinsic ratings": a model mapping
engine-assessed move quality to an Elo-equivalent, fitted on games at known
ratings. Their central empirical result is that the move quality associated with
a given rating has stayed roughly constant over decades, that is, little or no
rating inflation. **Regan, Macieja & Haworth (2012)** extended this by plotting
average error against FIDE tournament category over time, using ChessBase data
supplemented with TWIC.

**Künn, Palacios & Pestel (2023)** used engine-evaluated moves from real
tournaments as an outcome measure for decision quality in an economics setting,
which is the methodological template tracks 4, 8, 9 and 11 follow. **Künn, Seel
& Zegners (2022)** compared the same elite players online (the 2020 Magnus
Carlsen Invitational) and over the board (Rapid World Championships), finding
worse engine-measured move quality online. That is the within-player
online-versus-over-the-board design that tracks 11 and 12 use, applied to a
different outcome. **Strittmatter,
Sunde & Zegners (2020)** used engine-benchmarked performance to trace individual
careers over 125 years.

*Position of this repository.* Nothing here improves on the instrument. What it
adds is attention to what the instrument is applied to: the move sample
(decided positions, truncated games), the format of the games (probe P8), and the
comparability of the anchor across populations (track 11).

---

## 3. Errors, skill, and thinking time (tracks 3 and 10)

**Chabris & Hearst (2003)** compared the same grandmasters under rapid and
classical conditions and found rapid play produced substantially more and larger
blunders, more than twice as many large errors. Track 3 confirms the direction in
a different population (online players rated 1200-2200) but over a far narrower
time range, and track 10's joint inference shows the effect is only borderline
there (p = 0.052). The contrast is informative: a roughly fivefold difference in
thinking time produces a clear effect; the 12-to-33-second-per-move range
available in this corpus does not produce one that survives accounting for
analytic choices.

**Anderson, Kleinberg & Mullainathan (2016)** used endgame tablebases as ground
truth and found that the difficulty of the position predicts errors far better
than either the player's skill or the time remaining. Track 3's finding that the
time budget explains essentially none of the between-game variance in blunder
rate (adjusted R² near zero) while group means differ is consistent with that:
time is a small effect inside a large amount of position-driven variation.

**Sunde, Zegners & Strittmatter (2026)** found, across 215,000 moves, that faster
decisions are associated with *higher* quality, because time spent reflects how
difficult the position seemed. Track 3 met the same endogeneity from a different
direction: a time axis built by dividing a game's time budget by the moves
actually played reverses the sign of the time effect, because long games are
labelled "fast" for having lasted. Both results say the same thing: time that a
player chooses to spend, or a game's own length, is not an exogenous treatment.

**Human-like move models.** **McIlroy-Young et al. (2020)** trained Maia to
predict human moves conditional on rating, showing that error patterns vary
systematically with skill. Track 3's rating gradient in blunder rate is a
coarse, model-free view of the same regularity, and its survival under joint
inference (p = 0.002) is the most robust result in this repository.

---

## 4. White's advantage and draw rates (track 5)

That White's edge grows with playing strength is established. Database
tabulations show White's share of decisive games rising with rating (Adorján
2004, figures summarised by **Brams & Ismail 2021**), and **González-Díaz &
Palacios-Huerta (2016)** study first-mover effects in elite match play. Track 5
reproduces the gradient (White scores 0.533 at 2200-2400 rising to 0.558 at
2600+) and adds nothing new about it.

Draw rates are where the literature intervened. **Ben-Moshe & Genesove (2026)**
study the spread of neural-network engines from fall 2020 and report that
classical draw rates rose by about four percentage points by the end of 2021,
persisting after conditioning on ratings. This repository had reported the
opposite. The contradiction led to the discovery that TWIC's post-2020 coverage
is majority online blitz (see section 1). On classical games only:

- the 2400-2499 draw trend over 1999-2026 is **+3.1 points per decade**, with an
  interval excluding zero;
- comparing 2015-2019 with 2021-2025 gives **+4.0 points** (52.1% to 56.1%),
  almost exactly Ben-Moshe & Genesove's figure, but with an interval from
  −1.5 to +9.6 on about 1,150 games.

That is a consistency check on a study roughly three thousand times larger, not
an independent confirmation, and it is reported that way.

---

## 5. Engine evaluation and practical results in openings (track 2)

**Park (2026)** examined positions that Stockfish 18 assesses as equal and found
reproducible, systematic differences in how they score in human play, persisting
after calibration for rating, across 16.1 million position occurrences in
Lichess games. The paper's conclusion is that engine evaluation is not a
sufficient statistic for human outcomes. An earlier version of this review also
attributed to Park the finding that most unexplained variance lies within opening
families; the audit could not confirm that from the full text, so it is no longer
claimed here.

Track 2's null, that engine evaluation at book exit does not predict practical
score across the most-played families at any rating, is what Park's result
predicts. It also identifies track 2's weakness: Park works position by position,
and aggregating to family level discards that detail. A position-level
reanalysis would be a better test and is listed in the roadmap.

The self-selection problem track 2 already states (players choose openings they
know) is shared by every observational study of opening results, including
Park's.

---

## 6. Rating inflation and deflation (tracks 4 and 8)

Two literatures bear on this. The engine-anchored one (Regan & Haworth 2011;
Regan, Macieja & Haworth 2012) finds little or no inflation at master level.
The rating-system one reached a different concern: **Sonas (2023, 2024)**, in
analysis for FIDE, documented rating **deflation** present throughout the rated
pool, with the strongest players most shielded from it, as the list grew from
fewer than 40,000 players in 2003 to more than 400,000 in 2023. FIDE's response,
effective 1 March 2024, was a one-time correction applied only to ratings below
2000.

Track 4 is a replication of the Regan design on classical TWIC and agrees with
it: no detectable drift at 2400-2499 (−0.71 cp/decade, interval −1.90 to +0.41).
Its point estimate leans toward better play at a fixed rating, the direction
deflation would predict, but it cannot distinguish that from zero, and its
resolution (about ±1.5 cp/decade, roughly ±140 Elo per decade at the within-player
gradient) is too coarse to settle either the inflation or the deflation question.
FIDE's 2024 correction did not touch the 2400-2499 band studied here, and Sonas
describes the strongest players as the least affected by the deflation.

Track 8 follows the same players over time, the design **Strittmatter, Sunde &
Zegners (2020)** used over a much longer span. It runs into the problem their
paper confronts: within a person, calendar year and age (or career stage) move
together one for one. That is the age-period-cohort identification problem
(**Mason et al. 1973**; reviewed by **Fosse & Winship 2019**). Linear effects of
period and age cannot be separated without an assumption; nonlinear components
can. Strittmatter and colleagues had birth years and a 125-year span and attribute
the long-run pattern to cohort rather than period effects; TWIC has no birth
dates, so track 8 can only report the compound quantity. That limit is standard,
not a discovery of this repository.

---

## 7. Why lost positions are saved online (tracks 6, 9, 11 and 12)

*Verdict from the audit: apparently new, partially anticipated.* No study was
found that compares, between online and over-the-board play, how often a lost
game is played to checkmate, attributes the difference to concession behaviour,
or checks it within the same players. Three strands come close.

**Resignation as a behavioural decision.** **Purohit & Srivastava (2026)** is the
closest prior work. They model when players quit in roughly a million Lichess
classical games, finding that stronger players persevere longer, that players
persevere more against stronger opponents, and that a history of quitting
predicts more quitting. That is the mechanism claim 9 relies on, studied
carefully, but online only: there is no over-the-board arm and no cross-format
comparison. **Zhang et al. (2025)** train ALLIE to predict human resignations,
and **Siu & Istead (2026)** predict termination type, including resignation, on
both online and over-the-board-derived data, which is consistent with resignation
being a learned, setting-dependent behaviour.

**Same players, online and over the board.** **Künn, Seel & Zegners (2022)** use
exactly the within-player cross-format design, on engine-measured move quality.
Claim 9 applies the design to how games end.

**Informal claims.** Chess blogs assert that players resign later online than
over the board, without data, and a data-driven blog post (**Coulombe 2021**,
not peer reviewed) reports that in Lichess bullet, comebacks from lost positions
come almost entirely from flagging. The second is the strongest warning in the
literature against reading claim 9 as pure "resignation norms".

**What tracks 11 and 12 add.** Track 11 measured the difference directly: of
players who went on to lose a clearly lost position, 32.0% online played to
checkmate against 3.5% in classical over-the-board play, and the same 558 TWIC
players lose 11.6 points more often to checkmate online. Track 12 then took the
audit's warning seriously. Using chess.com's own Titled Tuesday exports, which
record each player's final clock and FIDE ID, it linked the same players to their
over-the-board games in TWIC:

- the gap replicates on an independent source (+12.4 points, 730 players);
- it survives matching on time control, online blitz against over-the-board
  blitz (+10.7 points, 154 players), so it is not about speed;
- about 30% of these players' online losses are time forfeits, so playing on
  online is in large part a bet on the opponent's clock, as Coulombe's analysis
  would predict.

The mechanism is therefore restated: over-the-board players concede lost
positions; online players concede far less often and frequently play on against
the clock. In the rapid Lichess corpus, about a fifth of saved lost positions
were won because the opponent ran out of time.

**Methodological debts.** Track 11's play-on threshold analysis conditions on how
long a game continued, a post-treatment collider (**Elwert & Winship 2014**). The
direct and linked measurements condition on nothing after the position is lost,
and the argument rests on those.

Readers who know of prior work comparing resignation across formats are invited
to say so through the "Challenge a finding" issue template.

---

## 8. Methods this repository relies on

No specification-curve or multiverse analysis applied to chess data was found in
either search. Track 10 may be the first; that is noted, not claimed.


- **Specification curves and multiverse analysis.** Simonsohn, Simmons & Nelson
  (2020); Steegen, Tuerlinckx, Gelman & Vanpaemel (2016). The motivating problem
  is analytic flexibility (Simmons, Nelson & Simonsohn 2011; Gelman & Loken 2013).
- **Collider bias.** Elwert & Winship (2014).
- **Age-period-cohort identification.** Mason et al. (1973); Fosse & Winship (2019).
- **Clustered inference and design effects.** Cameron & Miller (2015).
- **Proportions and multiplicity.** Wilson (1927) score interval; Holm (1979).
- **Ratings.** Elo (1978).

---

## 9. Search method and limits

Searches were run in September 2026 through general web search and publisher and
arXiv pages, starting from the question each track asks and then following
reference lists. A second, independent audit pass in the same month checked
every citation against primary sources (Crossref, publisher pages, arXiv, FIDE
documents), searched specifically for prior work on claim 9, and searched for
reachable data mirrors by file name as well as by topic. Paywalled full texts were not always accessible, so some
characterisations rest on abstracts and on how later papers summarise earlier
ones; those are the claims most worth checking against the originals. Several of
the most relevant papers are 2026 preprints and may change before publication.

The search was not systematic in the formal sense (no registered protocol, no
database-wide query). It is best read as a good-faith attempt to find what would
embarrass this repository, which is how most of it was used.
