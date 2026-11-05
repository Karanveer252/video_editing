#!/usr/bin/env python3
"""Automatic QA gates. Exit code 0 only when no gate FAILs (Kinocut rule: a render is not done until it passes).
Writes <video>_qa_report.json and <video>_receipt.json (Kinocut Video Receipt fields).

usage: qa.py FINAL.mp4 --timeline timeline.json --ratio 9x16 [--lut references/domin8te_half_grade_v1.cube]

 Q1 spec       codec, pix_fmt, size, 30 fps CFR, BT.709 tv tags, AAC 48 kHz, frame count, faststart, unique PTS
 Q2 loudness   integrated -14 +/-1 LUFS, true peak <= -1.0 dBTP (ebur128 measured on the file)
 Q3 safe zones every text box inside the ratio's text zone, out of the 9:16 right rail; 9:16 top inset is page only
 Q4 captions   word lights 0-80 ms early, swipe 180-220 ms starting 100-140 ms early, every line >= 1 s
 Q5 cut-on-beat every planned cut within 1 frame of a downbeat AND a measured picture change at that frame
 Q6 grain      the same grain patch is pixel-stable across the film and its noise std is in range
 Q7 colour     cream page within dE 3 of #FAF6F0; graded footage matches an independent LUT application
 Q7b           WARN if the LUT collapses saturated colours to grey (known half grade v1 defect)
 Q8 copy       banned words / digits / em dashes in every on-screen string
 Q9 end card   gradual crossfade, no footage after it, audio fades to silence with no click
 Q10 hook      the hook caption is on screen and in ink on frame 1
 Q11 privacy   frame OCR (AD_VIDEO_STANDARD QA 5): no client brand, place, staff or handle from brief.private_names
 Q12 opener    the presenter opener MOVES (AD_VIDEO_STANDARD QA 6): no repeated frames, few frozen frames, real motion
 Q13 speech    faster-whisper on the final file (AD_VIDEO_STANDARD QA 4): no private name spoken
"""
import argparse, re, subprocess, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from _common import load, save, probe, vstream, astream, hex_rgb, copy_violations, FPS, RATIOS, BRAND, SKILL, sha256
from layout import LAYOUT

R = []
TOPIX = "scale=in_color_matrix=bt709:in_range=tv:out_range=pc:out_color_matrix=bt709"
# Q13 decode: mono 16 kHz float32 on stdout, "{}" is the input path
DECODE_16K = ["ffmpeg", "-v", "error", "-i", "{}", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]


def gate(gid, name, ok, measured, need, level="FAIL"):
    status = "PASS" if ok else level
    R.append({"id": gid, "gate": name, "status": status, "measured": measured, "required": need})
    print(f"{gid:<4} {status:<4} {name}: {measured}  (need {need})")


def frames_at(path, idxs, w, h):
    """Exact frames by index, full-range RGB via an explicit BT.709 matrix."""
    sel = "+".join(f"eq(n\\,{i})" for i in idxs)
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"select='{sel}',{TOPIX}",
                        "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).astype(float).reshape(-1, h, w, 3)


def lab(rgb):
    c = np.asarray(rgb, float) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def read_cube(p):
    n, rows = None, []
    for ln in open(p):
        ln = ln.strip()
        if ln.startswith("LUT_3D_SIZE"):
            n = int(ln.split()[1])
        elif ln and (ln[0].isdigit() or ln[0] in "-."):
            rows.append([float(v) for v in ln.split()])
    return n, np.array(rows).reshape(n, n, n, 3)  # indexed [b][g][r]; red varies fastest in .cube


