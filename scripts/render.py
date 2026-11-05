#!/usr/bin/env python3
"""STEP 7-8 render the composition (Remotion) for each ratio from timeline.json. Picture only; sound is
mixed from the SAME timeline by mix_audio.py and joined by finish.py.

  render.py timeline.json --ratio 9x16 4x5 [--stills] [--concurrency 6]
--stills renders a still at every cut/cue first (Pixel & Oak loop: fix stills, then render the film).
Prepares <project>/_public (fonts, logos, grain.png, graded footage) and passes it as --public-dir.
Grain: one texture generated from the timeline's seed (same file, opacity, scale on every frame/ratio).
"""
import argparse, json, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from _common import load, run, SKILL, die, FPS

RENDER = SKILL / "render"


def make_grain(path, seed, cream="#FAF6F0", w=1080, h=1920, p=0.03, depth=170):
    """Paper grain: a cream sheet with sparse soft dark flecks plus a tiny uniform lift that cancels their
    mean, drawn at the timeline opacity with a normal blend. Cream has ~5 levels of headroom, so symmetric
    noise cannot be zero-mean there; sparse flecks can. Same seed -> byte-identical file every render.
    'overlay' blend was tried first and measured invisible on cream (std 0.05 levels), see references/grain.md."""
    rng = np.random.default_rng(seed)
    d = np.zeros((h, w))
    m = rng.random((h, w)) < p
    d[m] = -depth * rng.uniform(0.5, 1.0, m.sum())
    k = np.array([0.25, 0.5, 0.25])  # soft 3x3 fleck edge so the encoder keeps them instead of smearing
    d = sum(k[i] * np.roll(d, i - 1, 0) for i in range(3)); d = sum(k[i] * np.roll(d, i - 1, 1) for i in range(3))
    d *= 1 / (0.5 * 0.5)  # restore centre depth
    base = np.array([int(cream[i:i + 2], 16) for i in (1, 3, 5)], float)
    lift = min(-d.mean(), 255 - base.max())
    img = (base[None, None, :] + (d + lift)[..., None]).clip(0, 255)
    Image.fromarray(img.round().astype(np.uint8), "RGB").save(path)


def prepare_public(tl, base):
    pub = base / "_public"; pub.mkdir(exist_ok=True)
    for sub in ("fonts",):
        if (pub / sub).exists(): shutil.rmtree(pub / sub)
        shutil.copytree(RENDER / "public" / sub, pub / sub)
    for f in ("domin8te_logo_lockup.png", "domin8te_icon_infinity.png"):
        shutil.copy(RENDER / "public" / f, pub / f)
    g = tl["grain"]; make_grain(pub / g["file"], g["seed"])
    (pub / "graded").mkdir(exist_ok=True)
    shutil.copy(base / tl["footage"]["file"], pub / tl["footage"]["file"])
    return pub


def remotion(args):
    binp = RENDER / "node_modules" / ".bin" / "remotion"
    if not binp.exists():
        die(f"Remotion not installed: cd {RENDER} && npm ci  (versions pinned in package.json)")
    return run([str(binp)] + args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline"); ap.add_argument("--ratio", nargs="+", default=["9x16", "4x5"])
    ap.add_argument("--stills", action="store_true"); ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--out-dir", default="renders"); ap.add_argument("--no-graphics", action="store_true")
    a = ap.parse_args()
    tl = load(a.timeline); base = Path(a.timeline).resolve().parent
    import os; os.chdir(RENDER)  # remotion resolves the entry point from the render project
    pub = prepare_public(tl, base)
    out_dir = base / a.out_dir; out_dir.mkdir(exist_ok=True)
    stem = Path(a.timeline).stem.replace("timeline_", "")
    for r in a.ratio:
        props = out_dir / f"_props_{stem}_{r}.json"
        props.write_text(json.dumps({"tl": tl, "ratio": r, "showGraphics": not a.no_graphics}))
        common = ["--props", str(props), "--public-dir", str(pub), "--log", "error"]
        if a.stills:
            frames = sorted({0, *[s["frame_start"] for s in tl["segments"]], *[s["frame_start"] - 1 for s in tl["segments"][1:]],
                             *[o["frame_start"] + 10 for o in tl["overlays"]], tl["frames"] - 1})
            for fr in frames:
                remotion(["still", "src/index.ts", f"ad-{r}", str(out_dir / f"stills_{stem}_{r}" / f"f{fr:04d}.png"),
                          f"--frame={fr}"] + common)
            print(f"{r}: {len(frames)} stills -> {out_dir}/stills_{stem}_{r}/")
            continue
        out = out_dir / f"_picture_{stem}_{r}{'_nographics' if a.no_graphics else ''}.mp4"
        if True:
            remotion(["render", "src/index.ts", f"ad-{r}", str(out), "--codec", "h264", "--crf", "10",
                      "--color-space", "bt709", "--concurrency", str(a.concurrency), "--muted"] + common)
        print(f"{r}: picture -> {out}")


if __name__ == "__main__":
    main()
