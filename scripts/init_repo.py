"""Replace the OWNER/REPO placeholders in badges, templates and links.

Badge and issue-template URLs cannot be written until the repository has a
home. Rather than leaving dead links for someone to find later, they use an
explicit `OWNER` placeholder and this script rewrites them in one pass.

Usage:
    python scripts/init_repo.py andrew            # github.com/andrew/chess-lab
    python scripts/init_repo.py andrew my-fork    # github.com/andrew/my-fork
    python scripts/init_repo.py --check           # exit 1 if placeholders remain
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "README.md",
    "CITATION.cff",
    ".github/ISSUE_TEMPLATE/config.yml",
    "docs/FAQ.md",
    "CHANGELOG.md",
]
PLACEHOLDER = re.compile(r"github\.com/OWNER/chess-lab")


def check() -> int:
    stale = []
    for rel in TARGETS:
        p = ROOT / rel
        if p.exists() and PLACEHOLDER.search(p.read_text()):
            stale.append(rel)
    if stale:
        print("placeholders still present in:")
        for s in stale:
            print(f"  {s}")
        print("\nRun: python scripts/init_repo.py <github-owner> [repo-name]")
        return 1
    print("no placeholders remain")
    return 0


def apply(owner: str, repo: str) -> int:
    changed = []
    for rel in TARGETS:
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text()
        new = PLACEHOLDER.sub(f"github.com/{owner}/{repo}", text)
        if new != text:
            p.write_text(new)
            changed.append(rel)
    print(f"set repository to {owner}/{repo}")
    for c in changed:
        print(f"  updated {c}")
    if not changed:
        print("  (nothing to change)")
    print("\nAlso worth doing in GitHub settings:")
    print("  - set assets/banner.svg as the social preview image")
    print("  - add topics: chess, stockfish, reproducible-research, falsification, open-data")
    print("  - enable Pages from /docs to publish the findings report")
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    if args[0] == "--check":
        return check()
    owner = args[0]
    repo = args[1] if len(args) > 1 else "chess-lab"
    return apply(owner, repo)


if __name__ == "__main__":
    sys.exit(main())
