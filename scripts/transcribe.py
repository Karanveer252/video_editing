#!/usr/bin/env python3
"""STEP 3a transcript: word-level, verbatim (keeps um/uh so the filler cut can see them), cached by file hash.

Engine: local faster-whisper (open source, runs on the box, no account, no upload).
ElevenLabs Scribe (what video-use uses) is an option only if Karan approves sending audio to it.

usage: transcribe.py IN.(mov|mp4|wav) -o words.json [--model small.en] [--start S --end E]
Output: {"source", "sha256", "engine", "words":[{"w","start","end","p"}], "segments":[...]}
Speechless clip: writes words=[] and says so (no fake captions).
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _common import sha256, save, die

CACHE = Path.home() / ".cache" / "video-editing" / "transcripts"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--model", default="small.en"); ap.add_argument("--start", type=float); ap.add_argument("--end", type=float)
    a = ap.parse_args()
    h = sha256(a.input)
    key = f"{h[7:23]}_{a.model}_{a.start}_{a.end}.json"
    CACHE.mkdir(parents=True, exist_ok=True)
    if (CACHE / key).exists():
        Path(a.out).write_text((CACHE / key).read_text()); print(f"cached -> {a.out}"); return
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die("faster-whisper not installed. Run: python3 -m venv .venv && .venv/bin/pip install faster-whisper ; then use .venv/bin/python")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        cmd = ["ffmpeg", "-y", "-v", "error"]
        if a.start is not None: cmd += ["-ss", str(a.start)]
        if a.end is not None: cmd += ["-to", str(a.end)]
        cmd += ["-i", a.input, "-vn", "-ac", "1", "-ar", "16000", str(wav)]
        if subprocess.run(cmd).returncode:
            die("no audio stream to transcribe")
        model = WhisperModel(a.model, device="cpu", compute_type="int8")
        # verbatim: no prompt that cleans fillers; word timestamps on
        import wave, numpy as np
        with wave.open(str(wav)) as wf:  # pass samples, not a path (avoids PyAV version clashes)
            audio = np.frombuffer(wf.readframes(wf.getnframes()), "<i2").astype(np.float32) / 32768
        segs, info = model.transcribe(audio, word_timestamps=True, vad_filter=False,
                                      initial_prompt="Umm, uh, so, like, you know, I mean, hmm.")
        off = a.start or 0.0
        words, segments = [], []
        for s in segs:
            segments.append({"start": round(s.start + off, 3), "end": round(s.end + off, 3), "text": s.text.strip()})
            for w in s.words or []:
                words.append({"w": w.word.strip(), "start": round(w.start + off, 3), "end": round(w.end + off, 3),
                              "p": round(w.probability, 3)})
    out = {"source": a.input, "sha256": h, "engine": f"faster-whisper {a.model}", "language": info.language,
           "words": words, "segments": segments,
           "note": "speechless clip: no words found" if not words else ""}
    save(out, a.out); (CACHE / key).write_text(json.dumps(out, indent=2))
    print(f"{len(words)} words -> {a.out}")


if __name__ == "__main__":
    main()
