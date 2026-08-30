# Findings

Eleven tracks over two public chess corpora, with Stockfish 16 as ground truth.
Every number here is pinned by a test in `tests/test_headlines.py` and bound to
a results file by `scripts/check_claims.py`, so it cannot drift silently.

Read the scope note before the findings. It is not boilerplate; two of the
questions could not be answered as originally posed, and two findings have been
retracted, one by the falsification track and one by fixing a censoring rule.

## Scope

| | `lichess2017` | `twic` |
|---|---|---|
| what | online games, one 2017 scrape | over-the-board tournament games |
| games | 18,537 | 172,430 |
| ratings | 800-2400, mostly 1400-2000 | mostly 2200+ FIDE |
| time controls | rapid and classical only | classical only |
| time span | none usable | 1998-2026 |
| engine sample | 480 games | 348 games + a 400-game player panel |

Neither corpus is "chess". The Lichess file is one scrape of one site in one
year. TWIC is tournament chess as reported by one publication, weighted toward
European events. Every claim below is a claim about these corpora.

**No bullet, essentially no blitz.** Games with a base under three minutes are
about 1% of the Lichess file. This killed the threshold question in track 3 and
bounds the time axis to roughly 5-60 seconds per move.

**Engine settings.** Stockfish 16 NNUE, fixed *node* budget (20,000 for the
move-level samples, 400,000 for opening book-exit positions), single thread.
Fixed nodes rather than fixed time so results reproduce on a loaded machine.
Evaluations clamped to +/- 1500cp before any arithmetic; the first 8 plies are
skipped as book. Every game is evaluated to its end; nothing is truncated.

**Every search passes a per-game key** so Stockfish resets its transposition
table between games. Without this, results depend on the order games are
evaluated in and therefore on how a resumable run is chunked. That bug was in an
earlier build of this repo and was worth about 19cp per move. Probe P6 guards
against its return.

---

## How much can this data actually resolve?

Read this before the nulls. Three of the results below are "no effect
detected", and `scripts/power_report.py` computes what that is worth in each
case. The answer is sobering, and it changes what those tracks are allowed to
claim.

| Null | Resolution (half-width) | Effect worth caring about | Ruled out? |
|---|---|---|---|
| Track 4 inflation | ±1.31 cp/decade | ~0.5 cp/decade (≈50 Elo) | **No** |
| Track 8 inflation, within player | ±3.33 cp/decade | ~0.5 cp/decade | **No** |
| Track 2 opening slope | ±0.39 score/pawn | 0.05 score/pawn | **No** |
| Track 9 OTB save gradient | ±0.21 in save rate | ~0.05 | **No** |

**Neither inflation null rules out the inflation people argue about.** Claimed
FIDE drift runs 30-100 Elo per decade, which at track 8's within-player
gradient is around half a centipawn. That fits comfortably inside both
intervals. The honest statement is not "there is no inflation", it is "any
drift larger than roughly 130 Elo per decade would have shown up, and none
did." That bound excludes only implausibly large inflation.

**Track 2's null is structural, not a sample-size problem.** Slope resolution
depends on the spread of the x-axis as much as on the number of games, and
every mainline opening evaluates within a 0.26-pawn band. Adding games shrinks
the interval slowly; nothing shrinks the x-range, because that is a fact about
chess openings.

**Clustering compounds all of this.** Probe P4 measures a 1.48x confidence
interval width penalty from clustering moves within games. Width scales with
the standard error and sample size with variance, so that is a **2.18x** sample
penalty for the same resolution. Every number in the table carries it.

None of this makes the nulls worthless. A bounded null is a real result, and
these bounds do exclude large effects. It does mean that anyone citing "no
inflation found here" without the bound is citing something this repo does not
claim.

---

## Track 3: blunder rate against thinking time

**Blunder rate falls with rating, steeply.** 8.3% of moves at 1200-1400 down to
2.5% at 2000-2200, a factor of 3.4 across the range. The ordering is monotone
and survives every blunder threshold tested (150, 200, 300, 500cp).

**More time means fewer blunders, but the effect is small and the variance is
enormous.** Fast games (under 600s estimated) blunder 29% more often than slow
ones (900s+). That difference is distinguishable from zero when tested
directly, but the two groups' separate confidence intervals *overlap* slightly,
which is why the repo tests the difference rather than eyeballing overlap.

