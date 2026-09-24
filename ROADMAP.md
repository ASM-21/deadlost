# Roadmap

## Known gaps in v0.1.0

**The corpus cannot answer the fast-time-control question.** Track 3's original
threshold question needs bullet and blitz games. The Lichess open database
publishes monthly dumps that contain them; the current build uses a GitHub
mirror because `database.lichess.org` is not reachable from every environment.
Ingesting one real monthly dump, filtered to bullet and blitz, would make the
threshold question testable and is the single highest-value next step.

**The engine sample is small.** 1,228 games out of 190,967. Corpus-wide claims
(results, colour, openings) use everything, but every centipawn claim rests on
the sample. Doubling it is pure compute, no new design work.

**Track 6 is the weakest track.** Two probes fire against it. Worth either
rebuilding on a larger, uncensored sample (evaluate to game end rather than
ply 120) or narrowing its claims further.

**~~Player identity is unused.~~ Done in track 8.** It worked as intended on the
composition confound and ran straight into the age-period-cohort problem: within
a player, calendar year and career stage are the same regressor. The remaining
gap is *power*, not design. 34 players and 201 player-years cannot support a
career-curvature term. Roughly 100 players would make that spec informative and
is pure compute.

**~~Track 6 needs rebuilding or retiring.~~ Superseded by track 11.** Its
surviving contrast turned out to be real but not about chess: over-the-board
players resign lost positions and online players play them out. Tracks 6 and 9
are now best read as inputs to track 11 rather than as findings in their own
right, and the FINDINGS text says so.

**Open question track 11 raises.** "Stopped early" bundles resignation with
losing on time and the two cannot be separated for TWIC, which has no
termination tags. A corpus with reliable tags on both sides, or one where
clock data survives, would pin the resignation rate exactly rather than
bounding it.

**Old note, kept for context:** **Track 6 needs rebuilding or retiring.** Removing censoring destroyed its
monotonicity claim and probe P1 destroyed its secondary one. What is left is one
contrast confounded with playing format. Either find a corpus where rating and
format can be varied independently, or drop the track.

## After 1.1.0

**Redraw the TWIC samples from classical games only.** The current samples were
drawn before the format problem was known; filtering at load time left 292 of
348, 378 of 520 and 926 of 1,161 games. A classical-only redraw at the validated
5,000-node budget would restore the lost power, at the cost of changing every
sampled game and every pinned number.

**Position-level track 2.** Park (2026) finds most of the engine-versus-human
signal within opening families. Track 2 aggregates across them.

**Resignation versus time forfeit over the board.** Needs a tournament source
with termination tags.

## The concrete next step (from 1.0.0)

**Re-run the TWIC-based samples at 5,000 nodes and spend the savings on more
games.** The calibration (see FINDINGS.md) validates the cheaper budget on two
estimands at n=480: the by-band gradient and mean centipawn loss both land
within 2% of their 20,000-node values, for a 4.19x speedup.

This does NOT apply to the lichess sample, which is limited by the corpus
rather than by compute: the scarcest rating-band-by-time-control cell holds 44
games, so a balanced design caps out at 660 regardless of budget. Scaling it
would buy 1.18x narrower intervals in exchange for re-pinning every headline,
which is not worth it.

It applies fully to tracks 4, 8 and 9, which draw on 172,430 available TWIC
games and are capped only by engine time:

- Track 9 needs ~927 games per band to resolve a 5-point save-rate gap and has
  130. At 5k nodes that is reachable in roughly the compute the current sample
  already cost.
- ~~Track 8's panel needs ~100 players to support a career-curvature term and
  has 34.~~ **Done, and the prediction was wrong.** At 100 players the curvature
  spec is still uninformative (interval ~±6.5 cp/decade, curvature term spanning
  zero). The limit is collinearity between calendar year and career stage, not
  sample size, so no panel size fixes it. The expansion was still worth doing:
  it revealed that the 34-player point estimate had the opposite sign.
- Track 4 would tighten its ±1.3 cp/decade bound toward the ~0.5 cp/decade that
  would actually settle the inflation question.

Do it as one re-run at a single budget rather than mixing 20k and 5k
evaluations in one sample, and re-run the multiverse afterwards: the blunder
threshold drives 94% of the spread in track 3, and threshold crossings are the
quantity most sensitive to search depth.

## Candidate tracks

- **Time-pressure within a game.** Lichess PGN dumps carry per-move clock
  times. Blunder rate against *remaining clock* is the question track 3 actually
  wanted, and it is answerable with the right dump.
- **Opening novelty decay.** How long does a new idea keep scoring above the
  line before results regress? TWIC's 28-year span suits this.
- **Draw-rate decomposition.** Track 5 found falling draw rates in TWIC, which
  contradicts the common claim. Whether that is TWIC's event mix, faster
  classical controls, or something real deserves its own track.
- **Engine-agreement as an anchor.** ACPL is one skill proxy; top-move
  agreement rate is another with different failure modes. Agreement between the
  two anchors would strengthen track 4's null.

## Not planned

- Cheat detection. The methods overlap, the ethics and false-positive costs do
  not fit a repository like this one.
- Anything requiring per-account data from a live site API.
