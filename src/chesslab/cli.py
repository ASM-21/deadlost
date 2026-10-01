"""Command-line interface.

`pyproject.toml` has declared a `chesslab` console script since the first
commit. This module is what it points at.

The design goal is that someone who has cloned this repo can answer three
questions without reading any source: what does it claim, how far can those
claims be trusted, and how do I regenerate them.

    chesslab findings              what the repo concludes, one line per track
    chesslab findings --track 3    the detail for one track
    chesslab limits                resolution bounds and known confounds
    chesslab status                what is built, what is stale, what is missing
    chesslab verify                run every consistency check
    chesslab export                write a documented analysis dataset
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import paths

ROOT = Path(__file__).resolve().parents[2]

#: Track number -> (results file, headline extractor, one-line summary).
#: The summaries are deliberately hedged where the underlying result is weak;
#: a CLI that overstates is worse than no CLI.
TRACKS = {
    1: ("t1_validation.json", "Ingested 190,967 games; TWIC is majority online blitz from 2020 and is filtered to classical."),
    2: ("t2_openings.json", "Engine opening evaluations do not predict practical results (consistent with Park 2026)."),
    3: ("t3_blunders.json", "Blunder rate falls ~3.4x from 1200 to 2200; the time-control effect is borderline."),
    4: ("t4_inflation.json", "No detectable rating drift at fixed rating; replicates Regan & Haworth; underpowered."),
    5: ("t5_color.json", "White's edge grows with strength (replication); classical draw rates are rising."),
    6: ("t6_swindles.json", "Weakest track. Two claims retracted; superseded by track 11."),
    7: ("t7_falsify.json", "Eight probes against the other tracks. One fires (P1)."),
    8: ("t8_player_panel.json", "Within-player drift null; calendar time and ageing are not separable (textbook APC)."),
    9: ("t9_otb_swindles.json", "No save-rate gradient across OTB ratings; the online/OTB gap is not about strength."),
    10: ("t10_multiverse.json", "Specification curves with joint inference: rating gradient robust, time effect borderline."),
    11: ("t11_matched_skill.json", "New: lost positions are saved online because OTB players concede; same 558 players mate 11.6 pts more online."),
    12: ("t12_titled_tuesday.json", "Independent replication of 11 via FIDE-ID linkage; gap holds at matched time control; ~30% of online losses are flags."),
}


def _load(name: str) -> dict | None:
    p = paths.RESULTS / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def cmd_findings(args) -> int:
    if args.track:
        n = args.track
        if n not in TRACKS:
            print(f"no track {n}; available: {sorted(TRACKS)}")
            return 1
        fname, summary = TRACKS[n]
        d = _load(fname)
        if d is None:
            print(f"track {n} not built. Run: ./scripts/build_all.sh")
            return 1
        print(f"Track {n}: {summary}\n")
        print(json.dumps(d, indent=2, default=str)[: args.chars])
        if len(json.dumps(d, default=str)) > args.chars:
            print(f"\n... truncated; full file at results/{fname}")
        return 0

    print("chess-lab findings\n")
    for n, (fname, summary) in sorted(TRACKS.items()):
        built = "  " if (paths.RESULTS / fname).exists() else " !"
        print(f"{built}{n:>3}. {summary}")
    print("\n ! = not built. Detail: chesslab findings --track N")
    print(" Caveats and resolution bounds: chesslab limits")
    return 0


def cmd_limits(args) -> int:
    """What the repo cannot conclude. Printed as prominently as the findings."""
    print("What this data can and cannot resolve\n")

    p = _load("power_report.json")
    if p:
        c = p.get("clustering", {})
        if c:
            print(f"Clustering penalty: {c['implied_design_effect_on_sample_size']:.2f}x sample "
                  "needed for the same resolution.\n")
        print(f"{'null':44s} {'resolution':>12s}  ruled out?")
        print("-" * 78)
        for name, v in p.get("nulls", {}).items():
            res = v.get("resolution_half_width", v.get("mde"))
            if v.get("benchmark_would_have_been_detected") is not None:
                verdict = "yes" if v["benchmark_would_have_been_detected"] else "NO - underpowered"
            elif v.get("benchmark_detectable") is not None:
                verdict = "yes" if v["benchmark_detectable"] else "NO - underpowered"
            else:
                verdict = ""
            print(f"{name:44s} {res:12.4g}  {verdict}")
    else:
        print("power report not built. Run: python scripts/power_report.py")

    print("\nRetracted claims:")
    findings = ROOT / "FINDINGS.md"
    if findings.exists():
        for line in findings.read_text().splitlines():
            if line.startswith("### RETRACTED"):
                print(f"  - {line.replace('### ', '')}")

    print("\nKnown confounds that no amount of data here fixes:")
    for line in (
        "track 2: opening choice is self-selected, so a line's score partly measures who plays it",
        "track 4: inflation and population change predict identical trends at fixed rating",
        "TWIC 2020+: majority online blitz with no time-control tag; classical analyses depend on the "
        "format inferred from event and site headers",
        "track 8: within a player, calendar year and career stage are the same regressor",
        "track 6/9: online rapid and OTB classical do not overlap in rating, so format and strength "
        "cannot be separated",
    ):
        print(f"  - {line}")
    return 0


def cmd_status(args) -> int:
    """What exists, what is stale, what is missing."""
    print("chess-lab status\n")

    corpus = paths.GAMES_PARQUET
    print(f"corpus:      {'built' if corpus.exists() else 'MISSING (run scripts/fetch_data.sh)'}")

    for tag in ("lichess", "twic", "panel", "otb"):
        d = paths.EVAL / tag
        n = len(list(d.glob("shard_*.parquet"))) if d.exists() else 0
        print(f"engine {tag:8s} {f'{n} shards' if n else 'not evaluated'}")

    missing = [n for n, (f, _) in sorted(TRACKS.items()) if not (paths.RESULTS / f).exists()]
    print(f"\ntracks built: {len(TRACKS) - len(missing)}/{len(TRACKS)}"
          + (f"  (missing: {missing})" if missing else ""))

    man = paths.RESULTS / "manifest.json"
    if man.exists():
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "manifest.py"), "check"],
            capture_output=True, text=True,
        )
        print(f"manifest:    {'no drift' if r.returncode == 0 else 'DRIFT DETECTED (chesslab verify)'}")
    else:
        print("manifest:    not written")
    return 0


def cmd_verify(args) -> int:
    """Every consistency check the repo has, in one command."""
    checks = [
        ("tests", [sys.executable, "-m", "pytest", "-q"]),
        ("claims", [sys.executable, str(ROOT / "scripts" / "check_claims.py")]),
        ("manifest", [sys.executable, str(ROOT / "scripts" / "manifest.py"), "check"]),
    ]
    failed = []
    for name, cmd in checks:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        status = "pass" if r.returncode == 0 else "FAIL"
        print(f"[{status}] {name}")
        if r.returncode != 0:
            failed.append(name)
            tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
            for line in tail:
                print(f"       {line}")
    return 1 if failed else 0


def cmd_export(args) -> int:
    from .export import export_all

    written = export_all(Path(args.out) if args.out else None)
    for p in written:
        print(f"wrote {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="chesslab", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    f = sub.add_parser("findings", help="what the repo concludes")
    f.add_argument("--track", type=int, help="detail for one track")
    f.add_argument("--chars", type=int, default=4000, help="max characters of detail to print")
    f.set_defaults(func=cmd_findings)

    l = sub.add_parser("limits", help="resolution bounds, retractions and confounds")
    l.set_defaults(func=cmd_limits)

    s = sub.add_parser("status", help="what is built and whether it has drifted")
    s.set_defaults(func=cmd_status)

    v = sub.add_parser("verify", help="run tests, claims check and manifest check")
    v.set_defaults(func=cmd_verify)

    e = sub.add_parser("export", help="write a documented analysis dataset")
    e.add_argument("--out", type=str, default=None)
    e.set_defaults(func=cmd_export)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