**Seconds-per-move explains essentially none of the between-game variance**
(adjusted R² ≈ 0.002 linear, 0.011 log-linear). This is not a contradiction of
the previous paragraph. Time control shifts the mean by a little; which two
humans sat down shifts it by a lot. Any write-up that reports the group means
without this caveat is overselling a real but small effect.

**The threshold question is unanswered, not answered negatively.** There is no
bullet or blitz in the corpus to test a kink against.

**Methodological finding, and the one most worth reusing.** The natural way to
build a seconds-per-move axis is to divide the game's time budget by the moves
that were actually played. That axis is endogenous: a game that ran long gets
labelled "fast" because it lasted. Using it does not merely attenuate the
effect, it *reverses the sign* (+0.00008 per 10s, R² ≈ 0) versus the clean
nominal axis (−0.00112 per 10s). Pinned by
`test_t3_endogenous_axis_would_have_destroyed_the_effect`.

## Track 5: White's advantage

**White scores above parity in every over-the-board band, and the edge grows
with strength:** 0.530 at 2200-2400 rising to 0.553 at 2600+. Online, the edge
is near-invisible (around 0.51) and non-monotone across bands.

**Draw rate is falling in TWIC, which is the opposite of the usual claim.**
Within a fixed 2400-2499 band it falls about 5.9 percentage points per decade
(CI −8.9 to −3.1). White's share of decisive games and White's raw score both
drift slightly downward with intervals spanning zero, so the honest summary is:
the outcome mix is moving toward decisive games, and there is no detectable
change in who wins them.

**Composition warning, kept in the output on purpose.** On the *unrestricted*
2200+ pool the draw-rate slope is far steeper, and the pool's mean Elo drifts
down over the same period as TWIC's coverage broadens toward open tournaments.
That steeper number is a composition artifact. Both versions are published side
by side so the artifact is visible rather than tidied away.

## Track 2: do engine-approved openings win more?

**No, at any level.** Across the 12 most-played opening families, Spearman rank
correlation between engine evaluation at book exit and practical White score
survives multiplicity correction in no band, and the sign flips between bands
(ρ from −0.70 to +0.70).

**Stated precisely, because the raw numbers invite an overclaim.** One band
(2600+) is nominally significant at p = 0.039, with ρ = −0.60, i.e. pointing
*away* from the folk claim: engine-preferred openings score slightly worse among
the strongest players. Six bands were tested, so 0.3 nominal hits are expected
by chance and P(≥1 | null) = 0.27. Nothing survives Holm-Bonferroni (min
adjusted p = 0.23). Read as noise, not as a reversal.

**The mechanical reason is range compression.** Every mainline opening
evaluates within a 25.8cp band for White. The spread in
practical results across those same families is comparable or larger. There is
almost no signal to detect.

**The gap does not widen at lower ratings.** The online trend in mean absolute
gap across bands has a CI spanning zero. (The TWIC trend does exclude zero, but
that reflects White's score rising with strength, which track 5 already
measured, not opening assessment becoming more accurate.)

**Unremovable confound.** Reaching a named line is a choice. A line's score
partly measures who chose it. No observational design fixes this.

## Track 4: rating inflation

**Null result.** Holding nominal rating fixed at 2400-2499 FIDE and using
average centipawn loss as a skill anchor, the drift is +0.65 cp per decade
after controlling for game length and position sharpness, with a CI of −0.72 to
+1.93. Raw and winsorised versions agree. No detectable inflation or deflation.

**The bound is the finding.** Over 28 years this rules out drift larger than
roughly ±2cp per decade in ACPL terms. Translating that to Elo requires an
ACPL-per-Elo gradient measured on a different population, so the repo reports
the translation with that caveat attached and does not lead with it.

**What this design cannot settle, ever.** Inflation and population change
predict identical ACPL trends at fixed nominal rating. A null here is a null on
both jointly. It is not evidence that the rating pool's composition was stable.

## Track 6: saving lost positions

**9.3% of lost game-sides are saved at 2400-2499 over the board.** Of positions
worse than −500cp, that is how often the losing side still drew or won. Robust
to the threshold (higher at −300cp, lower at −800cp).

### RETRACTED (1): "save rate falls monotonically with rating"

