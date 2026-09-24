# FAQ

### Is this "chess research" or a stats demo?

Both, honestly. The questions are real chess questions and the answers are
computed from real games, but the reason to read the repo is the method: what it
does when a result does not survive scrutiny. Two claims were withdrawn, three
nulls are labelled as underpowered against the effects people care about, and
five bugs found during the build are documented rather than quietly fixed.

### Is any of this new?

Mostly not, and the repository says which parts are which. The literature
review (docs/LITERATURE.md) found that the rating-drift design, the White
advantage gradient and the age-period-cohort limit are all established. What is
new is claim 9, and some of the method: format inference for TWIC, the
decided-position filter, and joint inference applied to these questions.

### Why not use the full Lichess database?

`database.lichess.org` is not reachable from every environment, so the corpora
here come from stable GitHub mirrors. That decision bounds several results and
is stated up front rather than buried: the online sample is one 2017 scrape and
is almost entirely rapid, which is why the bullet-versus-blitz question in track
3 is marked untestable instead of answered.

### Which findings should I actually trust?

In descending order of confidence:

1. **Claim 1** (blunder rate falls with rating). Survives all 180 analytic
   specifications under joint inference (p = 0.002), a permutation null, and a
   fourfold-deeper engine. It is also a replication of well-known work.
2. **Claim 9** (lost positions are saved online because over-the-board players
   resign). A large, precise difference measured without conditioning on
   anything after the position is lost, with its online half checked against
   independent Lichess statistics. Rests on a 114-game over-the-board sample.
3. **Claim 4** (White's edge grows with strength). Large corpus, simple
   estimand, known result.
4. **Claims 5 and 6** (rising draws; opening evaluations). Consistent with
   recent literature, not independent tests of it.
5. **Claim 2** (time control). Borderline once analytic flexibility is
   accounted for.
6. **Claims 7 and 8** (rating drift). Nulls that cannot rule out moderate
   drift in either direction.

`chesslab limits` prints this in machine-checkable form.

### Was anything in this repository wrong?

Yes, six things, all listed in FINDINGS.md. The largest was that the tournament
corpus, The Week In Chess, became majority online blitz in 2020, and three
results built on it were really measuring the switch from classical to online
play. No test caught it. A literature search did: a 2026 paper found classical
draw rates rising after 2020, this repository found them falling, and the
contradiction led straight to the data.

### Why is the engine budget fixed by nodes instead of time?

So the numbers reproduce. A time budget makes evaluation depend on machine load,
which would mean a blunder measured on a busy afternoon differs from the same
blunder measured overnight. Nodes are deterministic, provided the transposition
table is also reset per game, which is a bug this repo shipped before fixing.

### 20,000 nodes is shallow. Does that matter?

Less than intuition suggests, and it was measured rather than assumed. At
n=480, re-scoring the same games at 5,000 nodes reproduces the by-band blunder
gradient to within 4% and mean centipawn loss to within 2%. Individual move
classification is where shallow search loses ground, and no track reports
individual moves. Misclassification unrelated to the grouping attenuates a group
estimate toward zero rather than reordering it.

### Can I reuse the evaluations?

Yes, that is the point of `chesslab export`. It writes 125,673 scored moves
joined to game metadata plus a data dictionary. The evaluations are the only
expensive artifact here; everything else is minutes of pandas.

### Why are there so many caveats?

Because the alternative is a repo that sounds more certain than its data
supports. Every limitation listed is one that changed a conclusion or bounds a
claim. None of them are ritual hedging: if a caveat did not affect what could be
said, it was cut.

### What is the single most interesting result?

Claim 9. Lost positions are saved far more often online than over the board, and
the reason is not that online players defend better. It is that over-the-board
players resign: of those who ended up losing, 3.5% played the position to
checkmate in classical play against 32.0% online. You cannot save a game you have
already resigned. No prior study comparing this across formats was found.

Getting there required noticing that the metadata thought to be necessary was
not necessary at all. TWIC carries no termination tags, which looked like a dead
end, until it became clear that checkmate is recoverable from the move list
itself, and that the recovery could be validated against the corpus that does
carry tags before being trusted on the corpus that does not.

### Something looks wrong.

Please [challenge it](../.github/ISSUE_TEMPLATE/challenge-a-finding.yml). That is
the contribution this project most wants.
