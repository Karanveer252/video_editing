#!/usr/bin/env python3
"""Contact sheets so Claude SEES footage before deciding anything (claudeclip sample_frames idea).

Modes:
  contact_sheet.py IN.mp4 -o sheet.png [--count 12 --cols 4 --tile 320]   evenly spaced frames
  contact_sheet.py IN.mp4 -o sheet.png --at 0.5,2.67,5.3                   frames at given seconds
  contact_sheet.py IN.mp4 -o sheet.png --timeline timeline.json            frames at every cut/cue (+/- 1 frame around cuts)
Each tile is stamped with its timestamp (s) and frame number.
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).parent))
from _common import probe, vstream, load, FPS, die

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def grab(path, t, width):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t,0):.3f}", "-i", str(path), "-frames:v", "1",
                        "-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if r.returncode or not r.stdout:
        return None
    from io import BytesIO
    return Image.open(BytesIO(r.stdout)).convert("RGB")


def times_from_timeline(tl):
    ts = set()
    for seg in tl.get("segments", []):
        s = seg["start"]
        for d in (-1 / FPS, 0, 1 / FPS):
            ts.add(round(s + d, 3))
    for c in tl.get("overlays", []):
        ts.add(round(c["start"] + 0.4, 3))
    for c in tl.get("captions", {}).get("lines", []):
        ts.add(round(c["words"][-1]["light"] + 0.25, 3))
    if "duration" in tl:
        ts.add(round(tl["duration"] - 1 / FPS, 3))
    return sorted(t for t in ts if 0 <= t < tl.get("duration", 1e9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--count", type=int, default=12); ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--tile", type=int, default=320); ap.add_argument("--at")
    ap.add_argument("--timeline"); ap.add_argument("--start", type=float, default=0); ap.add_argument("--end", type=float)
    a = ap.parse_args()
    info = probe(a.input)
    dur = float(info["format"]["duration"])
    end = a.end or dur
    if a.at:
        ts = [float(x) for x in a.at.split(",")]
    elif a.timeline:
        ts = times_from_timeline(load(a.timeline))
    else:
        n = a.count
        ts = [a.start + (end - a.start) * (i + 0.5) / n for i in range(n)]
    ts = [t for t in ts if t < dur]
    if not ts:
        die("no timestamps inside the clip")
    tiles = []
    font = ImageFont.truetype(FONT, max(12, a.tile // 16))
    for t in ts:
        im = grab(a.input, t, a.tile)
        if im is None:
            continue
        d = ImageDraw.Draw(im)
        label = f"{t:6.2f}s  f{round(t*FPS)}"
        d.rectangle([0, 0, d.textlength(label, font=font) + 10, font.size + 8], fill=(0, 0, 0))
        d.text((5, 3), label, fill=(255, 255, 255), font=font)
        tiles.append(im)
    cols = min(a.cols, len(tiles)); rows = (len(tiles) + cols - 1) // cols
    w, h = tiles[0].size
    sheet = Image.new("RGB", (cols * w + (cols + 1) * 6, rows * h + (rows + 1) * 6), (40, 40, 40))
    for i, im in enumerate(tiles):
        sheet.paste(im, (6 + (i % cols) * (w + 6), 6 + (i // cols) * (h + 6)))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out)
    print(f"{a.out}  ({len(tiles)} frames: {', '.join(f'{t:.2f}' for t in ts)})")


if __name__ == "__main__":
    main()