An earlier build reported a clean monotone decline across online rating bands.
**That was an artifact of censoring.** Evaluation used to stop at ply 120 and
drop game-sides still running, which preferentially discarded long grinding
defences. With every game evaluated to its end, the online rates are 0.206,
0.228, 0.161, 0.163, 0.177: not monotone, every interval overlapping every
other, and a fitted slope across bands of −0.013 (CI −0.033 to +0.014).

What survives is a single contrast: online amateurs save at 9.6 percentage
points above over-the-board masters (CI 0.035 to 0.149). **That comparison
confounds rating with playing format**, online rapid against classical OTB, so
it cannot be attributed to rating alone.

Probe P5, which used to fire on the censoring bounds, now passes. The cause was
removed rather than bounded.

### RETRACTED (2): "amateurs save by winning, masters save by drawing"

An earlier reading noted that amateurs' saves are almost entirely wins while
masters' are almost entirely draws, and called it a defensive-skill contrast.

**Falsification probe P1 kills it.** Masters draw a large share of *all* their
games; amateurs almost never do. Normalised by each group's own base draw rate,
masters save lost positions as draws at 0.18x their base rate against 0.43x for
amateurs. Masters convert lost positions to draws *less* often than their
overall drawing propensity predicts, not more.

The defensible residue of this track is thin: lost positions are saved
sometimes, more often online than over the board, for reasons this design
cannot separate from format.

## Track 9: saving lost positions, with format held constant

**Why this track exists.** Track 6 varied rating and playing format at the same
time (online rapid against classical over-the-board) and could not attribute
its one surviving contrast to either. This track varies rating *inside* TWIC
over-the-board classical, so format, time control and reporting source are
constant.

**No gradient across 400 Elo of over-the-board play.** Save rates are 0.110 at
2200-2400, then 0.055, 0.061 and 0.065 at 2400-2500, 2500-2600 and 2600+. The
fitted slope is −0.015 per band step (CI −0.055 to +0.007). The normalised
draw-save rate, divided by each band's own base draw rate, is likewise flat
(ratios 0.22, 0.12, 0.08, 0.13). The P1 base-rate correction that destroyed
track 6's secondary claim is built into this track from the start rather than
applied after a probe caught it.

**Resolution: ±0.21 in save rate.** The design would need roughly 927 games per
band to resolve a 5-point gap. This null means "no large gradient", nothing
finer.

**The useful inference is cross-track, and it is about format.** Both corpora
are internally flat: no detectable gradient across 1000 Elo of online play, and
none across 400 Elo over the board. They sit at very different levels, 0.189
online against 0.076 over the board, a step of 11 points. A mechanism where
strength alone makes lost positions harder to save predicts a decline *within*
each corpus. There isn't one. A format mechanism predicts exactly what is
observed: two plateaus with a step between them.

**With a real caveat.** The rating ranges do not overlap, so rating and format
cannot be separated by controlling for either. The argument rests on the
*absence* of within-corpus gradients, which is weaker evidence than a direct
contrast, and both of those nulls are themselves low-powered. Reporting source
and player population also differ between corpora and could produce the same
step.

## Track 7: falsification probes

| Probe | Target | Result |
|---|---|---|
| P1 base-rate confound | track 6 | **FIRES**, retraction above |
| P2 engine depth (4x nodes, paired games) | tracks 3, 4, 6 | passes, ρ = 0.90, gradient sign preserved, no band pair separated by >1pp reverses |
| P3 label permutation | track 3 | passes, observed gradient far outside the shuffled null |
| P4 clustering cost | all | informational, treating moves as independent would have made intervals 1.48x too narrow |
| P5 censoring bounds | track 6 | passes *now*, cause removed, see retraction (1) |
| P6 evaluation determinism | all engine work | passes, order-independent, bitwise-identical to a fresh process |

Two of seven probes fire. P1 forced a retraction in track 6. P7 was written
only after track 11 revealed how large resignation effects are in this data, and
it forced tracks 4 and 8 to change which specification they report as primary,
because the contaminant it found points the same direction as the hypothesis
those tracks are testing. P5 and P6 both record bugs that were real: P5's target was a censoring
rule that manufactured a trend, P6's was a shared transposition table that made
results depend on run chunking. Both are fixed at the cause.

