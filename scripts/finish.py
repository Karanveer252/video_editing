#!/usr/bin/env python3
"""Join picture + mix into the delivery file (AD_VIDEO_STANDARD): H.264 yuv420p, 30 fps CFR, BT.709 tv tags,
AAC 48 kHz, +faststart, monotonic timestamps, exact duration (no leftover frames after the end card).

usage: finish.py PICTURE.mp4 MIX.wav -o FINAL.mp4 --frames N
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _common import run, ENC_V, ENC_A, FPS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("picture"); ap.add_argument("mix"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--frames", type=int, required=True)
    a = ap.parse_args()
    dur = a.frames / FPS
    # Remotion wrote BT.709-tagged frames; scale keeps the matrix explicit so nothing is re-interpreted as BT.601
    run(["ffmpeg", "-y", "-v", "error", "-i", a.picture, "-i", a.mix,
         "-vf", "scale=in_color_matrix=bt709:out_color_matrix=bt709:in_range=tv:out_range=tv,format=yuv420p",
         "-map", "0:v:0", "-map", "1:a:0", "-frames:v", str(a.frames), "-t", f"{dur:.4f}"] + ENC_V + ENC_A +
        ["-movflags", "+faststart", "-avoid_negative_ts", "make_zero", a.out])
    print(f"final -> {a.out}")


if __name__ == "__main__":
    main()
