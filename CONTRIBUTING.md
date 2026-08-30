# Contributing

The bar here is not code style, it is whether a number can be trusted.

## Adding or changing a finding

1. **State the question so it can come out "no".** If no result would falsify
   it, it is not a track.
2. **Cluster correctly.** Move-level data resamples games. Player-level data
   resamples players. `stats.cluster_bootstrap` exists for this; using
   `wilson_ci` on move-level data is a bug, not a shortcut.
3. **Test differences as differences.** Do not compare two intervals for
   overlap. See `t3_blunders.fast_vs_slow_difference`.
4. **Pin the number.** Add an assertion to `tests/test_headlines.py` and an
   entry to the `CLAIMS` registry in `scripts/check_claims.py`. A number in the
   README with no registered source fails the build by design.
5. **Say what the design cannot settle.** Every track's results JSON carries a
   limitations field. An unstated confound is worse than a missing track.

## Adding a falsification probe

Probes live in `tracks/t7_falsify.py`. A probe needs a stated pass condition
before it is run, not after. A probe that fires is a result: downgrade the
affected claim in FINDINGS.md, do not tune the probe until it passes.

## Data

Do not commit corpus files. `scripts/fetch_data.sh` retrieves everything from
upstream. If you add a source, add it to the table in README.md and to NOTICE
with its licence.

## Engine work

Engine stages must be resumable and checkpointed. Assume the process will be
killed. Use fixed node budgets, never fixed time, so results reproduce across
machines.

## Running things

```bash
pip install -e ".[dev]"
python -m pytest -q
python scripts/check_claims.py
```

Both must pass before a change lands.

## Engine hygiene, learned the hard way

Two bugs shipped in this repo before being caught. Both are now guarded by
probes in track 7, and both are easy to reintroduce.

**Reset the transposition table per game.** Stockfish carries hash entries
across searches. Sharing one table across many games makes a result depend on
what was evaluated before it, and therefore on how a resumable run was chunked.
Always pass a `game=` key to `analyse`. Probe P6 fails if this regresses.

**Do not truncate games.** An earlier build stopped at ply 120 and dropped
unfinished games from the analysis, which preferentially discarded long grinding
defences and manufactured a monotone trend that did not exist. Evaluate to the
end. It costs about 10% more.

**Watch for collinear regressors under a within-transformation.** In a fixed
effects model, any regressor that differs from another by a group-constant
becomes identical after demeaning. `career_year` and `year` within a player are
the textbook case. The symptom is two coefficients coming back equal to many
decimal places; the solver will not warn you.
