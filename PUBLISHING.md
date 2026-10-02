# Publishing this repository

Everything is done except the push, which needs credentials this repository was
built without. Repository URLs, author identity, licence and tags are already
set, so publishing is two commands.

## 1. Push

```bash
git remote add origin git@github.com:ASM-21/deadlost.git
git push -u origin main --tags
```

Every commit is authored as `Andrew Morrissey
<77601626+ASM-21@users.noreply.github.com>`, the address GitHub attributes to
the ASM-21 account. Tags: `v1.1.0` and `findings-2026-09` mark the citable
release. `v1.0.0` is kept for history but its results are superseded; see
CHANGELOG.md for why it should not be cited.

## 2. Repository settings

- **Description**: Nine claims about chess tested on 190,967 public games with
  Stockfish, positioned against the literature, with a falsification track and
  resolution bounds on every null.
- **Topics**: `chess` `stockfish` `lichess` `reproducible-research`
  `falsification` `specification-curve` `open-data` `statistics` `python`
- **Social preview**: upload a PNG render of `assets/banner.svg`.
- **Pages**: serve from `/docs` to publish the generated findings page.
- **Release**: create a GitHub release from `v1.1.0` so Zenodo, if connected,
  mints a DOI for the citable version.

## Verifying it worked

```bash
git clone https://github.com/ASM-21/deadlost && cd deadlost
pip install -e ".[dev]" && python -m pytest -q    # passes with no corpus and no engine
bash scripts/fetch_data.sh && make tracks            # reproduces every pinned number from committed engine output
python scripts/check_claims.py
```

Engine evaluations are committed in `data/eval/`, so reproducing the analysis
needs the ~150 MB corpus fetch but not the hour of engine time.
