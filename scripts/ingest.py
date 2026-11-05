#!/usr/bin/env python3
"""STEP 1 ingest: copy phone clips into the project and normalise them. Originals are never touched.

For each input: probe -> report (codec, size, fps, VFR?, rotation, HDR?, colour tags, audio) ->
write a mezzanine copy to <project>/ingest/<name>.mp4:
  - rotation applied (phones store portrait as landscape + rotate tag)
  - HDR (PQ/HLG, e.g. iPhone Dolby Vision HEVC) tone-mapped to SDR BT.709 BEFORE any grade
  - variable frame rate -> 30 fps CFR
  - untagged colour: decoded with --assume-matrix (default bt709) and converted to BT.709 tv
  - audio -> 48 kHz stereo PCM
  - high quality intermediate (x264 crf 12) so the grade has headroom
Writes <project>/ingest/ingest.json with source sha256 (for the receipt).

usage: ingest.py PROJECT_DIR clip1.mov [clip2.mp4 ...] [--assume-matrix bt601] [--trim START:END]
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _common import probe, vstream, astream, rotation, sha256, run, save, FPS, die

HDR_TRC = {"smpte2084", "arib-std-b67"}


def describe(path):
    info = probe(path)
    vs, as_ = vstream(info), astream(info)
    if not vs:
        die(f"{path}: no video stream")
    num, den = (int(x) for x in vs.get("avg_frame_rate", "0/1").split("/"))
    rnum, rden = (int(x) for x in vs.get("r_frame_rate", "0/1").split("/"))
    avg = num / den if den else 0
    rfr = rnum / rden if rden else 0
    return {
        "path": str(path), "sha256": sha256(path), "bytes": Path(path).stat().st_size,
        "duration": float(info["format"]["duration"]), "codec": vs["codec_name"],
        "width": vs["width"], "height": vs["height"], "pix_fmt": vs.get("pix_fmt"),
        "avg_fps": round(avg, 3), "r_fps": round(rfr, 3), "vfr": abs(avg - rfr) > 0.01,
        "rotation": rotation(vs),
        "color": {k: vs.get(k, "unknown") for k in ("color_range", "color_space", "color_transfer", "color_primaries")},
        "hdr": vs.get("color_transfer") in HDR_TRC,
        "audio": ({"codec": as_["codec_name"], "rate": int(as_["sample_rate"]), "ch": as_["channels"]} if as_ else None),
    }


def build_vf(d, assume_matrix):
    vf = []
    # ffmpeg autorotates by default when decoding; we keep that and just record it.
    if d["hdr"]:
        # zscale tone map: PQ/HLG -> linear -> hable -> BT.709 tv
        vf += ["zscale=tin=%s:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=100" % d["color"]["color_transfer"], "format=gbrpf32le", "zscale=p=bt709", "tonemap=hable:desat=0",
               "zscale=t=bt709:m=bt709:r=tv", "format=yuv420p"]
    else:
        src_m = d["color"]["color_space"]
        if src_m in ("unknown", "", None):
            src_m = assume_matrix
        src_m = {"smpte170m": "bt601", "bt470bg": "bt601"}.get(src_m, src_m)
        src_r = "pc" if d["color"]["color_range"] == "pc" else "tv"
        if src_m == "bt601" or src_r == "pc":
            vf += [f"scale=in_color_matrix={src_m}:out_color_matrix=bt709:in_range={src_r}:out_range=tv"]
        vf += ["format=yuv420p"]
    if not d["vfr"] and 0 < d["avg_fps"] < FPS - 0.01:
        # AD_VIDEO_STANDARD 2: never frame-repeat 24 fps up to 30. Optical-flow in-betweens instead.
        vf += [f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"]
    else:
        vf += [f"fps={FPS}"]
    return ",".join(vf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project"); ap.add_argument("clips", nargs="+")
    ap.add_argument("--assume-matrix", default="bt709", choices=["bt709", "bt601"],
                    help="matrix for UNTAGGED sources (ffmpeg-skill rule: untagged = bt709 unless you know better)")
    ap.add_argument("--trim", help="START:END seconds, applied to every clip")
    a = ap.parse_args()
    out_dir = Path(a.project) / "ingest"; out_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for c in a.clips:
        d = describe(c)
        out = out_dir / (Path(c).stem + ".mp4")
        if out.resolve() == Path(c).resolve():
            die("refusing to overwrite the original")
        cmd = ["ffmpeg", "-y", "-v", "error"]
        if a.trim:
            s, e = a.trim.split(":"); cmd += ["-ss", s, "-to", e]
        cmd += ["-i", c, "-map", "0:v:0"] + (["-map", "0:a:0"] if d["audio"] else []) + ["-vf", build_vf(d, a.assume_matrix),
                "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-g", "15",
                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
        cmd += (["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"] if d["audio"] else ["-an"])
        cmd += [str(out).replace(".mp4", ".mov")]
        out = Path(str(out).replace(".mp4", ".mov"))
        run(cmd)
        d["mezzanine"] = str(out)
        d["actions"] = [x for x in [
            "tone-mapped HDR to SDR BT.709" if d["hdr"] else None,
            f"rotation {d['rotation']} applied" if d["rotation"] else None,
            "VFR to 30 fps CFR" if d["vfr"] else (f"{d['avg_fps']} fps to 30 fps by optical flow (no repeated frames)" if d['avg_fps'] < FPS - 0.01
                                    else f"{d['avg_fps']} fps to 30 fps" if abs(d['avg_fps'] - FPS) > 0.01 else None),
            (f"untagged colour decoded as {a.assume_matrix}" if d["color"]["color_space"] in ("unknown", None) else None),
        ] if x]
        report.append(d)
        print(f"{Path(c).name}: {d['codec']} {d['width']}x{d['height']} {d['avg_fps']}fps rot={d['rotation']} "
              f"hdr={d['hdr']} -> {out.name}  [{'; '.join(d['actions']) or 'no changes needed'}]")
    save({"clips": report}, out_dir / "ingest.json")


if __name__ == "__main__":
    main()