## Track 8: inflation, following the same players

**Null, and it agrees with track 4 from a different direction.** A panel of 100
TWIC players with 584 player-years across 1998-2026, fitting ACPL on a player
fixed effect plus rating, year and position sharpness: the year coefficient is
+1.32cp per decade, with an interval spanning zero. Track 4's corrected anchor
gives +1.20. Two designs that fail in different ways now agree on both the sign
and the magnitude of a non-result.

**An earlier version of this track got the sign wrong, and that is worth
recording.** At 34 players the coefficient was −0.65cp per decade. Tripling the
panel did not merely tighten the interval, it moved the point estimate across
zero to +1.32. Both versions are nulls, so no published conclusion changes, but
anyone who had read the smaller panel's point estimate as a direction was
reading noise. Resolution improved from ±3.33 to ±1.69cp per decade.

**Panel size and engine budget changed together, so they were separated before
interpreting.** The larger panel was scored at 5,000 nodes rather than 20,000.
Re-scoring the TWIC sample at both budgets gives ACPL year trends of +1.681 and
+1.645, and the ratio between budgets has no year trend of its own (−0.016 per
decade, interval spanning zero). Search depth does not interact with time, so
the sign change is sampling.

**A prediction this repo made about itself was refuted.** ROADMAP.md held that
roughly 100 players would make the career-curvature specification informative.
It does not: that interval remains about ±6.5cp per decade and the curvature
term still does not exclude zero. The obstacle is the collinearity described
below, which no amount of additional players dissolves.

**What this buys over track 4.** The player fixed effect differences away
composition entirely, a change in who holds a rating cannot produce a year
effect when every comparison is within one person. And the within-player rating
gradient is estimated here directly (−0.0104cp per Elo point, CI excluding
zero), where track 4 had to borrow that gradient from lichess amateurs.

**What it runs into instead, and cannot escape.** Within a player,
`career_year = year − first_year`, and `first_year` is constant for that person.
After the within-transformation the two are the *same column*. An earlier
version of this module included both as if one controlled for the other; the
solver split a single coefficient across two names and returned them equal to
ten decimal places. This is the age-period-cohort problem: the year coefficient
is unavoidably the **sum** of rating-scale drift and the average career
trajectory of these players. Only curvature is separately identifiable.

**And the panel is too small to carry curvature.** Adding a quadratic career
term widens the year interval by roughly a factor of four (to ±1.4cp/year) and
costs the rating coefficient its precision. That spec is reported as a power
diagnostic, not a result.

**No Elo-equivalent is quoted.** The ratio of two noisy coefficients gives an
interval spanning more than 200 Elo per decade, so the module refuses to print
a point estimate rather than manufacture false precision.

Track 8 trades track 4's composition confound for a structural one. With 100
players its resolution is ±1.7cp per decade against track 4's ±1.3, so the
better-identified design is no longer much less precise. The honest summary of both tracks together
is that neither detects drift, neither is powered to detect the drift that is
actually claimed, and they fail in different directions. Two underpowered nulls
that agree are more reassuring than one, but not by much.

## Track 11: the online/over-the-board gap is behavioural, not skill

This is the deepest result here, and it settles a question tracks 6 and 9 both
left open.

**The problem.** Lost positions are saved far more often online than over the
board. Track 6 could not say whether that was strength or playing format,
because the corpora vary both together. Track 9 held format constant and found
no rating gradient, which was suggestive but rested on an absence. Neither could
compare like with like, because the two corpora do not overlap in rating.

**Matching on rating would not have helped anyway.** A lichess rapid rating and
a FIDE classical rating are different scales attached to different populations.
Controlling for rating across these corpora controls for a label, not for
strength.

**So match on engine-measured skill instead.** Every game in this repository is
scored by the same Stockfish build at the same node budget, which makes average
centipawn loss one instrument applied identically to both corpora. It also turns
out to supply common support: strong online players and weaker over-the-board
players overlap in the 20-40cp range. Skill is measured only over moves played
*before* the position went bad, since a player's whole-game ACPL is contaminated
by the blunder that lost it.

**Result: matching does not shrink the gap, it widens it.** Raw difference
+11.0 points; at matched skill +17.3 points (CI +2.3 to +25.9). A logistic model
on the common-support window, controlling defender skill, converter skill and
how lost the position was, puts online games at 2.59x the odds of being saved.
A strength explanation predicts the gap collapses toward zero under matching.
It does the opposite, because the stronger over-the-board population was masking
the effect.

