## What this changes

<!-- One or two sentences. -->

## If this changes a number

Numbers in this repo are pinned in two places so they cannot drift silently.
Tick what applies:

- [ ] Re-ran the affected track(s)
- [ ] Updated the assertion in `tests/test_headlines.py`
- [ ] Updated the entry in the `CLAIMS` registry in `scripts/check_claims.py`
- [ ] Updated the prose in `README.md` / `FINDINGS.md`
- [ ] Re-ran `python scripts/manifest.py write`

## If this adds a finding

- [ ] The question could have come out "no"
- [ ] Intervals resample the right cluster (games for move-level data, players for player-level)
- [ ] Group differences are tested as differences, not by comparing interval overlap
- [ ] The limitations field says what the design cannot settle
- [ ] A resolution bound is reported if the result is a null

## Checks

```
deadlost verify
```

- [ ] `tests` pass
- [ ] `claims` pass
- [ ] `manifest` pass
