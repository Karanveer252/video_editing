"""Shared helpers for video-editing scripts. stdlib + numpy only."""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
BRAND = {"cream": "#FAF6F0", "ink": "#1F2128", "orange": "#F15C22"}
FPS = 30
RATIOS = {"9x16": (1080, 1920), "4x5": (1080, 1350)}


def die(msg, code=2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def need(binary):
    if not shutil.which(binary):
        die(f"{binary} not found on PATH")


def run(cmd, capture=False, check=True):
    r = subprocess.run(cmd, capture_output=capture, text=capture)
    if check and r.returncode != 0:
        err = r.stderr if capture else ""
        die(f"command failed ({r.returncode}): {' '.join(map(str, cmd))[:300]}\n{err[-2000:] if err else ''}")
    return r


def probe(path):
    need("ffprobe")
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], capture=True)
    return json.loads(r.stdout)


def vstream(info):
    return next((s for s in info["streams"] if s.get("codec_type") == "video"), None)


def astream(info):
    return next((s for s in info["streams"] if s.get("codec_type") == "audio"), None)


def rotation(vs):
    for sd in vs.get("side_data_list", []) or []:
        if "rotation" in sd:
            return int(round(float(sd["rotation"])))
    tag = (vs.get("tags") or {}).get("rotate")
    return int(tag) if tag else 0


def sha256(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2))


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# Delivery encode: AD_VIDEO_STANDARD + COLOR.md (limited-range BT.709, tagged)
ENC_V = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-fps_mode", "cfr",
         "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709"]
ENC_A = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]

# Copy rules (Domin8te): no prices, no em/en dashes, never "done-for-you" / "free checkup",
# nothing framed as an audit, report, score, grade or analysis. Digits banned in on-screen copy
# (prices hide in digits); the URL and the logo are exempt.
import re as _re
BANNED = [r"done[- ]?for[- ]?you", r"free check[- ]?up", r"\baudit", r"\bscor(e|es|ed|ing)\b", r"\bgrad(e|es|ed|ing)\b",
          r"\breports?\b", r"\banaly[sz]", r"\bpdf\b", r"\bcomment\b", r"\$", r"\u00a3", r"\u20ac", "\u2014", "\u2013",
          r"\bprice", r"\bcost", r"\bdomin(?:ate|8)\b(?!te)"]


def copy_violations(text):
    hits = []
    for b in BANNED:
        hits += [m.group(0) for m in _re.finditer(b, text, _re.I)]
    hits += _re.findall(r"\d", text)
    return sorted(set(hits))
