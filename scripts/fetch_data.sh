#!/usr/bin/env bash
# Fetch the two public corpora and the opening tables.
# Both sources are GitHub mirrors: database.lichess.org is not reachable from
# every environment, and these mirrors are stable and small enough to script.
set -euo pipefail
cd "$(dirname "$0")/.."
RAW=data/raw
mkdir -p "$RAW/twic"

echo "==> lichess 2017 CSV (~7.7 MB)"
curl -fsSL -o "$RAW/lichess_games_2017.csv" \
  "https://raw.githubusercontent.com/ogreowl/chess-analysis/main/data/games.csv"

echo "==> lichess ECO opening tables"
for L in a b c d e; do
  curl -fsSL -o "$RAW/eco_$L.tsv" \
    "https://raw.githubusercontent.com/lichess-org/chess-openings/master/$L.tsv"
done

echo "==> TWIC issues, every 26th from 210 to 1649 (~138 MB, 56 files)"
seq 210 26 1649 | xargs -P 8 -I{} sh -c \
  'test -s '"$RAW"'/twic/twic{}.pgn || curl -fsSL --max-time 180 -o '"$RAW"'/twic/twic{}.pgn \
   "https://raw.githubusercontent.com/rozim/ChessData/master/Twic/twic{}.pgn"'

echo "==> done"
du -sh "$RAW"
