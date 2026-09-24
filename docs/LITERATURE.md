# Literature review

This review was written **after** the results existed, deliberately. The aim
was not to decorate findings with references but to find out which of them were
already known, which contradicted published work, and which, if any, were new.
The search changed the repository substantially: it caught a data error that had
produced a false headline, it turned several "findings" into replications, and
it exposed a missing step in the multiverse analysis. Those changes are listed
first, because they are the useful part.

Full bibliographic entries are in [`references.bib`](references.bib). Every
source below was located and checked during the search in September 2026,
except where a note says otherwise.

---

## 1. What the search changed

| # | Before the search | What was found | What changed |
|---|---|---|---|
| 1 | Track 5: draw rates in master chess are **falling**, contrary to the usual claim | Ben-Moshe & Genesove (2026) report classical draw rates **rose** about four points after neural-network engines spread in 2020, in 3.9M rated classical games | Chasing the contradiction showed TWIC is majority **online blitz** from 2020 and carries no time-control tag. The ingester had labelled every game classical. Headline **retracted**; on classical games draws are rising (+3.1 pp/decade) |
| 2 | Probe P7: players now play on longer after a position is lost, drifting the skill anchor | Same root cause as 1 | **Retracted**. Online blitz players play on; classical players did not change |
| 3 | Track 8: enlarging the panel from 34 to 100 players **flipped the sign** of the year coefficient | Same root cause as 1 | **Retracted**. The enlarged panel contained online games; on classical games both estimates share a sign |
| 4 | Power report benchmark justified by "commonly repeated claims of 30-100 Elo/decade inflation" | The documented concern of the last decade is **deflation** (Sonas 2023, 2024); engine-anchored studies find little drift either way (Regan & Haworth 2011) | Unsourced claim **removed**. Benchmark relabelled as an illustrative, symmetric magnitude |
| 5 | Track 4 presented as a test of rating inflation | Regan & Haworth (2011) and Regan, Macieja & Haworth (2012) used the same design (engine-measured error at fixed rating across time) and **the same TWIC corpus** | Track 4 reframed as a **replication**. Its own contribution is narrower: a decided-position filter and an explicit resolution bound |
| 6 | Track 5: White's edge grows with playing strength, presented as a finding | Established in database studies (Adorján 2004, as summarised by Brams & Ismail 2021; González-Díaz & Palacios-Huerta 2016) | Reframed as a **replication** |
| 7 | Track 8: "only curvature is separately identifiable" presented as a discovery | Textbook age-period-cohort result (Mason et al. 1973; reviewed by Fosse & Winship 2019) | Reframed as a **known identification limit**, rediscovered in a within-player setting |
| 8 | Track 10 implemented specification curves | Simonsohn, Simmons & Nelson (2020) define a third step, **joint inference** across all specifications, which was missing | Implemented. Result: the rating gradient survives (p = 0.002), the time effect is **borderline** (p = 0.052), the ACPL drift is a null (p = 0.064) |
| 9 | Track 2: engine evaluation does not predict practical opening results | Park (2026): engine evaluation is not a sufficient statistic for human outcomes, across 16.1M position occurrences, with most variance **within** opening family | **Consistent**, and it exposes a limitation: track 2 aggregates at family level, which washes out the within-family signal |
| 10 | Track 11: online and over-the-board players differ in whether they play lost positions out | No prior comparison found. Online side checked against Siu & Istead (2026), whose Lichess termination shares put checkmate at 27-28% of games | Kept as the repository's most defensibly new result, with an **external consistency check** on its online half |

Four of these ten came from one error, found by reading a single paper whose
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
which is the methodological template tracks 4, 8, 9 and 11 follow. **Strittmatter,
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

**Park (2026)** examined positions that engines assess as equal and found
reproducible, systematic differences in how they score in human play, persisting
after calibration for rating, across 16.1 million position occurrences. The
paper's conclusion is that engine evaluation is not a sufficient statistic for
human outcomes, and that most of the unexplained variance lies within opening
families rather than between them.

Track 2's null, that engine evaluation at book exit does not predict practical
score across the most-played families at any rating, is what Park's result
predicts. It also identifies track 2's weakness: aggregating to family level
discards the level of detail where Park finds the signal. A position-level
reanalysis would be a better test and is listed in the roadmap.

The self-selection problem track 2 already states (players choose openings they
know) is shared by every observational study of opening results, including
Park's.

---

## 6. Rating inflation and deflation (tracks 4 and 8)

Two literatures bear on this. The engine-anchored one (Regan & Haworth 2011;
Regan, Macieja & Haworth 2012) finds little or no inflation at master level.
The rating-system one reached a different concern: **Sonas (2023, 2024)**, in
analysis commissioned by FIDE, documented substantial rating **deflation** over
the preceding decade, concentrated below 2000 and driven by the rated pool
growing roughly tenfold since 2003, which led FIDE to apply a one-time
compression to ratings below 2000 in March 2024.

Track 4 is a replication of the Regan design on classical TWIC and agrees with
it: no detectable drift at 2400-2499 (−0.71 cp/decade, interval −1.90 to +0.41).
Its point estimate leans toward better play at a fixed rating, the direction
deflation would predict, but it cannot distinguish that from zero, and its
resolution (about ±1.5 cp/decade, roughly ±140 Elo per decade at the within-player
gradient) is too coarse to settle either the inflation or the deflation question.
Sonas's deflation is concentrated well below the 2400-2499 band studied here.

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

## 7. Why lost positions are saved online (tracks 6, 9 and 11)

No study comparing resignation behaviour between online and over-the-board play
was found. Two strands are adjacent.

**Human-like engines that model resignation.** **Zhang et al. (2024)** train
ALLIE to predict when human players resign, treating resignation as a learned
behaviour rather than an outcome of the position alone. That is the framing track
11 needs: whether a lost position gets saved depends on whether the player keeps
playing.

**Termination statistics at scale.** **Siu & Istead (2026)** report termination
shares for millions of Lichess games, with checkmate ending about 27-28% of games
in both 2014 and 2022 samples. Track 11 finds 32.0% of lost-and-lost online game
sides end in checkmate in the 2017 rapid corpus. The small gap is expected: their
samples include bullet and blitz, where games are far more often lost on time.
That external agreement is the reason to trust the online half of the comparison;
the over-the-board half (3.5% played to checkmate) has no published comparator.

**Methodological debts.** Track 11's play-on threshold analysis conditions on
how long a game continued, which is a post-treatment collider; **Elwert &
Winship (2014)** describe the bias and why it cannot be read as a decomposition.
The direct measurement, which conditions on nothing post-treatment, is the one
the argument rests on.

*Status.* New as far as this search could determine. Readers with knowledge of
prior work comparing resignation across formats are invited to say so through the
"Challenge a finding" issue template.

---

## 8. Methods this repository relies on

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
reference lists. Paywalled full texts were not always accessible, so some
characterisations rest on abstracts and on how later papers summarise earlier
ones; those are the claims most worth checking against the originals. Several of
the most relevant papers are 2026 preprints and may change before publication.

The search was not systematic in the formal sense (no registered protocol, no
database-wide query). It is best read as a good-faith attempt to find what would
embarrass this repository, which is how most of it was used.
