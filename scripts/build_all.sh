#!/usr/bin/env bash
# Full rebuild. Engine work dominates: budget roughly 45-60 minutes on one core.
# Every engine stage is resumable, so re-running after an interrupt continues
# where it stopped rather than starting over.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:/usr/games"

echo "== track 1: ingest ==";        python -m deadlost.tracks.t1_ingest
echo "== engine: lichess sample ==";  python -m deadlost.eval_run --which lichess --nodes 20000
echo "== engine: twic sample ==";     python -m deadlost.eval_run --which twic --nodes 20000
echo "== engine: player panel ==";    python -m deadlost.eval_run --which panel --nodes 20000
echo "== engine: otb bands ==";       python -m deadlost.eval_run --which otb --nodes 20000
echo "== track 2: openings ==";       python -m deadlost.tracks.t2_openings
echo "== track 3: blunders ==";       python -m deadlost.tracks.t3_blunders
echo "== track 4: inflation ==";      python -m deadlost.tracks.t4_inflation
echo "== track 5: colour ==";         python -m deadlost.tracks.t5_color
echo "== track 6: swindles ==";       python -m deadlost.tracks.t6_swindles
echo "== track 8: player panel ==";   python -m deadlost.tracks.t8_player_panel
echo "== track 9: otb swindles ==";   python -m deadlost.tracks.t9_otb_swindles
echo "== track 7: falsification ==";  python -m deadlost.tracks.t7_falsify
echo "== track 12: titled tuesday ==";  python -m deadlost.tracks.t12_titled_tuesday
echo "== track 11: matched skill ==";  python -m deadlost.tracks.t11_matched_skill
echo "== track 10: multiverse ==";    python -m deadlost.tracks.t10_multiverse
echo "== power report ==";            python scripts/power_report.py
echo "== claims check ==";            python scripts/check_claims.py
echo "== tests ==";                   python -m pytest -q
echo "== export dataset ==";         python -m deadlost.cli export
echo "== findings page ==";           python scripts/make_report.py
echo "== manifest ==";                python scripts/manifest.py write
