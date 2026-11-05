#!/usr/bin/env python3
"""Original music bed + SFX synthesized in code (SOUND.md: "Synthesized in this repo" is an allowed source).
No samples, no reverb (AD_VIDEO_STANDARD), deterministic (seeded) so re-renders are identical.

usage: synth_audio.py OUT_DIR --bpm 90 --bars 5 [--seed 7]
writes OUT_DIR/music.wav, OUT_DIR/beats.json (beats + downbeats as generated),
       OUT_DIR/sfx_pop.wav, sfx_swish.wav, sfx_tick.wav
and appends rows to OUT_DIR/LICENCES.csv (SOUND.md manifest columns).
"""
import argparse, csv, datetime, json, wave
from pathlib import Path
import numpy as np

SR = 48000


def write(path, x):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    peak = np.abs(x).max() or 1
    x = x / peak * 0.89
    pcm = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def env(n, a, d):
    t = np.arange(n) / SR
    e = np.minimum(t / max(a, 1e-4), 1.0) * np.exp(-t / d)
    return e


def note(f):
    return 440.0 * 2 ** ((f - 69) / 12)


def music(bpm, bars, seed):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm; bar = 4 * beat
    total = bars * bar + 1.5  # tail ring-out after last bar (no hard stop, no glitch)
    n = int(total * SR); out = np.zeros((n, 2))
    t_all = np.arange(n) / SR
    prog = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]  # C G Am F
    for b in range(bars):
        root, chord = prog[b % 4] if b < bars - 1 else (48, [60, 64, 67, 72])
        s0 = int(b * bar * SR); L = int(bar * SR)
        seg = slice(s0, min(n, s0 + L + int(0.6 * SR)))
        tt = t_all[seg] - b * bar
        pad = sum(np.sin(2 * np.pi * note(m) * tt) + 0.3 * np.sin(2 * np.pi * 2 * note(m) * tt) for m in chord)
        pe = np.minimum(tt / 0.25, 1) * np.where(tt < bar, 1.0, np.exp(-(tt - bar) / 0.15))
        out[seg, 0] += 0.06 * pad * pe; out[seg, 1] += 0.06 * pad * pe
        for k in range(4):  # bass on every beat
            s = int((b * bar + k * beat) * SR); m = int(beat * SR)
            if s >= n: break
            tb = np.arange(min(m, n - s)) / SR
            out[s:s + len(tb)] += (0.22 * np.sin(2 * np.pi * note(root - 12) * tb) * env(len(tb), 0.005, 0.25))[:, None]
    nbeats = int(bars * 4)
    for i in range(nbeats + 1):
        s = int(i * beat * SR)
        if s >= n: break
        L = min(int(0.35 * SR), n - s); tb = np.arange(L) / SR
        f = 50 + 70 * np.exp(-tb * 30)
        kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.002, 0.12) * (1.0 if i % 4 == 0 else 0.6)
        out[s:s + L] += 0.55 * kick[:, None]
        if i % 2 == 1 and i < nbeats:  # soft clap on 2 and 4
            Lc = min(int(0.18 * SR), n - s)
            nz = rng.standard_normal(Lc)
            clap = np.convolve(nz, np.ones(8) / 8, "same") * env(Lc, 0.001, 0.05)
            out[s:s + Lc] += 0.18 * clap[:, None]
        for h in (0.5,):  # off-beat hat
            sh = int((i + h) * beat * SR)
            if sh < n and i < nbeats:
                Lh = min(int(0.05 * SR), n - sh)
                hat = np.diff(rng.standard_normal(Lh + 1)) * env(Lh, 0.0005, 0.012)
                out[sh:sh + Lh, 0] += 0.07 * hat; out[sh:sh + Lh, 1] += 0.05 * hat
    fade = int(1.2 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
    beats = [round(i * beat, 6) for i in range(nbeats + 1)]
    downbeats = [round(b * bar, 6) for b in range(bars + 1)]
    return out, {"bpm": bpm, "beats": beats, "downbeats": downbeats, "bars": bars, "music_duration": round(total, 3),
                 "how": "generated (exact); verify with beats.py --detect"}


def pop():
    L = int(0.12 * SR); t = np.arange(L) / SR
    f = 900 * np.exp(-t * 18) + 300
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.002, 0.03)


def swish(seed):
    rng = np.random.default_rng(seed + 1)
    L = int(0.45 * SR); t = np.arange(L) / SR
    nz = rng.standard_normal(L)
    out = np.zeros(L); k = 1
    for i in range(0, L, 480):  # crude time-varying lowpass sweep
        w = int(2 + 30 * (1 - i / L)); seg = nz[max(0, i - w):i + 480]
        out[i:i + 480] = np.convolve(seg, np.ones(w) / w, "same")[-len(out[i:i + 480]):]
    e = np.sin(np.pi * np.clip(t / 0.45, 0, 1)) ** 2
    return out * e


def tick():
    L = int(0.04 * SR); t = np.arange(L) / SR
    return np.sin(2 * np.pi * 2400 * t) * env(L, 0.0005, 0.006)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--bpm", type=float, default=90); ap.add_argument("--bars", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    o = Path(a.out); o.mkdir(parents=True, exist_ok=True)
    m, beats = music(a.bpm, a.bars, a.seed)
    write(o / "music.wav", m); (o / "beats.json").write_text(json.dumps(beats, indent=1))
    write(o / "sfx_pop.wav", pop()); write(o / "sfx_swish.wav", swish(a.seed)); write(o / "sfx_tick.wav", tick())
    lic = o / "LICENCES.csv"; new = not lic.exists()
    with open(lic, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["file", "source_url", "licence", "author", "attribution_required", "paid_ads_allowed", "downloaded_on", "notes"])
        today = datetime.date.today().isoformat()
        for fn in ("music.wav", "sfx_pop.wav", "sfx_swish.wav", "sfx_tick.wav"):
            w.writerow([fn, "scripts/synth_audio.py", "original (synthesized in code)", "Domin8te Media", "no", "yes", today,
                        f"seed {a.seed}, {a.bpm:g} BPM, no samples, no reverb"])
    print(f"music {beats['music_duration']}s @ {a.bpm:g} BPM, downbeats {beats['downbeats']}")


if __name__ == "__main__":
    main()
