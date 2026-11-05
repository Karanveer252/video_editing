#!/usr/bin/env python3
"""beats.json downbeat map.

  beats.py MUSIC.wav --detect -o beats.json [--bpm 90]   detect beats/downbeats from audio (onset energy +
                                                          autocorrelation tempo + strongest-phase downbeat)
  beats.py MUSIC.wav --verify beats.json                   compare a generated/hand map with detection (max error in frames)
Schema (same as avatar-motion-explainer v2.2): {"bpm", "beats":[s...], "downbeats":[s...]}
Licensed tracks (e.g. Meta Sound Collection) MUST go through --detect and a human check of the contact sheet at downbeats.
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from _common import FPS

SR = 22050; HOP = 220  # 10 ms


def load_mono(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<i2").astype(np.float64) / 32768


def onset_env(x):
    x = np.pad(x, (512, 512))  # centre the 1024 window on each hop
    frames = (len(x) - 1024) // HOP
    # low band (kick) energy flux
    from numpy.fft import rfft
    win = np.hanning(1024)
    E = []
    for i in range(frames):
        seg = x[i * HOP:i * HOP + 1024]
        if len(seg) < 1024: seg = np.pad(seg, (0, 1024 - len(seg)))
        sp = np.abs(rfft(seg * win))
        E.append(sp[:24].sum())  # < ~500 Hz
    E = np.log1p(np.array(E) * 10)
    flux = np.maximum(np.diff(E, prepend=0.0), 0)
    return flux


def detect(path, bpm_hint=None):
    x = load_mono(path); fl = onset_env(x); fr = SR / HOP
    if bpm_hint:
        bpm = bpm_hint
    else:
        ac = np.correlate(fl, fl, "full")[len(fl) - 1:]
        lo, hi = int(fr * 60 / 160), int(fr * 60 / 70)
        lag = lo + int(np.argmax(ac[lo:hi])); bpm = 60 * fr / lag
    period = fr * 60 / bpm
    # phase: best offset for beat grid
    best = max(range(int(period)), key=lambda o: fl[np.arange(o, len(fl), period).astype(int)].sum())
    beats = np.arange(best, len(fl), period) / fr
    # refine each beat to local onset peak (+/- 30 ms)
    ref = []
    for b in beats:
        i = int(b * fr); w = fl[max(0, i - 3):i + 4]
        ref.append((max(0, i - 3) + int(np.argmax(w))) / fr if len(w) else b)
    ref = np.array(ref)
    # refit tempo + phase by least squares on the refined beats (removes drift)
    k = np.arange(len(ref)); A = np.vstack([k, np.ones_like(k)]).T
    per_s, off = np.linalg.lstsq(A, ref, rcond=None)[0]
    bpm = 60 / per_s
    ref = np.where(np.abs(ref - (k * per_s + off)) < 0.02, ref, k * per_s + off)
    if ref[0] - per_s > -0.02:
        ref = np.concatenate([[max(0.0, ref[0] - per_s)], ref])
    strength = np.array([fl[int(b * fr)] if int(b * fr) < len(fl) else 0 for b in ref])
    phase = max(range(4), key=lambda p: strength[p::4].mean() if len(strength[p::4]) else 0)
    downs = ref[phase::4]
    return {"bpm": round(float(bpm), 2), "beats": [round(float(b), 3) for b in ref],
            "downbeats": [round(float(d), 3) for d in downs], "how": f"detected from {Path(path).name}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("music"); ap.add_argument("-o", "--out"); ap.add_argument("--detect", action="store_true")
    ap.add_argument("--verify"); ap.add_argument("--bpm", type=float)
    a = ap.parse_args()
    d = detect(a.music, a.bpm)
    if a.verify:
        g = json.load(open(a.verify))
        errs = [min(abs(x - y) for y in d["downbeats"]) * FPS for x in g["downbeats"] if x < d["beats"][-1]]
        ok = max(errs) <= 1.0
        print(json.dumps({"detected_bpm": d["bpm"], "generated_bpm": g["bpm"], "max_downbeat_err_frames": round(max(errs), 2),
                          "pass": ok}))
        sys.exit(0 if ok else 1)
    Path(a.out).write_text(json.dumps(d, indent=1)); print(f"bpm {d['bpm']} downbeats {d['downbeats'][:6]}...")


if __name__ == "__main__":
    main()
