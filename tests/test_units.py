"""Unit tests (no rendering). Run: python3 -m pytest -q tests/  (or python3 tests/test_units.py)"""
import sys, tempfile, json, subprocess
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _common import copy_violations, BRAND
from filler_cut import propose
from layout import LAYOUT, text_w, wrap
import qa


def test_copy_rules_block_banned():
    for bad in ["Our done-for-you service", "Get a free checkup", "Website audit", "Your score", "Read the report",
                "Only $49", "Fast \u2014 clean", "SEO analysis", "Grade your site", "Save 20%"]:
        assert copy_violations(bad), bad


def test_copy_rules_allow_clean():
    for ok in ["Your first month is on us", "Book your free month", "So we rebuilt it around the food.",
               "People eat with their eyes first. Online too.", "Baked to order"]:
        assert not copy_violations(ok), ok


def W(w, s, e):
    return {"w": w, "start": s, "end": e}


def test_filler_cut_removes_um_and_gap_never_inside_word():
    words = [W("We", 0.0, 0.2), W("um", 0.3, 0.5), W("bake", 0.6, 0.9), W("daily", 1.6, 2.0)]
    r = propose(words, 0.0, 2.0, gap=0.4, pad=0.05)
    whys = [x["why"] for x in r["removed"]]
    assert any("filler" in w for w in whys) and any("gap" in w for w in whys)
    for s, e in r["keep"]:
        for w in words:
            if w["w"] != "um":
                assert not (w["start"] + 0.01 < s < w["end"] - 0.01) and not (w["start"] + 0.01 < e < w["end"] - 0.01)


def test_filler_cut_flags_ambiguous_not_cut():
    words = [W("So", 0.0, 0.2), W("like", 0.25, 0.4), W("this", 0.45, 0.7)]
    r = propose(words, 0.0, 0.7, gap=0.4, pad=0.05)
    assert {f["w"] for f in r["flagged"]} >= {"So", "like"} and not r["removed"]


def test_safe_zone_inside():
    z = LAYOUT["9x16"]["text_zone"]
    assert qa.inside([120, 360, 700, 80], z) and not qa.inside([100, 360, 700, 80], z) and not qa.inside([120, 200, 100, 80], z)


def test_wrap_respects_width():
    lines = wrap("Your website should taste as good as your food.".split(), "display", 66, 780)
    for ln in lines:
        assert text_w(" ".join(w for w, _, _ in ln) if isinstance(ln[0], tuple) else " ".join(ln), "display", 66) <= 780


def test_lut_identity_and_independent_interp():
    n = 5; g = np.linspace(0, 1, n)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")
    ident = np.stack([r, gg, b], -1)
    px = np.array([[12, 200, 77], [255, 0, 128], [0, 0, 0]], float)
    assert np.abs(qa.apply_cube(px, n, ident) - px).max() < 1e-6


def test_beats_verify_on_synth():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "synth_audio.py"), d, "--bars", "4"], check=True,
                       capture_output=True)
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "beats.py"), f"{d}/music.wav", "--detect",
                             "--verify", f"{d}/beats.json"], capture_output=True, text=True)
        assert rc.returncode == 0, rc.stdout + rc.stderr


def _brief_tmp(d, **over):
    """Minimal brief + beats in a temp project; clip is a tiny synthetic moving test pattern."""
    d = Path(d); (d / "audio").mkdir(); (d / "ingest").mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=540x960:rate=30:duration=6",
                    "-pix_fmt", "yuv420p", str(d / "ingest" / "clip.mp4")], check=True)
    json.dump({"bpm": 120, "beats": [i * 0.5 for i in range(20)], "downbeats": [0, 2, 4, 6, 8]}, open(d / "audio/beats.json", "w"))
    b = json.load(open(ROOT / "templates" / "brief.example.json"))
    b["step0"] = {k: "x" for k in ("feel", "subject", "prop", "before_after", "specific_effect")}
    b["segments"] = [{"kind": "presenter", "clip": "ingest/clip.mp4", "in": 0.0, "bars": 1},
                     {"clip": "ingest/clip.mp4", "in": 2.0, "bars": 1}]
    b["lines"] = []; b["overlays"] = [{"type": "dish_label", "segment": 1, "text": "Made to order"}]
    b["private_names"] = ["Le Cookie"]
    b.update(over)
    json.dump(b, open(d / "brief.json", "w"))
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "build_timeline.py"), str(d / "brief.json"), "--hook", "A",
                           "-o", str(d / "tl.json")], capture_output=True, text=True)


