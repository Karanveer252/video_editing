#!/usr/bin/env bash
# End-to-end local test. Never uploads, posts, pushes or touches any account.
#   tests/run_test_ad.sh [PROJECT_DIR] [HOOK ...]
# PROJECT_DIR must already hold brief.json, ingest/ (ingest.py output) and audio/ (music + beats.json + LICENCES.csv).
# Steps: unit tests -> timelines -> grade (footage + presenter only) -> mix -> render 9x16 + 4x5 -> finish -> QA gates
#        -> contact sheets -> negative QA test (QA must reject a broken file).
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"; P="${1:-$SKILL/test-output/project-v2}"; shift || true
python3 "$SKILL/tests/test_units.py"
cd "$P"
python3 "$SKILL/scripts/build_timeline.py" brief.json --hook "${1:-A}" -o "timeline_${1:-A}.json"
python3 "$SKILL/scripts/grade_segments.py" "timeline_${1:-A}.json"
python3 "$SKILL/scripts/variants.py" brief.json --skip-grade ${@:+--hooks "$@"}
bash "$SKILL/tests/qa_negative.sh" "$P"
echo "end-to-end test ok: see $P/renders/variants_summary.json and $P/sheets/"