def apply_cube(rgb, n, lut):
    """Tetrahedral interpolation, written independently of ffmpeg's lut3d."""
    x = np.asarray(rgb, float) / 255.0 * (n - 1)
    i0 = np.clip(np.floor(x).astype(int), 0, n - 2); f = x - i0
    r, g, b = i0[..., 0], i0[..., 1], i0[..., 2]; fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    L = lambda dr, dg, db: lut[b + db, g + dg, r + dr]
    c0, c1 = L(0, 0, 0), L(1, 1, 1)
    conds = [(fr >= fg) & (fg >= fb), (fr >= fb) & (fb >= fg), (fb >= fr) & (fr >= fg),
             (fg >= fr) & (fr >= fb), (fg >= fb) & (fb >= fr), (fb >= fg) & (fg >= fr)]
    vals = [c0 + fr * (L(1, 0, 0) - c0) + fg * (L(1, 1, 0) - L(1, 0, 0)) + fb * (c1 - L(1, 1, 0)),
            c0 + fr * (L(1, 0, 0) - c0) + fb * (L(1, 0, 1) - L(1, 0, 0)) + fg * (c1 - L(1, 0, 1)),
            c0 + fb * (L(0, 0, 1) - c0) + fr * (L(1, 0, 1) - L(0, 0, 1)) + fg * (c1 - L(1, 0, 1)),
            c0 + fg * (L(0, 1, 0) - c0) + fr * (L(1, 1, 0) - L(0, 1, 0)) + fb * (c1 - L(1, 1, 0)),
            c0 + fg * (L(0, 1, 0) - c0) + fb * (L(0, 1, 1) - L(0, 1, 0)) + fr * (c1 - L(0, 1, 1)),
            c0 + fb * (L(0, 0, 1) - c0) + fg * (L(0, 1, 1) - L(0, 0, 1)) + fr * (c1 - L(0, 1, 1))]
    out = np.zeros(x.shape); done = np.zeros(x.shape[:-1] + (1,), bool)
    for c, v in zip(conds, vals):
        m = c & ~done; out = np.where(m, v, out); done |= m
    return np.clip(out * 255, 0, 255)


