# video-editing: STATUS

- Date: 2026-11-04, 10:52 CT
- Version: DRAFT v0.1, local only. Not pushed and not in any repo. Not copied into agent-data/workflows.

## What it does

The skill turns a business's phone footage into short FB/IG ads (10 s, 9:16 and 4:5) in the Domin8te style:
cream page (#FAF6F0), ink (#1F2128), orange highlight (#F15C22), Montserrat/Inter, footage in a phone panel
with a 3D tilt settle, a moving presenter opener, word-by-word captions, cuts on the beat, the half grade on the
footage layer only, and an end card "Book your free month". The pipeline runs ingest, transcribe, filler cut,
beats, timeline, grade, Remotion render, mix and finish. Then `qa.py` runs 14 automatic gates (Q1 to Q13 plus Q7b), and
a render only counts as done when it has 0 FAIL. `variants.py` builds hooks A/B/C x both ratios.

## Files

- `SKILL.md`, `README.md`: the workflow and setup
- `references/`: `shoot-guide.md`, `domin8te_half_grade_v1.cube`, `half_grade_v1_ffmpeg_filter.txt`
- `templates/brief.example.json`: example brief (step 0 answers are a TEST ASSUMPTION, see below)
- `scripts/`: `_common.py`, `ingest.py`, `transcribe.py`, `filler_cut.py`, `beats.py`, `build_timeline.py`, `layout.py`,
  `grade_segments.py`, `render.py`, `synth_audio.py`, `mix_audio.py`, `finish.py`, `ocr_check.py`, `qa.py`,
  `contact_sheet.py`, `variants.py`
- `render/`: Remotion project (`src/Ad.tsx`, `Root.tsx`, `fonts.ts`, `types.ts`, `index.ts`, fonts and logos in `public/`)
- `tests/`: `test_units.py`, `qa_negative.sh`, `run_test_ad.sh`
- `research/`: `EXTRACTION.md` plus the `_src/` reference clones (103 MB; leave these out of any repo)
- `test-output/project-v2/`: the full test project (renders, sheets, graded footage, timelines)

## Test results (2026-11-04)

- Unit tests: `python3 -m unittest tests/test_units.py -v` gives 16 of 16 OK. The ERROR lines from the licence test
  are expected stderr.
- Negative QA: `bash tests/qa_negative.sh test-output/project-v2` exits 0.
  Part 1: a broken file gets Q1, Q2 and Q9 FAIL. Part 2: a still opener with a fake zoom gets Q12 FAIL
  (mean change 0.00, 59 repeated frames).
- Render gates (from `renders/*_qa_report.json`):

| Render | FAIL | WARN | Q7b | Q12 opener | Q13 speech |
|---|---|---|---|---|---|
| ad_A_9x16 | 0 | 1 | WARN | PASS | PASS |
| ad_A_4x5  | 0 | 1 | WARN | PASS | PASS |
| ad_B_9x16 | 0 | 1 | WARN | PASS | PASS |
| ad_B_4x5  | 0 | 1 | WARN | PASS | PASS |
| ad_C_9x16 | 0 | 1 | WARN | PASS | PASS |
| ad_C_4x5  | 0 | 1 | WARN | PASS | PASS |

All other gates (Q1 to Q12 except Q7b) PASS on all six renders. Loudness is -14.0 LUFS and true peak is -1.7 dBTP.

- Visual check of `sheets/ad_A_9x16_sheet.png` and full-res stills in `sheets/stills/`:
  - The presenter opener moves.
  - The panel tilt is visible at f0 and flat by f14.
  - The end card reads "Book your free month" in both ratios, with the URL domin8temedia.com/marketing/free-month.
  - I saw no private names on the sheet.

## Render paths (test-output/project-v2/)

- `renders/ad_{A,B,C}_{9x16,4x5}.mp4`, each with `_qa_report.json`, `_receipt.json` and `_ocr.json`
- `renders/variants_summary.json`
- `sheets/ad_{A,B,C}_{9x16,4x5}_sheet.png`, `sheets/graded_sheet.png`, `sheets/stills/`
- Negative test scratch: `renders/_neg/` and `graded/_neg_still_opener.mp4`

## Known gaps

- The source footage has on-site web text with the client's script logo "Lecookie", an em dash and "1-2 business
  days". OCR (Q11) misses the script logo, and Q8 only checks our own on-screen strings, not text inside the footage.
- Q7b: half grade v1 collapses 7 of 4524 saturated chart colours to grey (worst saturation loss 0.59). This is a known LUT defect.
- The test music is a synth placeholder. Meta Sound Collection has no API. Add a track in Ads Manager or download it to
  `sounds/meta/`.
- The presenter is Freddy's AI test clip. The finger stays raised and the mouth moves silently, so the Q13 transcript is empty.
- The step 0 answers in the test brief are an agent TEST ASSUMPTION, not Karan's.
- Safe zones are untested in Ads Manager, and ad performance is untested.
- A framemd5 check against the approved version is not implemented.

## Decisions for Karan before any push

1. His real five step 0 answers.
2. A real Meta Sound Collection track.
3. Which presenter clip to use.
4. Whether to accept Q7b (half grade v1) or fix the LUT.
5. Whether to mask client logos and text inside the footage.
6. Where the repo goes: a new repo, or a folder in motion-graphics-skill.
