#!/usr/bin/env bash
# Full analysis pipeline: ghost_hunt → dispersal_map → collision
# Run from project root: bash analysis/pipeline.sh
#
# Requires: uv (from parent project), requests library
# Data:     ../../data/wwi_extended.jsonl (354 articles)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CORPUS="${1:-../../data/wwi_extended.jsonl}"

echo "========================================"
echo "Wikipedia Institutional Fetishism"
echo "Reproducible Analysis Pipeline"
echo "Corpus: $CORPUS"
echo "========================================"
echo ""

echo "[1/3] Ghost Hunt — reverse search for empty-category terms in corpus text"
uv run --project ../../ python analysis/ghost_hunt.py --corpus "$CORPUS"

echo ""
echo "[2/3] Dispersal Map — fetch real Wikipedia categories for ghost-term articles"
uv run --project ../../ python analysis/dispersal_map.py

echo ""
echo "[3/3] Collision Analysis — co-occurrence and character distance between ghost terms"
uv run --project ../../ python analysis/collision.py

echo ""
echo "========================================"
echo "Pipeline complete. Output files:"
ls -lh output/
echo ""

# Reconciliation: vault claims vs. actual numbers
echo "========================================"
echo "Reconciliation: vault claims vs. actual"
echo "========================================"
if [ -f output/ghost_summary.json ]; then
    echo ""
    echo "Ghost term article counts:"
    echo "  Claim: Assassination=67, Western Front=23, Lenin=10, Bolshevism=6"
    echo "  Actual:"
    uv run --project ../../ python -c "
import json
with open('output/ghost_summary.json') as f:
    s = json.load(f)
for term, stats in s.items():
    print(f'    {term}: {stats[\"article_count\"]} articles, {stats[\"total_mentions\"]} mentions')
"
fi

if [ -f output/dispersal.json ]; then
    echo ""
    echo "Dispersal (unique categories per ghost term):"
    echo "  Claim: Assassination scatters across 757 categories"
    echo "  Actual:"
    uv run --project ../../ python -c "
import json
with open('output/dispersal.json') as f:
    d = json.load(f)
for term, stats in d.items():
    print(f'    {term}: {stats[\"article_count\"]} articles → {stats[\"unique_categories\"]} unique categories')
"
fi
