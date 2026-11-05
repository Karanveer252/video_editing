#!/usr/bin/env python3
"""Sound from the SAME timeline.json as the picture: music bed + SFX at their cue times (+ optional
dialogue/ambience from the footage with 30 ms fades). One continuous soundtrack across the end-card
crossfade (AD_VIDEO_STANDARD). Music fades to true silence 0.25 s before the last frame. No reverb anywhere. Then two-pass loudnorm to -14 LUFS, -1 dBTP, LRA 7.

usage: mix_audio.py timeline.json -o mix.wav [--licences audio/LICENCES.csv]
Refuses to mix any file that has no row in LICENCES.csv (SOUND.md: licence check before every render).
"""
import argparse, csv, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _common import load, run, die


# SOUND.md section 6 allowed list. Mixkit stays out until its licence page is read.
ALLOWED = {"CC0", "Kenney-CC0", "Sonniss-GDC", "Pixabay", "Meta-Sound-Collection", "ElevenLabs-paid", "original"}


def licence_check(files, lic):
    if not lic.exists():
        die(f"no {lic}: every sound needs a licence row (SOUND.md)")
    rows = {r["file"]: r for r in csv.DictReader(open(lic))}
    for f in files:
        r = rows.get(Path(f).name)
        if not r:
            die(f"licence check: {Path(f).name} has no row in {lic}")
        lic_ = r["licence"].strip()
        if not (lic_ in ALLOWED or lic_.lower().startswith("original")):
            die(f"licence check: {Path(f).name} licence {lic_!r} is not on the SOUND.md allowed list")
        # meta-only (Meta Sound Collection) is fine: these ads run on Facebook and Instagram ONLY
        if r["paid_ads_allowed"].strip().lower() not in ("yes", "meta-only"):
            die(f"licence check: {Path(f).name} is not cleared for paid ads")
        if r.get("attribution_required", "no").strip().lower() != "no":
            die(f"licence check: {Path(f).name} needs a credit; SOUND.md uses no-credit sources only")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--licences", default="audio/LICENCES.csv")
    a = ap.parse_args()
    tl = load(a.timeline); base = Path(a.timeline).parent
    music = base / tl["music"]["file"]; dur = tl["duration"]
    files = [music] + [base / s["file"] for s in tl["sfx"]]
    licence_check(files, base / a.licences)
    inputs = ["-i", str(music)]
    chains = [f"[0:a]atrim=0:{dur},asetpts=N/SR/TB,afade=t=out:st={dur - 1.25:.3f}:d=1.0,volume=-6dB[m]"]
    labels = ["[m]"]
    for i, s in enumerate(tl["sfx"], start=1):
        inputs += ["-i", str(base / s["file"])]
        ms = max(0, int(round(s["at"] * 1000)))
        chains.append(f"[{i}:a]adelay={ms}|{ms},volume={s['gain_db']}dB[s{i}]"); labels.append(f"[s{i}]")
    chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first,atrim=0:{dur}[mix]")
    pre = Path(a.out).with_suffix(".pre.wav")
    run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(chains), "-map", "[mix]",
         "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(pre)])
    # two-pass loudnorm (measure, then apply linear). If linear gain would break -1 dBTP, first bring the mix up
    # to target with a transparent peak limiter (no reverb, no colouring), re-measure, then apply linear loudnorm.
    def measure(f):
        r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(f), "-af", "loudnorm=I=-14:TP=-1:LRA=7:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True)
        return json.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    m = measure(pre); first = dict(m)
    gain = -14 - float(m["input_i"])
    if float(m["input_tp"]) + gain > -1.2:
        lim = pre.with_suffix(".lim.wav")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-af",
             f"volume={gain + 0.6:.2f}dB,alimiter=limit={10 ** (-1.6 / 20):.4f}:attack=3:release=60:level=disabled",
             "-ar", "48000", "-c:a", "pcm_s16le", str(lim)])
        lim.replace(pre); m = measure(pre)
    af = (f"loudnorm=I=-14:TP=-1:LRA=7:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
          f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=json")
    r2 = subprocess.run(["ffmpeg", "-y", "-v", "info", "-i", str(pre), "-af", af, "-ar", "48000", "-c:a", "pcm_s16le", a.out],
                        capture_output=True, text=True)
    if r2.returncode:
        die(r2.stderr[-1500:])
    m2 = json.loads(r2.stderr[r2.stderr.rfind("{"):r2.stderr.rfind("}") + 1])
    if m2.get("normalization_type") != "linear":
        die(f"loudnorm fell back to {m2.get('normalization_type')} mode; fix the mix instead of letting it pump")
    print(f"mix -> {a.out}: raw I={first['input_i']} TP={first['input_tp']}; out I={m2['output_i']} TP={m2['output_tp']} (linear)")
    pre.unlink()


if __name__ == "__main__":
    main()
