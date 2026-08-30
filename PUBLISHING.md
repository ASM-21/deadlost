# Publishing this repository

Everything below is done except the final push, which needs credentials this
repository was built without. The git history and tags are already in place, so
publishing is three commands.

## 1. Set the repository URL

Badge and issue-template links carry an explicit `OWNER` placeholder rather than
a guess. One command rewrites them:

```bash
python scripts/init_repo.py <your-github-username>        # or: <owner> <repo-name>
python scripts/init_repo.py --check                        # verifies none remain
git commit -am "Set repository URLs"
```

## 2. Push

The repository is already committed and tagged (`v1.0.0` and
`findings-2026-08`). No corpus or engine output is tracked; `git count-objects`
reports a source-only tree of 90 files.

```bash
git remote add origin git@github.com:<owner>/chess-lab.git
git push -u origin main --tags
```

## 3. Repository settings

- **Description**: Eleven falsifiable analyses of 190,967 public chess games
  with Stockfish ground truth, including a falsification track, specification
  curves, and resolution bounds on every null.
- **Topics**: `chess` `stockfish` `lichess` `reproducible-research`
  `falsification` `specification-curve` `open-data` `statistics` `python`
  `data-analysis`
- **Social preview**: upload `assets/banner.svg` (or a PNG render of it).
- **Pages**: serve from `/docs` to publish the generated findings page.

## Verifying it worked

```bash
git clone https://github.com/<owner>/chess-lab && cd chess-lab
pip install -e ".[dev]" && python -m pytest -q      # 117 tests, 2 skip without the corpus
chesslab findings
```

The suite is designed to pass on a fresh clone with no corpus and no engine:
tests that need fetched data skip rather than fail, and tests that need
Stockfish are behind the `slow` marker. This was verified by installing into a
clean virtualenv, not assumed.
