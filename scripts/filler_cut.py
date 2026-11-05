#!/usr/bin/env python3
"""STEP 3b filler cut PROPOSAL (Claude reviews it; nothing is cut blindly).

Reads words.json, marks:
  - filler words (ffmpeg-skill list: um uh erm hmm mm mhm er ah), trimmed 0.02 s either side
  - ambiguous words ("like", "so", "you know", "I mean", "actually", "basically") are FLAGGED, never auto-cut
  - gaps >= --gap seconds between words (video-use: >= 0.4 s silences are the cleanest cut points)
Rules (video-use): never cut inside a word; pad every cut by --pad (default 0.05 s, allowed 0.03 to 0.2);
every kept range gets 30 ms audio fades when extracted (grade_segments.py does that).
Writes cuts.json: {"keep":[[s,e],...], "removed":[...], "flagged":[...], "packed": "text with [cut] marks"}
usage: filler_cut.py words.json -o cuts.json [--gap 0.4 --pad 0.05 --start S --end E]
"""
import argparse, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _common import load, save, die

FILLERS = {"um", "uh", "erm", "hmm", "mm", "mhm", "er", "ah", "umm", "uhh"}
AMBIGUOUS = {"like", "so", "actually", "basically", "literally", "right", "okay"}
AMBIG_PAIRS = {("you", "know"), ("i", "mean"), ("kind", "of"), ("sort", "of")}


def norm(w):
    return re.sub(r"[^a-z']", "", w.lower())


def propose(words, start, end, gap, pad):
    if not 0.03 <= pad <= 0.2:
        die("--pad must be between 0.03 and 0.2 s (video-use rule)")
    words = [w for w in words if w["start"] >= start and w["end"] <= end]
    remove, flagged = [], []
    for i, w in enumerate(words):
        n = norm(w["w"])
        if n in FILLERS:
            remove.append([w["start"] - 0.02, w["end"] + 0.02, f"filler '{w['w']}'"])
        elif n in AMBIGUOUS:
            flagged.append({"t": w["start"], "w": w["w"], "why": "ambiguous filler, Claude decides"})
        if i + 1 < len(words) and (n, norm(words[i + 1]["w"])) in AMBIG_PAIRS:
            flagged.append({"t": w["start"], "w": w["w"] + " " + words[i + 1]["w"], "why": "ambiguous phrase"})
    for a_, b_ in zip(words, words[1:]):
        if b_["start"] - a_["end"] >= gap:
            remove.append([a_["end"] + pad, b_["start"] - pad, f"gap {b_['start'] - a_['end']:.2f}s"])
    # turn removals into keep ranges; never cut inside a kept word
    remove.sort()
    keep, cur = [], start
    for s, e, _ in remove:
        if e <= s:
            continue
        prev = [w for w in words if w["end"] <= s + 1e-6]
        nxt = [w for w in words if w["start"] >= e - 1e-6]
        s2 = max(s, (prev[-1]["end"] + pad) if prev and norm(prev[-1]["w"]) not in FILLERS else s)
        e2 = min(e, (nxt[0]["start"] - pad) if nxt else e)
        if s2 > cur:
            keep.append([round(cur, 3), round(min(s2, end), 3)])
        cur = max(cur, e2)
    if cur < end:
        keep.append([round(cur, 3), round(end, 3)])
    keep = [k for k in keep if k[1] - k[0] > 0.12]
    for k in keep:  # safety: a keep boundary may not fall inside a word
        for w in words:
            for b in k:
                if w["start"] + 0.01 < b < w["end"] - 0.01 and norm(w["w"]) not in FILLERS:
                    die(f"internal error: boundary {b} inside word '{w['w']}'")
    packed = []
    rm = [(s, e) for s, e, _ in remove]
    for w in words:
        cut = any(s - 1e-6 <= w["start"] and w["end"] <= e + 1e-6 for s, e in rm)
        packed.append(f"[{w['w']}]" if cut else w["w"])
    return {"keep": keep, "removed": [{"start": round(s, 3), "end": round(e, 3), "why": y} for s, e, y in remove],
            "flagged": flagged, "packed": " ".join(packed),
            "kept_s": round(sum(e - s for s, e in keep), 3), "source_s": round(end - start, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--gap", type=float, default=0.4); ap.add_argument("--pad", type=float, default=0.05)
    ap.add_argument("--start", type=float, default=0.0); ap.add_argument("--end", type=float)
    a = ap.parse_args()
    d = load(a.words)
    if not d["words"]:
        save({"keep": [], "removed": [], "flagged": [], "packed": "", "note": "no speech; nothing to cut"}, a.out)
        print("no speech; nothing to cut"); return
    end = a.end if a.end is not None else d["words"][-1]["end"] + 0.3
    r = propose(d["words"], a.start, end, a.gap, a.pad)
    save(r, a.out)
    print(f"keep {len(r['keep'])} ranges, {r['kept_s']}s of {r['source_s']}s; removed {len(r['removed'])}; flagged {len(r['flagged'])}")
    print("packed:", r["packed"][:400])


if __name__ == "__main__":
    main()
