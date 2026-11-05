#!/usr/bin/env python3
"""Build timeline.json: the ONE cue file that drives picture (Remotion) and sound (mix_audio.py).
(Pixel & Oak: one timeline drives both; retime a cue once and both follow.)

Inputs: brief.json (STEP 0 answers + selects + copy, written by Claude after seeing the contact sheets),
        beats.json (downbeat map). Output: timeline.json with seconds AND frames, plus per-ratio pixel boxes.

Rules enforced here (fail fast, before any render):
  - STEP 0: all five answers present
  - every footage cut and every reveal lands on a downbeat (snapped; error reported in frames)
  - copy rules (banned words, digits, dashes) on every on-screen string
  - captions fit max_lines in the caption box for every ratio
  - opener: segment 0 is a MOVING presenter clip (kind "presenter"), unless brief.opener.waiver carries
    Karan's reason (AD_VIDEO_STANDARD 2). A still photo is never a presenter.
  - end card headline is exactly "Book your free month"
  - no private name (client brand, place, staff, handle) in any on-screen string
usage: build_timeline.py brief.json --hook A -o timeline.json
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _common import load, save, die, FPS, copy_violations, BRAND
from layout import LAYOUT, wrap, text_w

STEP0 = ["feel", "subject", "prop", "before_after", "specific_effect"]
WORD_STEP = 0.18       # s between word reveals for written (non-speech) lines
LIGHT_EARLY = 0.04     # word lights 0-80 ms before it is spoken (v2.2 caption rule); we use 40 ms
SWIPE_LEAD, SWIPE_DUR = 0.12, 0.20


def f(t):
    return round(t * FPS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brief"); ap.add_argument("--hook", required=True); ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    b = load(a.brief); base = Path(a.brief).parent
    s0 = b.get("step0", {})
    missing = [k for k in STEP0 if not str(s0.get(k, "")).strip()]
    if missing:
        die(f"STEP 0 gate: answer the five questions first (missing: {', '.join(missing)})")
    op = b.get("opener", {})
    segs_in = b["segments"]
    if segs_in[0].get("kind") != "presenter" and not str(op.get("waiver", "")).strip():
        die("opener gate: segment 0 must be a moving presenter clip (kind: presenter), or set opener.waiver "
            "with Karan's reason (AD_VIDEO_STANDARD 2)")
    for s_ in segs_in:
        if s_.get("kind") == "presenter" and Path(s_["clip"]).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            die("opener gate: a presenter must be moving footage, never a still")
    if b["end_card"].get("headline") != "Book your free month":
        die(f"end card gate: headline must be 'Book your free month' (got {b['end_card'].get('headline')!r})")
    beats = load(base / b["music"]["beats"])
    downs = beats["downbeats"]; bar = downs[1] - downs[0]
    hook = next((h for h in b["hooks"] if h["id"] == a.hook), None) or die(f"no hook {a.hook}")

    # segments on consecutive downbeats
    segs, k = [], 0
    for i, s in enumerate(b["segments"]):
        start = downs[k]; dur = s["bars"] * bar
        end = start + dur; k += s["bars"]
        snap_err = min(abs(end - d) for d in downs + [downs[-1] + bar]) * FPS
        if snap_err > 1:
            die(f"segment {i} does not end on a downbeat (off by {snap_err:.2f} frames)")
        segs.append({"id": i, "clip": s["clip"], "src_in": s["in"], "src_out": round(s["in"] + dur, 4),
                     "start": round(start, 4), "end": round(end, 4), "frame_start": f(start), "frame_end": f(end),
                     "crop_y": s.get("crop", {}).get("y", 0), "label": s.get("label", ""),
                     "kind": s.get("kind", "footage"), "push_in": s.get("push_in", 0.03 if s.get("kind") == "presenter" else 0),
                     "push_origin": s.get("push_origin", [0.5, 0.3])})
    foot_end = segs[-1]["end"]
    ec = b["end_card"]; xf = ec.get("xfade_frames", 12) / FPS
    segs[-1]["src_out"] = round(segs[-1]["src_out"] + xf, 4)  # footage keeps moving under the crossfade (no freeze)
    total = foot_end + ec["bars"] * bar
    from _common import probe
    for s in segs:  # selects must exist in the source (no frozen or missing frames)
        _i = probe(base / s["clip"]); cd = float(next(x for x in _i["streams"] if x["codec_type"] == "video").get("duration") or _i["format"]["duration"])
        if s["src_out"] > cd - 0.01:
            die(f"segment {s['id']}: needs source up to {s['src_out']:.3f}s but {s['clip']} ends at {cd:.3f}s; move 'in' earlier")

    # captions (hook is line 0 on segment 0, starting frame 0)
    lines_in = [{"segment": 0, "text": hook["text"], "highlight": hook.get("highlight")}] + b.get("lines", [])
    cap_lines = []
    for ln in lines_in:
        seg = segs[ln["segment"]]
        words = ln["text"].split()
        t0 = seg["start"] + (0.0 if ln["segment"] == 0 else 0.0)
        ws = []
        for i, w in enumerate(words):
            spoken = t0 + i * WORD_STEP + (LIGHT_EARLY if i else 0)  # first hook word is visible on frame 0
            light = max(seg["start"], spoken - LIGHT_EARLY)
            ws.append({"w": w, "spoken": round(spoken, 3), "light": round(light, 3), "frame": f(light),
                       "hl": bool(ln.get("highlight")) and w.strip(".,!?").lower() == ln["highlight"].lower()})
            if ws[-1]["hl"]:
                ws[-1]["swipe"] = [round(max(seg["start"], light - SWIPE_LEAD), 3), round(SWIPE_DUR, 3)]
        cap_lines.append({"start": seg["start"], "end": seg["end"], "frame_start": seg["frame_start"],
                          "frame_end": seg["frame_end"], "text": ln["text"], "words": ws})

    for x in b.get("lines", []) + b.get("overlays", []):
        if not 0 <= x["segment"] < len(segs):
            die(f"brief: {x.get('type', 'line')} points at segment {x['segment']} but there are {len(segs)} segments")
    overlays = []
    for o in b.get("overlays", []):
        seg = segs[o["segment"]]
        end = foot_end if o["type"] == "offer_card" else seg["end"]
        overlays.append({**o, "start": seg["start"], "end": round(end, 4), "frame_start": seg["frame_start"], "frame_end": f(end)})
    overlays.append({"type": "end_card", "start": foot_end, "end": total, "frame_start": f(foot_end), "frame_end": f(total),
                     "xfade_frames": ec.get("xfade_frames", 12), "headline": ec["headline"], "url": ec["url"], "link": ec["link"]})

    # copy gate before anything renders
    strings = [l["text"] for l in cap_lines] + [o.get("text", "") for o in overlays] + [o.get("sub", "") for o in overlays] + [ec["headline"]]
    bad = {s: copy_violations(s) for s in strings if copy_violations(s)}
    for nm in b.get("private_names", []):
        for s_ in strings:
            if nm.replace(" ", "").lower() in s_.replace(" ", "").lower():
                bad.setdefault(s_, []).append(f"private name {nm!r}")
    if bad:
        die(f"copy gate: {bad}")

    # per-ratio boxes
    boxes = {}
    for r, L in LAYOUT.items():
        c = L["caption"]; rb = {"captions": [], "overlays": []}
        for li, ln in enumerate(cap_lines):
            wl = wrap([w["w"] for w in ln["words"]], "display", c["size"], c["maxw"])
            if len(wl) > c["max_lines"]:
                die(f"{r}: caption '{ln['text']}' needs {len(wl)} lines (max {c['max_lines']})")
            lb, wi = [], 0
            for row, line in enumerate(wl):
                for (w, x, ww) in line:
                    lb.append([round(c["x"] + x), round(c["y"] + row * c["size"] * c["lh"]), round(ww), round(c["size"] * c["lh"])])
                    wi += 1
            rb["captions"].append(lb)
        for o in overlays:
            if o["type"] == "dish_label":
                ch = L["chip"]; w = text_w(o["text"], "body", ch["size"]) + 2 * ch["pad"]
                rb["overlays"].append({"type": o["type"], "box": [ch["x"], ch["y"], round(w), ch["h"]]})
            elif o["type"] == "offer_card":
                of = L["offer"]; inner = of["w"] - 2 * of["pad"]
                hl = wrap(o["text"].split(), "display", of["size"], inner)
                sl = wrap(o.get("sub", "").split(), "body", of["sub"], inner) if o.get("sub") else []
                h = of["pad"] * 2 + len(hl) * of["size"] * 1.15 + (16 + len(sl) * of["sub"] * 1.3 if sl else 0) + 14
                rb["overlays"].append({"type": o["type"], "box": [of["x"], of["y"], of["w"], round(h)],
                                       "head_lines": [" ".join(w for w, _, _ in l) for l in hl],
                                       "sub_lines": [" ".join(w for w, _, _ in l) for l in sl]})
            elif o["type"] == "end_card":
                e = L["end"]; lx, ly, lw = e["logo"]
                hl = wrap(ec["headline"].split(), "display", e["head_size"], e["maxw"])
                hh = len(hl) * e["head_size"] * 1.1
                url_y = e["head_y"] + hh + 40
                uw = text_w(ec["url"], "body", e["url_size"])
                rb["overlays"].append({"type": "end_card", "logo": [lx, ly, lw, lw],
                                       "head": [lx, e["head_y"], round(max(text_w(" ".join(w for w, _, _ in l), "display", e["head_size"]) for l in hl)), round(hh)],
                                       "head_lines": [" ".join(w for w, _, _ in l) for l in hl],
                                       "head_widths": [round(text_w(" ".join(w for w, _, _ in l), "display", e["head_size"])) for l in hl],
                                       "url": [lx, round(url_y), round(uw), round(e["url_size"] * 1.4)],
                                       "box": [lx, ly, round(max(lw, uw, e["maxw"])), round(url_y + e["url_size"] * 1.4 - ly)]})
        boxes[r] = rb

    sfx = []
    for s in segs[1:]:
        sfx.append({"file": "audio/sfx_swish.wav", "at": round(s["start"] - 0.2, 4), "gain_db": -14, "why": "cut"})
    sfx.append({"file": "audio/sfx_swish.wav", "at": round(foot_end - 0.2, 4), "gain_db": -16, "why": "end card"})
    for o in overlays:
        if o["type"] in ("offer_card",):
            sfx.append({"file": "audio/sfx_pop.wav", "at": round(o["start"] + 0.03, 4), "gain_db": -12, "why": o["type"]})

    tl = {"version": 1, "fps": FPS, "duration": round(total, 4), "frames": f(total), "hook_id": a.hook,
          "brand": BRAND, "business": b.get("business", "business"),
          "private_names": b.get("private_names", []),
          "music": {"file": b["music"]["file"], "bpm": beats["bpm"], "downbeats": downs, "beats": beats["beats"]},
          "footage": {"file": "graded/footage_graded.mp4", "end": foot_end, "xfade_s": round(xf, 4)},
          "segments": segs, "captions": {"lines": cap_lines}, "overlays": overlays, "sfx": sfx,
          "grain": b.get("grain", {"file": "grain.png", "opacity": 0.045, "seed": 1234, "scale": 1}),
          "boxes": boxes, "step0": s0, "opener": op}
    save(tl, a.out)
    print(f"timeline {a.out}: {total:.3f}s ({f(total)} frames), cuts at {[s['start'] for s in segs[1:]] + [foot_end]}")


if __name__ == "__main__":
    main()
