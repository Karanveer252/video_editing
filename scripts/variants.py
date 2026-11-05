#!/usr/bin/env python3
"""STEP 10 batch hook variants that share ONE middle (one-variable rule: only the hook line changes).

  variants.py brief.json [--hooks A B C] [--ratio 9x16 4x5] [--skip-grade]

Shared once: selects, grade (graded/footage_graded.mp4), music + SFX mix (identical cue times for every hook,
because the hook sits on the same first bar). Per hook: timeline_<id>.json, render, finish, QA.
Writes renders/variants_summary.json. Exit 1 if any variant fails a QA gate.
"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _common import load, save, die

S = Path(__file__).resolve().parent


def py(*args):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run([sys.executable, *map(str, args)]).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brief"); ap.add_argument("--hooks", nargs="+"); ap.add_argument("--ratio", nargs="+", default=["9x16", "4x5"])
    ap.add_argument("--skip-grade", action="store_true")
    a = ap.parse_args()
    brief = load(a.brief); base = Path(a.brief).resolve().parent
    hooks = a.hooks or [h["id"] for h in brief["hooks"]]
    import os; os.chdir(base)
    tls = []
    for h in hooks:
        if py(S / "build_timeline.py", "brief.json", "--hook", h, "-o", f"timeline_{h}.json"): die(f"timeline {h} failed")
        tls.append(f"timeline_{h}.json")
    # the middle must be identical across variants: same segments, overlays, sfx
    mids = [json.dumps([load(t)[k] for k in ("segments", "overlays", "sfx", "music", "footage")], sort_keys=True) for t in tls]
    if len(set(mids)) != 1: die("variants do not share one middle (segments/overlays/sfx differ)")
    if not a.skip_grade:
        if py(S / "grade_segments.py", tls[0]): die("grade failed")
    Path("renders").mkdir(exist_ok=True)
    if py(S / "mix_audio.py", tls[0], "-o", "renders/_mix_shared.wav"): die("mix failed")
    summary = []
    for h, t in zip(hooks, tls):
        if py(S / "render.py", t, "--ratio", *a.ratio): die(f"render {h} failed")
        n = load(t)["frames"]
        for r in a.ratio:
            out = f"renders/ad_{h}_{r}.mp4"
            if py(S / "finish.py", f"renders/_picture_{h}_{r}.mp4", "renders/_mix_shared.wav", "-o", out, "--frames", n): die("finish failed")
            rc = py(S / "qa.py", out, "--timeline", t, "--ratio", r)
            rep = load(out.replace(".mp4", "_qa_report.json"))
            summary.append({"hook": h, "ratio": r, "file": out, "fails": rep["fails"], "warns": rep["warns"],
                            "gates": {g["id"]: g["status"] for g in rep["gates"]}})
            py(S / "contact_sheet.py", out, "--timeline", t, "-o", f"sheets/ad_{h}_{r}_sheet.png")
    save(summary, "renders/variants_summary.json")
    for s in summary: print(f"{s['hook']} {s['ratio']}: {s['fails']} FAIL, {s['warns']} WARN")
    sys.exit(1 if any(s["fails"] for s in summary) else 0)


if __name__ == "__main__":
    main()
