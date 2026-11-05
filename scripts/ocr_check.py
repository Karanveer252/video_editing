#!/usr/bin/env python3
"""Frame OCR check (AD_VIDEO_STANDARD QA 5): OCR every Nth frame and report any hit of a private name
(client brand, place, staff names, handles) that must not appear on screen. Run with the skill venv:
  .venv/bin/python scripts/ocr_check.py FINAL.mp4 --names "Le Cookie" "Winnipeg" [--step 2] [-o hits.json]
Exit 1 when any name is found. Uses RapidOCR (Apache-2.0, local ONNX models, nothing leaves the box)."""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--names", nargs="+", required=True)
    ap.add_argument("--step", type=int, default=2); ap.add_argument("-o", "--out")
    a = ap.parse_args()
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    pats = [(n, re.compile(r"\s*".join(map(re.escape, n.replace(" ", ""))), re.I)) for n in a.names]
    hits, n_frames = [], 0
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-vf", f"select='not(mod(n\\,{a.step}))'",
                        "-fps_mode", "passthrough", "-frame_pts", "1", f"{d}/f%05d.png"], check=True)
        for f in sorted(Path(d).glob("f*.png")):
            n_frames += 1; idx = int(f.stem[1:])
            res, _ = ocr(str(f))
            text = " | ".join(r[1] for r in (res or []))
            for name, p in pats:
                if p.search(text.replace(" ", "")):
                    hits.append({"frame": idx, "name": name, "text": text[:200]})
    summary = {"video": a.video, "frames_checked": n_frames, "step": a.step, "names": a.names,
               "hits": len(hits), "frames_with_hits": sorted({h["frame"] for h in hits}),
               "names_found": sorted({h["name"] for h in hits}), "examples": hits[:10]}
    if a.out:
        Path(a.out).write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ("frames_checked", "hits")} | {"names_found": summary["names_found"]}))
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