### The mechanism, measured directly

Resignation norms are the obvious candidate: a resigned game can never be
saved, so if masters resign promptly and online players grind on, the online
rate is inflated by opportunity alone. That is measurable here without
conditioning on anything.

Checkmate is detectable from the move list itself. **The detector is validated
on the corpus that has termination tags before being applied to the corpus that
does not**: on lichess games the move-derived mate rate is 0.3197 and the
independent `mate` tag gives 0.3197, exact agreement. TWIC carries no
termination tags at all, so the move list is the only witness available, and
this shows it is a reliable one.

Measured on lost game-sides that went on to lose, which removes the
circularity in asking whether a player who saved the game had resigned:

| | played to checkmate | stopped early |
|---|---|---|
| online (lichess rapid) | 32.0% | 68.0% |
| over the board (TWIC classical) | 5.8% | **94.2%** |

Difference in playing to mate: 26.2 points (CI 20.1 to 32.2). The online tag
breakdown is 56.7% resign, 32.0% mate, 11.3% out of time.

Over-the-board players almost never play a lost position to its conclusion.
A player who stops early forgoes any chance of being saved, so this is a direct
behavioural explanation for the entire difference in save rates, and it
conditions on nothing post-treatment.

One honest limit: "stopped early" bundles resignation with losing on time, and
those cannot be separated for TWIC. Classical over-the-board games rarely end on
the clock, so the 94.2% is close to a pure resignation rate, but it is not
exactly one.

### The same mechanism, seen through a collider

Resignation norms are the obvious candidate: a resigned game can never be saved,
so if masters resign promptly and online players grind on, the online rate is
inflated by opportunity alone. That is testable here.

| minimum moves played after the position went lost | online | over the board | gap |
|---|---|---|---|
| 0 (all) | 0.186 | 0.076 | +0.110 |
| 5 | 0.227 | 0.095 | +0.132 |
| 10 | 0.258 | 0.122 | +0.136 |
| 15 | 0.277 | 0.167 | +0.110 |
| 20 | 0.277 | 0.224 | +0.053 |
| 25 | 0.287 | 0.286 | **+0.001** |

Median moves played after reaching a lost position: 16 online, 7 over the board.
Restricted to game-sides where both populations actually played the position
out, the save rates are indistinguishable.

**Why this second analysis is suggestive and not a decomposition.** Conditioning
on how long a game continued conditions on a **post-treatment collider**: a game that gets
saved lasts longer by construction, so higher thresholds over-select saves in
both corpora and inflate both rates. The convergence is exactly what a
resignation explanation predicts, and it cannot be converted into "resignation
explains X% of the gap". This module deliberately reports no such percentage.

It is reported alongside the direct measurement above because the two agree by
different routes, and because the contrast between them is a useful worked
example: the clean test needed no conditioning, and finding it required
noticing that the move list already contained the answer that the missing
metadata was thought to be needed for.

**What this changes about tracks 6 and 9.** Their surviving contrast is real but
was never about chess skill. The most likely reading of all three tracks
together is that "saving lost positions" mostly measures whether the losing
player is in a setting where playing on is normal.

## Track 10: do the findings survive the choices that produced them?

Every earlier track reports one specification, chosen from dozens of defensible
alternatives: where a blunder threshold sits, how many opening plies count as
book, how long a game must be, whether losses are winsorised. Reporting one path
through those choices is a garden of forking paths even when each step is
reasonable. This track re-runs the main estimands across every combination.

**The blunder gradient is completely robust.** All 180 specifications find a
negative gradient across rating bands, ranging from −0.0075 to −0.0285 per band
step. The reported specification sits at the 74th percentile, so if anything it
understates the effect relative to the median choice.

**The fast-versus-slow difference is completely robust.** All 180
specifications find faster games blundering more, ranging from +0.004 to
+0.018. The reported specification sits at the 68th percentile.

