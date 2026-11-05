"""Layout per ratio (pixels). Single source for render boxes AND the safe-zone gate.

9:16 rules carried from avatar-motion-explainer v2.2:
  - top inset y 0-270 stays empty (platform header)
  - ALL text inside x 120-960, y 270-1248, and never in the right rail (x > 780 and y > 840)
  - captions top-left from x120 y360, max width 780
4:5: captions x 65-800, y 120-460; text zone x 65-1015, y 68-1215 (Meta feed ~5% top, ~10% bottom keep-clear,
     ad-video-skills platform-specs table, UNTESTED; verify in Ads Manager preview).
Footage may run into keep-clear areas; text may not.
"""
from pathlib import Path
from PIL import ImageFont

FONTS = Path(__file__).resolve().parent.parent / "render" / "public" / "fonts"

LAYOUT = {
    "9x16": {
        "W": 1080, "H": 1920,
        "text_zone": [120, 270, 960, 1248], "rail": [780, 840], "top_inset": 270,
        "caption": {"x": 120, "y": 360, "maxw": 780, "size": 66, "lh": 1.2, "max_lines": 3},
        "panel": {"x": 160, "y": 640, "w": 760, "h": 1180, "r": 36},
        "chip": {"x": 120, "y": 600, "size": 34, "h": 72, "pad": 28},
        "offer": {"x": 120, "y": 880, "w": 660, "size": 54, "sub": 30, "pad": 40},
        "end": {"logo": [120, 330, 200], "head_y": 580, "head_size": 108, "url_y": 0, "url_size": 30, "maxw": 760},
    },
    "4x5": {
        "W": 1080, "H": 1350,
        "text_zone": [65, 68, 1015, 1215], "rail": None, "top_inset": 68,
        "caption": {"x": 65, "y": 120, "maxw": 735, "size": 58, "lh": 1.2, "max_lines": 3},
        "panel": {"x": 270, "y": 420, "w": 540, "h": 838, "r": 30},
        "chip": {"x": 65, "y": 384, "size": 30, "h": 64, "pad": 24},
        "offer": {"x": 65, "y": 700, "w": 600, "size": 50, "sub": 28, "pad": 36},
        "end": {"logo": [65, 120, 180], "head_y": 340, "head_size": 104, "url_y": 0, "url_size": 30, "maxw": 760},
    },
}


def font(kind, size):
    f = ImageFont.truetype(str(FONTS / ("Montserrat-Variable.ttf" if kind == "display" else "Inter-Variable.ttf")), size)
    try:
        f.set_variation_by_axes([800] if kind == "display" else [32, 700])
    except Exception:
        try:
            f.set_variation_by_name("ExtraBold" if kind == "display" else "Bold")
        except Exception:
            pass
    return f


def text_w(txt, kind, size):
    return font(kind, size).getlength(txt)


def wrap(words, kind, size, maxw):
    """Greedy wrap; returns list of lines, each a list of (word, x_offset, width)."""
    f = font(kind, size); space = f.getlength(" ")
    lines, cur, x = [], [], 0.0
    for w in words:
        ww = f.getlength(w)
        if cur and x + ww > maxw:
            lines.append(cur); cur, x = [], 0.0
        cur.append((w, x, ww)); x += ww + space
    if cur:
        lines.append(cur)
    return lines