def inside(b, z):
    x, y, w, h = b
    return x >= z[0] and y >= z[1] and x + w <= z[2] and y + h <= z[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--timeline", required=True); ap.add_argument("--ratio", required=True)
    ap.add_argument("--ocr-step", type=int, default=2, help="OCR every Nth frame (standard: 2)")
    ap.add_argument("--lut", default=str(SKILL / "references" / "domin8te_half_grade_v1.cube"))
    a = ap.parse_args()
    v = Path(a.video); tl = load(a.timeline); base = Path(a.timeline).resolve().parent
    W, H = RATIOS[a.ratio]; LY = LAYOUT[a.ratio]; N = tl["frames"]
    cream = np.array(hex_rgb(BRAND["cream"]), float); ink = np.array(hex_rgb(BRAND["ink"]), float)
    PATCH = {"9x16": (0, 0, 100, 200), "4x5": (0, 0, 60, 64)}[a.ratio]  # page-only corner (outside captions + panel)
    pxs = lambda fr: fr[..., PATCH[1]:PATCH[1] + PATCH[3], PATCH[0]:PATCH[0] + PATCH[2], :]
    P = LY["panel"]; px, py, pw, ph = P["x"], P["y"], P["w"], P["h"]
    py1 = min(py + ph, H) - 40  # panel may run off the bottom edge by design

    # Q1
    info = probe(v); vs, au = vstream(info), astream(info)
    pts = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts", "-of", "csv=p=0", str(v)],
                         capture_output=True, text=True).stdout.split()
    pts = [int(p) for p in pts if p.strip().lstrip("-").isdigit()]
    head = open(v, "rb").read(1 << 16); mo, md = head.find(b"moov"), head.find(b"mdat")
    ck = {"codec": vs["codec_name"] == "h264", "pix_fmt": vs["pix_fmt"] == "yuv420p", "size": (vs["width"], vs["height"]) == (W, H),
          "fps_cfr": vs["r_frame_rate"] == "30/1" and vs["avg_frame_rate"] == "30/1",
          "bt709_tv": all(vs.get(k) == "bt709" for k in ("color_space", "color_transfer", "color_primaries")) and vs.get("color_range") == "tv",
          "aac_48k": au is not None and au["codec_name"] == "aac" and au["sample_rate"] == "48000",
          "frame_count": int(vs.get("nb_frames", 0)) == N, "faststart": mo != -1 and (md == -1 or mo < md),
          "pts_unique": len(pts) == len(set(pts)) == N}
    gate("Q1", "delivery spec", all(ck.values()), [k for k, ok in ck.items() if not ok] or f"all ok ({N} frames)",
         "h264 yuv420p, 30/1 CFR, bt709 tv, aac 48k, exact frame count, faststart, unique PTS")

    # Q2
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(v), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)[-1])
    gate("Q2", "loudness", abs(I + 14) <= 1.0 and TP <= -1.0, f"I {I} LUFS, true peak {TP} dBTP", "-14 +/-1 LUFS, TP <= -1.0")

    # Q3
    zone, rail, bad = LY["text_zone"], LY.get("rail"), []
    B = tl["boxes"][a.ratio]
    boxes = [("caption", b) for line in B["captions"] for b in line]
    for o in B["overlays"]:
        keys = ("logo", "head", "url") if o["type"] == "end_card" else ("box",)  # end_card.box is a layout container, not ink
        boxes += [(f"{o['type']}.{k}", o[k]) for k in keys if k in o]
    for nm, b in boxes:
        if not inside(b, zone): bad.append(f"{nm} {b} outside text zone")
        if rail and b[0] + b[2] > rail[0] and b[1] + b[3] > rail[1]: bad.append(f"{nm} {b} enters rail")
    msg = f"{len(boxes)} boxes inside {zone}"
    if a.ratio == "9x16":
        fr = frames_at(v, list(range(0, N, max(1, N // 12))), W, H)[:, :LY["top_inset"]]
        dark = float((np.abs(fr - cream).max(-1) > 40).mean())
        msg += f"; top inset pixels off-page {dark:.5f}"
        if dark > 0.001: bad.append(f"top inset has content ({dark:.4f})")
    gate("Q3", "safe zones", not bad, bad or msg, "all text in zone, none in rail; 9:16 top inset page only")

    # Q4
    iss, nw = [], 0
    for i, ln in enumerate(tl["captions"]["lines"]):
        for w in ln["words"]:
            nw += 1; early = round((w["spoken"] - w["light"]) * 1000)
            if not 0 <= early <= 80: iss.append(f"line{i} '{w['w']}' lights {early} ms early")
            if w.get("swipe"):
                s0, d = w["swipe"]; dms, lead = round(d * 1000), round((w["light"] - s0) * 1000)
                if not 180 <= dms <= 220: iss.append(f"swipe '{w['w']}' {dms} ms")
                if not 100 <= lead <= 140: iss.append(f"swipe '{w['w']}' starts {lead} ms early")
        if ln["frame_end"] - ln["frame_start"] < 30: iss.append(f"line{i} on screen < 1 s")
    gate("Q4", "caption timing", not iss, iss or f"{nw} words, {len(tl['captions']['lines'])} lines ok",
         "light 0-80 ms early; swipe 180-220 ms, starts 100-140 ms early; line >= 1 s")

    # Q5: plan check on the timeline; picture check on the footage layer (overlays pop on cuts, so measure under them)
    db = tl["music"]["downbeats"]; iss, meas = [], []
    gf = base / tl["footage"]["file"]; gs = vstream(probe(gf)); gw, gh = gs["width"], gs["height"]
    for s in tl["segments"][1:]:
        off = min(abs(s["start"] - d) for d in db) * FPS
        if off > 1.0: iss.append(f"{s['id']} {off:.2f} frames off a downbeat")
        f0 = s["frame_start"]
        fr = frames_at(gf, [f0 - 2, f0 - 1, f0, f0 + 1], gw, gh)
        d = [float(np.abs(fr[k + 1] - fr[k]).mean()) for k in range(3)]
        meas.append(f"f{f0}: off {off:.2f} fr, change {d[1]:.1f} vs {d[0]:.1f}/{d[2]:.1f}")
        if not (d[1] > 2 * max(d[0], 0.5) and d[1] > 2 * max(d[2], 0.5)): iss.append(f"no clean change at f{f0} {d}")
    gate("Q5", "cut on beat", not iss, iss or meas, "<= 1 frame from a downbeat; footage change spike exactly at the cut (> 2x neighbours)")

    # Q6
    fr = pxs(frames_at(v, list(range(0, N, max(1, N // 10))), W, H)).mean(-1)
    stab = float(np.abs(fr - fr[0]).mean(axis=(1, 2)).max()); std = float(fr.std(axis=(1, 2)).mean())
    gate("Q6", "grain consistency", stab < 0.6 and 0.8 <= std <= 4.0, f"patch drift {stab:.3f}, grain std {std:.2f} levels",
         "drift < 0.6; std 0.8-4.0 levels")

    # Q7
    pg = pxs(frames_at(v, [30], W, H))[0].reshape(-1, 3)
    dE = float(np.linalg.norm(lab(np.median(pg, 0)) - lab(cream)))
    n, lut = read_cube(a.lut)
    uf = base / "graded" / "footage_ungraded.mp4"
    diffs = [float(np.abs(apply_cube(frames_at(uf, [k], gw, gh)[0], n, lut) - frames_at(gf, [k], gw, gh)[0]).mean()) for k in sorted({15, int(tl["footage"]["end"] * FPS) // 2, int(tl["footage"]["end"] * FPS) - 15})]
    gate("Q7", "colour", dE < 3 and max(diffs) < 4, f"cream dE {dE:.2f}; graded vs independent LUT mean diff {max(diffs):.2f} levels",
         "cream dE < 3; LUT match < 4 levels")
    g = np.linspace(0, 255, 18); chart = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    sat = (chart.max(1) - chart.min(1)) / 255; out = apply_cube(chart, n, lut); osat = (out.max(1) - out.min(1)) / 255
    m = sat > 0.35; ncol = int((osat[m] < 0.05).sum())
    loss = float(np.max(sat[m] - osat[m]))
    gate("Q7b", "LUT keeps saturated colours", ncol == 0, f"{ncol} of {int(m.sum())} saturated chart colours come out grey; worst saturation loss {loss:.2f}",
         "0 collapse to grey", level="WARN")

    # Q8
    texts = [ln["text"] for ln in tl["captions"]["lines"]] + [o.get(k, "") for o in tl["overlays"] for k in ("text", "sub", "headline")]
    viol = [(t, copy_violations(t)) for t in texts if t and copy_violations(t)]
    gate("Q8", "copy rules", not viol, viol or f"{len([t for t in texts if t])} strings clean", "no banned phrases, digits, em dashes")

    # Q9
    end = next(o for o in tl["overlays"] if o["type"] == "end_card"); f0, xf = end["frame_start"], end.get("xfade_frames", 12)
    fr = frames_at(v, list(range(f0 - 1, f0 + xf + 1)), W, H)
    steps = [float(np.abs(fr[k + 1] - fr[k]).mean()) for k in range(len(fr) - 1)]
    eb = next(o for o in B["overlays"] if o["type"] == "end_card")
    ey = max(eb[k][1] + eb[k][3] for k in ("logo", "head", "url")) + 30
    pan = frames_at(v, [f0 + xf + 2, N - 1], W, H)[:, max(py, ey):py1, px + 40:px + pw - 40]
    resid = float((np.abs(pan - cream).max(-1) > 40).mean())
    au = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(v), "-f", "f32le", "-ac", "1", "-ar", "48000", "-"],
                                      capture_output=True).stdout, np.float32)
    tail_db = float(20 * np.log10(np.sqrt(np.mean(au[-4800:] ** 2)) + 1e-12)); click = float(np.abs(au[-2400:]).max())
    mean_s = sum(steps) / len(steps)
    ok = max(steps) < 2.5 * mean_s + 0.5 and resid < 0.01 and tail_db < -45 and click < 0.01
    gate("Q9", "end card", ok, f"xfade step max {max(steps):.2f} / mean {mean_s:.2f}; footage left in panel area {resid:.4f}; "
         f"last 100 ms {tail_db:.1f} dBFS; peak in last 50 ms {click:.4f}",
         "gradual (max step < 2.5x mean), nothing left of the footage, tail < -45 dBFS, last 50 ms peak < 0.01 (no click)")

    # Q10
    x, y, w_, h_ = B["captions"][0][0]
    f1 = frames_at(v, [0], W, H)[0][y:y + h_, x:x + w_]
    cov = float((np.linalg.norm(f1 - ink, axis=-1) < 60).mean())
    gate("Q10", "hook on frame 1", cov > 0.03 and tl["captions"]["lines"][0]["frame_start"] == 0, f"first hook word ink coverage {cov:.2f}",
         "hook caption starts at frame 0, first word in full ink")

    # Q11
    names = tl.get("private_names", []); vpy = SKILL / ".venv" / "bin" / "python"
    if not names:
        gate("Q11", "privacy OCR", False, "not run: brief.private_names is empty", "list the client's brand/place/staff names", level="WARN")
    elif not vpy.exists():
        gate("Q11", "privacy OCR", False, "not run: no .venv with rapidocr_onnxruntime", "see README setup", level="FAIL")
    else:
        oj = v.with_name(v.stem + "_ocr.json")
        subprocess.run([str(vpy), str(SKILL / "scripts" / "ocr_check.py"), str(v), "--names", *names, "--step", str(a.ocr_step),
                        "-o", str(oj)], capture_output=True)
        o = load(oj)
        gate("Q11", "privacy OCR", o["hits"] == 0, f"{o['hits']} hits in {o['frames_checked']} frames (every {a.ocr_step}); "
             f"names found {o.get('names_found', sorted({h['name'] for h in o['examples']}))}; frames {o['frames_with_hits'][:6]}...",
             "0 hits of any private name")

    # Q12: measured on the footage layer (real motion, not the push-in, which Remotion adds on top)
    s0 = tl["segments"][0]
    if s0.get("kind") == "presenter":
        idx = list(range(s0["frame_start"], s0["frame_end"]))
        g = frames_at(gf, idx, gw, gh).mean(-1)
        d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))
        dup = int((d < 0.05).sum()); frozen = int((d < 0.3).sum()); q = np.array_split(d, 4)
        ok = dup == 0 and frozen <= max(1, len(d) // 20) and float(d.mean()) >= 0.5
        gate("Q12", "opener moves", ok, f"{len(idx)} frames; mean change {d.mean():.2f} levels/frame; per quarter "
             f"{[round(float(x.mean()), 2) for x in q]}; repeated {dup}; frozen (<0.3) {frozen}; push-in {s0.get('push_in', 0):.0%}",
             "0 repeated frames, frozen <= 5%, mean change >= 0.5 (a still with a zoom fails)")
    else:
        gate("Q12", "opener moves", False, f"no presenter opener; waiver: {tl.get('opener', {}).get('waiver', 'none')}",
             "moving presenter in segment 0, or Karan's written waiver", level="WARN" if tl.get("opener", {}).get("waiver") else "FAIL")

    # Q13
    if not names:
        pass
    elif not vpy.exists():
        gate("Q13", "speech privacy", False, "not run: no .venv with faster-whisper", "see README setup", level="WARN")
    else:
        # samples are passed as an array (the venv's PyAV clashes with faster-whisper's own decoder)
        code = ("import sys,json,subprocess,numpy as np;from faster_whisper import WhisperModel;"
                f"a=np.frombuffer(subprocess.run([x.replace('{{}}',sys.argv[1]) for x in {DECODE_16K!r}],"
                "capture_output=True).stdout,np.float32);m=WhisperModel('small.en',device='cpu',compute_type='int8');"
                "seg,_=m.transcribe(a,vad_filter=True);print(json.dumps(' '.join(s.text for s in seg)))")
        r = subprocess.run([str(vpy), "-c", code, str(v)], capture_output=True, text=True)
        if r.returncode:
            gate("Q13", "speech privacy", False, f"not run: {r.stderr.strip()[-160:]}", "transcript of the final file", level="WARN")
        else:
            txt = __import__("json").loads(r.stdout.strip().splitlines()[-1]); low = txt.replace(" ", "").lower()
            heard = [n_ for n_ in names if n_.replace(" ", "").lower() in low]
            gate("Q13", "speech privacy", not heard, f"heard {heard or 'no private names'}; transcript {txt.strip()[:80]!r}",
                 "0 private names in speech")

    fails = sum(g["status"] == "FAIL" for g in R); warns = sum(g["status"] == "WARN" for g in R)
    rep = {"video": str(v), "ratio": a.ratio, "hook": tl["hook_id"], "fails": fails, "warns": warns, "gates": R,
           "human_checks": ["DSNRY test: watch graded/footage_graded.mp4 with no graphics. Does the footage still tell the story?",
                            f"STEP 0 answered by: {tl['step0'].get('answered_by', 'Karan')}",
                            "Watch the full ad once, sound on, on a phone, before it ships"]}
    save(rep, v.with_name(v.stem + "_qa_report.json"))
    save({"timeline": str(Path(a.timeline).resolve()), "timeline_sha256": sha256(a.timeline), "render": str(v.resolve()),
          "render_sha256": sha256(v), "ratio": a.ratio, "hook": tl["hook_id"], "duration_s": tl["duration"], "frames": N,
          "music": tl["music"]["file"], "licences": "audio/LICENCES.csv", "grade": f"{Path(a.lut).name}, footage layer only",
          "qa": {g["id"]: g["status"] for g in R}, "approved_for_upload": False}, v.with_name(v.stem + "_receipt.json"))
    print(f"\n{len(R)} gates: {fails} FAIL, {warns} WARN")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
