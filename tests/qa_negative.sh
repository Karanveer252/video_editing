#!/usr/bin/env bash
# Proves the QA gates can fail. Breaks a passing render on purpose and expects qa.py to exit non-zero:
#   1) BT.601 tags, quiet audio, 44.1 kHz, a jump cut into the end card  -> Q1, Q2, Q9 FAIL
#   2) the presenter opener replaced by a still photo with a fake zoom    -> Q12 FAIL
#   usage: tests/qa_negative.sh [PROJECT_DIR]   (needs renders/ad_A_9x16.mp4 + timeline_A.json)
set -euo pipefail
P="${1:-test-output/project-v2}"; S="$(cd "$(dirname "$0")/.." && pwd)/scripts"
cd "$P"; mkdir -p renders/_neg
EC=$(python3 -c "import json;t=json.load(open('timeline_A.json'));print(next(o for o in t['overlays'] if o['type']=='end_card')['frame_start'])")
ffmpeg -v error -y -i renders/ad_A_9x16.mp4 -vf "select='not(between(n\,$((EC+4))\,$((EC+11))))',setpts=N/30/TB,tpad=stop_mode=clone:stop=8" \
  -af "volume=-8dB" -c:v libx264 -crf 18 -pix_fmt yuv420p -colorspace smpte170m -color_primaries smpte170m -color_trc smpte170m \
  -c:a aac -ar 44100 renders/_neg/broken.mp4
if python3 "$S/qa.py" renders/_neg/broken.mp4 --timeline timeline_A.json --ratio 9x16 > renders/_neg/qa.txt; then
  echo "NEGATIVE TEST FAILED: qa passed a broken file"; exit 1; fi
grep -E "^Q(1|2|9) +FAIL" renders/_neg/qa.txt | cut -c1-140
[ "$(grep -cE '^Q(1|2|9) +FAIL' renders/_neg/qa.txt)" = 3 ] || { echo "NEGATIVE TEST FAILED: Q1/Q2/Q9 did not all fail"; exit 1; }
# 2) still opener: freeze frame 0 of the footage for the whole opener, add a 3% zoom, keep the rest
python3 - <<'PY'
import json
t = json.load(open("timeline_A.json")); s0 = t["segments"][0]
t["footage"]["file"] = "graded/_neg_still_opener.mp4"; json.dump(t, open("renders/_neg/timeline_still.json", "w"))
open("renders/_neg/opener_frames", "w").write(str(s0["frame_end"]))
PY
N0=$(cat renders/_neg/opener_frames)
ffmpeg -v error -y -i graded/footage_graded.mp4 -filter_complex \
  "[0:v]split[a][b];[a]trim=end_frame=1,loop=loop=$((N0-1)):size=1,setpts=N/30/TB,scale=iw*1.03:-2,crop=960:1490,setsar=1[s];[b]trim=start_frame=$N0,setpts=PTS-STARTPTS,setsar=1[r];[s][r]concat=n=2:v=1[o]" \
  -map "[o]" -c:v libx264 -crf 12 -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv graded/_neg_still_opener.mp4
cp renders/_neg/timeline_still.json timeline__neg.json; cp renders/ad_A_9x16.mp4 renders/_neg/still_opener_test.mp4
if python3 "$S/qa.py" renders/_neg/still_opener_test.mp4 --timeline timeline__neg.json --ratio 9x16 > renders/_neg/qa_still.txt; then
  rm -f timeline__neg.json; echo "NEGATIVE TEST FAILED: qa passed a still opener"; exit 1; fi
rm -f timeline__neg.json
grep -E "^Q12 +FAIL" renders/_neg/qa_still.txt | cut -c1-160 || { echo "NEGATIVE TEST FAILED: Q12 did not fail on a still opener"; exit 1; }
echo "negative test ok: qa rejected the broken file and the still opener"
