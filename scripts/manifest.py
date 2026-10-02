"""Content-hash every input, module and result, so drift is detectable.

Two failure modes motivated this, both of which actually happened here.

**Silent code change.** Files in this repository were modified partway through a
build by something outside the session that produced them, and the only reason
it was noticed was a coincidental filesystem listing. Nothing in the output
looked wrong. A manifest turns that from a lucky catch into a diff.

**Silent numeric drift.** A track gets re-run, a headline moves, and the prose
keeps the old number. `check_claims.py` guards the numbers that are written
down; this guards the ones that are not, by recording what every result file
contained at the moment the prose was verified against it.

The manifest records, for each file: SHA256, byte size, and modification time.
Data files are hashed by content, not by name, so a corpus re-fetch that returns
different bytes is visible even if the filename is identical.

Usage:
    python scripts/manifest.py write     # record current state
    python scripts/manifest.py check     # compare against the record, exit 1 on drift
    python scripts/manifest.py diff      # human-readable change list
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "results" / "manifest.json"

#: Globs recorded in the manifest, grouped so a diff says what kind of thing moved.
TRACKED = {
    "code": ["src/deadlost/**/*.py", "scripts/*.py", "tests/*.py"],
    "results": ["results/*.json"],
    "prose": ["README.md", "FINDINGS.md", "ROADMAP.md", "CONTRIBUTING.md", "NOTICE"],
    "config": ["pyproject.toml", "scripts/*.sh", ".github/workflows/*.yml"],
    # Engine output is expensive to regenerate and is the thing most worth
    # knowing has changed. Hashed as whole files; shards are content-addressed
    # by the parquet writer, so a re-run with different settings shows up.
    "engine_data": ["data/eval/**/*.parquet"],
}

#: The manifest records its own hash last, so it never hashes itself.
SELF_EXCLUDE = {"results/manifest.json"}


def _canonical_json(obj):
    """Round floats to 10 significant digits, recursively.

    Results files are regenerated on whatever NumPy and BLAS build the user has.
    Least-squares sums then differ in the last floating-point digit between
    builds (observed: 0.384735296869993 against 0.38473529686998914). That is not
    drift, and hashing raw bytes reported it as drift. Ten significant digits is
    far below the precision any claim in this repository relies on.
    """
    if isinstance(obj, float):
        return float(f"{obj:.10g}")
    if isinstance(obj, dict):
        return {k: _canonical_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_canonical_json(v) for v in obj]
    return obj


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    if path.suffix == ".json":
        try:
            data = _canonical_json(json.loads(path.read_text()))
            h.update(json.dumps(data, sort_keys=True).encode())
            return h.hexdigest()
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect() -> dict:
    entries: dict[str, dict] = {}
    for group, globs in TRACKED.items():
        for pattern in globs:
            for p in sorted(ROOT.glob(pattern)):
                if not p.is_file():
                    continue
                rel = p.relative_to(ROOT).as_posix()
                if rel in SELF_EXCLUDE or "__pycache__" in rel:
                    continue
                st = p.stat()
                entries[rel] = {
                    "group": group,
                    "sha256": sha256(p),
                    "bytes": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                }
    return entries


def environment() -> dict:
    """Record enough of the environment to explain a numeric difference."""
    env: dict = {}
    try:
        import chess

        env["python_chess"] = chess.__version__
    except Exception:  # noqa: BLE001
        pass
    for mod in ("numpy", "pandas", "scipy"):
        try:
            env[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001
            pass
    env["python"] = sys.version.split()[0]
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from deadlost.engine import engine_id

        env["engine"] = engine_id()
    except Exception:  # noqa: BLE001
        env["engine"] = "unavailable"
    try:
        env["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:  # noqa: BLE001
        env["git_commit"] = None
    return env


def write() -> int:
    entries = collect()
    doc = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment(),
        "file_count": len(entries),
        "files": entries,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(doc, indent=2))
    by_group: dict[str, int] = {}
    for v in entries.values():
        by_group[v["group"]] = by_group.get(v["group"], 0) + 1
    print(f"wrote {MANIFEST.relative_to(ROOT)}: {len(entries)} files")
    for g, n in sorted(by_group.items()):
        print(f"  {g:14s} {n}")
    return 0


def compare() -> tuple[list[str], list[str], list[str]]:
    if not MANIFEST.exists():
        raise FileNotFoundError("no manifest; run: python scripts/manifest.py write")
    recorded = json.loads(MANIFEST.read_text())["files"]
    current = collect()
    added = sorted(set(current) - set(recorded))
    removed = sorted(set(recorded) - set(current))
    changed = sorted(
        f for f in set(current) & set(recorded) if current[f]["sha256"] != recorded[f]["sha256"]
    )
    return added, removed, changed


def check() -> int:
    added, removed, changed = compare()
    if not (added or removed or changed):
        print("manifest check passed: no drift")
        return 0
    print("manifest check FAILED\n")
    for label, items in (("CHANGED", changed), ("ADDED", added), ("REMOVED", removed)):
        for f in items:
            print(f"  {label:8s} {f}")
    print(
        "\nIf these changes are intended, re-run the affected tracks, re-run "
        "scripts/check_claims.py, then: python scripts/manifest.py write"
    )
    return 1


def diff() -> int:
    added, removed, changed = compare()
    recorded = json.loads(MANIFEST.read_text())
    print(f"manifest written {recorded['created_utc']}")
    print(f"environment: {json.dumps(recorded.get('environment', {}))}\n")
    if not (added or removed or changed):
        print("no changes")
        return 0
    cur = collect()
    for f in changed:
        old = recorded["files"][f]
        new = cur[f]
        delta = new["bytes"] - old["bytes"]
        print(f"CHANGED  {f}  ({old['bytes']} -> {new['bytes']} bytes, {delta:+d})")
    for f in added:
        print(f"ADDED    {f}  ({cur[f]['bytes']} bytes)")
    for f in removed:
        print(f"REMOVED  {f}")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "write":
        return write()
    if cmd == "check":
        return check()
    if cmd == "diff":
        return diff()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