**One arbitrary choice dominates.** The blunder threshold alone accounts for
94% of the spread in the gradient and 50% in the fast-slow difference. Opening
plies skipped, minimum game length and endgame truncation together account for
almost nothing. That is worth stating plainly: the single most consequential
decision in track 3 was a cutoff picked because 300cp is conventional, and it
deserved an argument rather than a default. It does not change the sign, but it
moves the magnitude by nearly a factor of four.

**A trap worth naming.** The ACPL drift curve is positive in all 144
specifications, which reads as strong evidence and is not. Every specification
runs on the same games, so agreeing with each other costs them nothing. Track
4's interval on that same unadjusted quantity is −0.20 to +2.85 and includes
zero. Sign consistency across specifications and statistical significance are
different properties, and a specification curve speaks only to the first.

**What the curve cannot do.** It does not fix a confound and does not make an
underpowered null informative. Tracks 7 and the power report cover those.

## Appendix: how much engine compute should a group comparison buy?

`scripts/calibrate_nodes.py` asks whether fixed compute is better spent on more
games at shallower search or fewer at deeper. The reasoning is that
misclassification unrelated to the grouping attenuates a group estimate toward
zero rather than reordering it, while sample size buys interval width at the
square root, so shallow-and-many may win outright.

**The cost side is settled.** Measured on this machine: 0.99 seconds per game
at 5,000 nodes against 9.84 at 80,000, a 10x speedup that would buy roughly 3x
narrower intervals at equal compute.

**The accuracy side needed a second attempt.** A first run on 24 games gave
gradient retention of 0.90, 0.79 and 1.11 for 5k, 10k and 20k nodes. That
ordering is impossible as a real effect, since a deeper search cannot distort a
group estimate further from its own deeper self, and it is therefore proof the
estimate was noise-dominated. The script refuses to recommend anything on
non-monotone input, which is what saved it from endorsing 5,000 nodes for the
wrong reason.

**Re-run against the production sample, the answer is clear.** Using the
already-evaluated 480-game sample at 20,000 nodes as the reference and
re-scoring the same games at 5,000:

| quantity | 5k vs 20k |
|---|---|
| by-band blunder gradient | 1.043 of reference |
| mean centipawn loss | 1.018 of reference |
| ACPL gradient across bands | 1.014 of reference |
| move-level blunder agreement | 98.3% |
| speed | 4.19x faster |
| implied interval narrowing at equal compute | 2.05x |

Both estimands survive, which matters because they degrade differently: the
gradient depends on a threshold crossing, mean loss on the whole distribution.
Individual move classification is where the shallow budget does lose ground
(80% recall of reference blunders), and that is exactly the quantity none of
the tracks report. Misclassification unrelated to the grouping attenuates a
group estimate toward zero rather than reordering it, and at these budgets even
the attenuation is negligible.

**What this is worth, and where.** For the lichess tracks, nothing: that corpus
is sample-limited rather than compute-limited, since requiring both players in
the same rating band leaves only 44 games in the scarcest cell, so a balanced
design cannot exceed 660 games no matter how cheap evaluation gets. For the
TWIC-based tracks it is worth a great deal, because 172,430 games are available
and the samples are capped purely by engine time. Track 9 currently needs
roughly 927 games per band to resolve a 5-point gap and has 130. At 5,000 nodes
that target costs about the same compute as the current sample did.

## Cross-track thread

The three tracks that measure *skill* agree and the two that measure *outcomes*
diverge from folk expectation.

Skill scales cleanly and boringly: blunder rate falls by a factor of three from
1200 to 2200 (track 3), and centipawn loss tracks rating closely enough to serve
as an anchor, both across players (track 4) and within a single player's career
(track 8). Engine ground truth measures human skill well. Track 6 was originally
listed here as a third example and no longer qualifies: its rating gradient did
not survive removing censoring.

Outcomes do not follow. Engine-assessed opening quality predicts nothing about
practical results at any level (track 2), and White's advantage is larger among
stronger players, not smaller (track 5), despite stronger players having better
access to the engine analysis that supposedly neutralises it. Saving a lost
position turns out not to be a chess-skill phenomenon at all: at matched
engine-measured skill the online advantage grows, and it disappears once both
populations actually play the position out (tracks 9 and 11).

The reconciliation is range: engine evaluation discriminates human skill across
a 1000-point rating span beautifully, and discriminates almost nothing across
the 29cp band that separates real openings from each other. A tool's resolution
is a property of the comparison, not of the tool.
