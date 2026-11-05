#!/usr/bin/env python3
"""STEP 5 grade, FOOTAGE LAYER ONLY. Extract each timeline segment, crop to the panel aspect,
apply half grade v1 (references/domin8te_half_grade_v1.cube, tetrahedral), concat in output order.

Why here and not in Remotion: grading the footage file before composition means the LUT can never
touch the cream page, the ink type, the orange highlighter, the logo or the grain (COLOR.md:
"no LUT on the picture"; Karan's ask: half grade per layer, footage only). Gate Q7 verifies it.

Colour pipeline is explicit (no swscale BT.601 default): yuv bt709 tv -> gbrp -> lut3d -> yuv bt709 tv.
Writes graded/footage_graded.mp4 and graded/footage_ungraded.mp4 (same cuts, no grade; used by the
colour gate and the DSNRY "remove the graphics" check).
usage: grade_segments.py timeline.json [--strength 1.0] [--keep-audio]
"""
import argparse, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _common import load, run, probe, vstream, SKILL, FPS, die
from layout import LAYOUT

LUT = SKILL / "references" / "domin8te_half_grade_v1.cube"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline"); ap.add_argument("--keep-audio", action="store_true")
    ap.add_argument("--lut", default=str(LUT))
    a = ap.parse_args()
    tl = load(a.timeline); base = Path(a.timeline).parent
    out_dir = base / "graded"; out_dir.mkdir(exist_ok=True)
    p = LAYOUT["9x16"]["panel"]; aspect = p["w"] / p["h"]
    for r, L in LAYOUT.items():
        if abs(L["panel"]["w"] / L["panel"]["h"] - aspect) > 0.005:
            die(f"panel aspect differs in {r}; one graded file must serve every ratio")
    OUT_W = 960; OUT_H = round(OUT_W / aspect); OUT_H -= OUT_H % 2
    for graded in (True, False):
        parts = []
        for s in tl["segments"]:
            src = base / s["clip"]
            vs = vstream(probe(src)); W, H = vs["width"], vs["height"]
            y0 = s.get("crop_y", 0); ch = H - y0; cw = round(ch * aspect)
            if cw > W:
                cw = W; ch = round(W / aspect)
            cw -= cw % 2; ch -= ch % 2
            x0 = (W - cw) // 2
            # every segment lands at one size so the concat is valid (phone clips and the presenter differ)
            vf = [f"crop={cw}:{ch}:{x0}:{y0}", f"scale={OUT_W}:{OUT_H}:flags=lanczos"]
            if graded:
                vf += ["scale=in_color_matrix=bt709:in_range=tv:out_range=pc,format=gbrp",
                       f"lut3d=file={a.lut}:interp=tetrahedral",
                       "scale=out_color_matrix=bt709:out_range=tv:in_range=pc,format=yuv420p"]
            vf += [f"fps={FPS}", "setsar=1"]
            dur = s["src_out"] - s["src_in"]
            part = out_dir / f"_seg{s['id']}{'' if graded else '_ungraded'}.mp4"
            # in-point snapped to the 30 fps grid and an exact frame count, so no segment drops or repeats a frame
            cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{round(s['src_in'] * FPS) / FPS:.4f}", "-i", str(src),
                   "-frames:v", str(round(dur * FPS)),
                   "-vf", ",".join(vf), "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-g", "15",
                   "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
            if a.keep_audio:  # 30 ms fades at every boundary (video-use rule)
                cmd += ["-af", f"afade=t=in:d=0.03,afade=t=out:st={dur - 0.03:.4f}:d=0.03", "-c:a", "aac", "-ar", "48000"]
            else:
                cmd += ["-an"]
            run(cmd + [str(part)])
            n = int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                         "stream=nb_read_frames", "-of", "csv=p=0", str(part)], capture=True).stdout.strip())
            if n != round(dur * FPS):
                die(f"segment {s['id']}: {n} frames, expected {round(dur * FPS)}")
            parts.append(part)
        lst = out_dir / "_concat.txt"; lst.write_text("".join(f"file '{p_.name}'\n" for p_ in parts))
        out = out_dir / ("footage_graded.mp4" if graded else "footage_ungraded.mp4")
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
        d = float(probe(out)["format"]["duration"])
        print(f"{out.name}: {d:.3f}s, {len(parts)} segments, out {OUT_W}x{OUT_H}, {'half grade v1' if graded else 'no grade'}")


if __name__ == "__main__":
    main()