def test_timeline_builds_with_presenter_opener():
    with tempfile.TemporaryDirectory() as d:
        r = _brief_tmp(d); assert r.returncode == 0, r.stderr
        tl = json.load(open(Path(d) / "tl.json"))
        assert tl["segments"][0]["kind"] == "presenter" and tl["segments"][0]["push_in"] == 0.03


def test_five_question_gate_blocks():
    with tempfile.TemporaryDirectory() as d:
        r = _brief_tmp(d, step0={"feel": "warm"})
        assert r.returncode != 0 and "STEP 0" in r.stderr


def test_opener_gate_needs_presenter_or_waiver():
    with tempfile.TemporaryDirectory() as d:
        r = _brief_tmp(d, segments=[{"clip": "ingest/clip.mp4", "in": 0.0, "bars": 1}, {"clip": "ingest/clip.mp4", "in": 2.0, "bars": 1}])
        assert r.returncode != 0 and "opener gate" in r.stderr
    with tempfile.TemporaryDirectory() as d:
        r = _brief_tmp(d, segments=[{"clip": "ingest/clip.mp4", "in": 0.0, "bars": 1}, {"clip": "ingest/clip.mp4", "in": 2.0, "bars": 1}], opener={"waiver": "Karan: no presenter on this one"})
        assert r.returncode == 0, r.stderr


def test_end_card_must_say_book_your_free_month():
    with tempfile.TemporaryDirectory() as d:
        ec = json.load(open(ROOT / "templates" / "brief.example.json"))["end_card"]; ec["headline"] = "Get a free checkup"
        r = _brief_tmp(d, end_card=ec)
        assert r.returncode != 0 and "end card gate" in r.stderr


def test_private_name_in_copy_blocked():
    with tempfile.TemporaryDirectory() as d:
        r = _brief_tmp(d, overlays=[{"type": "dish_label", "segment": 1, "text": "Le Cookie favourites"}])
        assert r.returncode != 0 and "private name" in r.stderr


def test_licence_check_rules():
    sys.path.insert(0, str(ROOT / "scripts"))
    import mix_audio
    with tempfile.TemporaryDirectory() as d:
        lic = Path(d) / "LICENCES.csv"
        hdr = "file,source_url,licence,author,attribution_required,paid_ads_allowed,downloaded_on,notes\n"
        lic.write_text(hdr + "m.wav,u,Meta-Sound-Collection,Meta,no,meta-only,2026-11-04,\n")
        mix_audio.licence_check([Path(d) / "m.wav"], lic)  # Meta Sound Collection is fine on FB/IG-only ads
        for bad in ["m.wav,u,Mixkit,x,no,yes,2026-11-04,\n", "m.wav,u,CC0,x,yes,yes,2026-11-04,\n", "m.wav,u,CC0,x,no,no,2026-11-04,\n"]:
            lic.write_text(hdr + bad)
            try:
                mix_audio.licence_check([Path(d) / "m.wav"], lic); raise AssertionError(bad)
            except SystemExit:
                pass


def test_ingest_uses_optical_flow_for_24fps():
    import ingest
    d = {"hdr": False, "vfr": False, "avg_fps": 24.0, "color": {"color_space": "bt709", "color_range": "tv"}}
    vf = ingest.build_vf(d, "bt709")
    assert "minterpolate" in vf and "fps=30" not in vf.replace("minterpolate=fps=30", "")


def test_q13_decode_gives_mono_16k_float_array():
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "tone.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=1:sample_rate=44100", "-ac", "2", str(wav)], check=True)
        out = subprocess.run([x.replace("{}", str(wav)) for x in qa.DECODE_16K], capture_output=True, check=True).stdout
        a = np.frombuffer(out, np.float32)
        assert abs(len(a) - 16000) <= 32, len(a)
        assert 0.05 < float(np.abs(a).max()) <= 1.0


def load_tests(loader, tests, pattern):
    # lets "python3 -m unittest tests/test_units.py" run the plain test_ functions
    import unittest
    return unittest.TestSuite(unittest.FunctionTestCase(f, description=k) for k, f in globals().items() if k.startswith("test_"))


if __name__ == "__main__":
    fails = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            try:
                f(); print("ok  ", k)
            except Exception as e:
                fails += 1; print("FAIL", k, repr(e))
    sys.exit(1 if fails else 0)
