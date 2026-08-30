# FAQ

### Is this "chess research" or a stats demo?

Both, honestly. The questions are real chess questions and the answers are
computed from real games, but the reason to read the repo is the method: what it
does when a result does not survive scrutiny. Two claims were withdrawn, three
nulls are labelled as underpowered against the effects people care about, and
five bugs found during the build are documented rather than quietly fixed.

### Why not use the full Lichess database?

`database.lichess.org` is not reachable from every environment, so the corpora
here come from stable GitHub mirrors. That decision bounds several results and
is stated up front rather than buried: the online sample is one 2017 scrape and
is almost entirely rapid, which is why the bullet-versus-blitz question in track
3 is marked untestable instead of answered.

### Which findings should I actually trust?

In descending order:

1. **Track 3** (blunder rate by rating and time control). Survives all 180
   analytic specifications, a label-permutation null, and a 4x deeper engine.
2. **Track 5** (White's advantage). Large corpus, simple estimand, composition
   artifact identified and reported alongside the corrected version.
3. **Track 2** (openings). A clean null, but see the resolution bound.
4. **Tracks 4 and 8** (inflation). Two designs, two nulls, neither powered to
   rule out the drift rate commonly claimed.
5. **Track 11** (why the save-rate gap exists). A strong identification chain
   with a directly measured mechanism, but built on the narrow overlap between
   two unusual subpopulations.
6. **Tracks 6 and 9** (saving lost positions). The weakest work here. Two
   retractions, and their surviving contrast turned out not to be about chess
   skill at all; read them as inputs to track 11.

`chesslab limits` prints this in machine-checkable form.

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

Track 11. Lost positions are saved more than twice as often online as over the
board, and the reason is not that online players defend better. It is that
over-the-board players resign: of those who ended up losing, 5.8% played the
position to checkmate against 32.0% online. You cannot save a game you have
already resigned.

Getting there required noticing that the metadata thought to be necessary was
not necessary at all. TWIC carries no termination tags, which looked like a dead
end, until it became clear that checkmate is recoverable from the move list
itself, and that the recovery could be validated against the corpus that does
carry tags before being trusted on the corpus that does not.

### Something looks wrong.

Please [challenge it](../.github/ISSUE_TEMPLATE/challenge-a-finding.yml). That is
the contribution this project most wants.
