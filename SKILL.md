---
name: video-editing
description: "Use when Karan wants a client's phone footage (or a screen recording of a client site) turned into a Domin8te paid ad for Facebook and Instagram: 9:16 and 4:5, hook variants that share one middle, moving presenter opener, half grade v1 on footage and presenter only, cream/ink/orange brand graphics, 'Book your free month' end card, Meta Sound Collection music, -14 LUFS, and pass/fail QA gates (Q1-Q13) before anything is called done. DRAFT v0.1, local package for manual upload to https://github.com/Karanveer252/video_editing; original draft at /workspace/skills/phone-to-ad-video/ untouched."
---

# video-editing (DRAFT v0.1, local package for video_editing)

Turns raw phone clips into a finished Domin8te ad: ingest, look, pick selects, grade the footage, lay brand graphics
over it in Remotion, mix sound from the same timeline, render 9:16 and 4:5, then run QA gates. A render is not done
until every gate passes. Nothing here uploads, posts, sends or deploys.

## STEP 0: HARD GATE, the five questions (before ANY generation)

Ask Karan conversationally, then WAIT. No selects, copy, render or AI generation before all five are answered:

1. What's the one thing this video has to make someone feel?
2. What's the subject or product, in a sentence?
3. Do you have a prop idea, or should I invent one that fits?
4. Is there a before-and-after or transformation angle?
5. Any specific effect you want, like the floating stat or typed-out words?

Question 5 is the ONLY place a copied effect is allowed. Save the answers in `brief.json` under `step0`
(`answered_by`: "Karan, <date>"). `build_timeline.py` refuses to build without all five. Running with no brief:
stop and output the questions.

## Standing rules (Karan; encoded as gates where possible)

| Rule | Where it is enforced |
|---|---|
| Five questions first | `build_timeline.py` STEP 0 gate |
| Half grade v1 (`references/domin8te_half_grade_v1.cube`, identical to `/workspace/research/color-grade/`) on footage and presenter layers only, BEFORE brand graphics | `grade_segments.py` grades the footage file before Remotion; Q7 checks cream is untouched and the grade matches an independent LUT |
| AD_VIDEO_STANDARD (`/workspace/ads-post/AD_VIDEO_STANDARD.md`) | Q1 spec, Q2 loudness, Q9 crossfade/no pop, Q11 frame OCR, Q12 opener motion, Q13 transcript |
| No echo or reverb on voices | `mix_audio.py` adds none; dialogue only gets 30 ms fades |
| Brand-neutral: the client's name becomes "business" | `brief.private_names` blocked in copy (build) and on screen (Q11 OCR) and in speech (Q13) |
| Screens fill the phone panel, no inner card | panel is `objectFit: cover`, footage crop fills it |
| Clean crossfade into the end card, one soundtrack, no leftover frames | Q9 |
| Check pieced-together headings up close | HUMAN check: full-res stills from `render.py --stills` |
| Moving presenter in the opener, never a still; ~3% push-in on top of real motion; skip the near-frozen first 0.5 s of an I2V clip; no 24-to-30 frame repeats | build opener gate, `ingest.py` optical-flow 24->30, Ad.tsx push-in, Q12 |
| 3D by default where relevant | phone panel settles from a perspective tilt; invented props default to a 3D look (clay/soft 3D render), flat only if Karan asks |
| End card "Book your free month" | build end card gate |
| Colours cream #FAF6F0, ink #1F2128, orange #F15C22 | `_common.BRAND`, Q7 cream dE |
| No prices, no em dashes, no "done-for-you", no "free checkup", nothing framed as an audit, report, score or grade | `copy_violations` at build (and Q8) |
| Music: Meta Sound Collection by default (SOUND.md 4), FB/IG only | licence check in `mix_audio.py` (allowed list, `meta-only` accepted because these ads run on Facebook and Instagram only) |
| Facebook and Instagram only | no other placements are planned or exported |

Not touched by this skill: the pending custom-music-only rule (left as Karan has it), Apify, billing, account
settings, any secret. Never print secrets.

## Pipeline

```
ingest.py PROJECT clip...           probe, rotate, HDR->SDR, BT.601->709, VFR->30 CFR, 24 fps -> 30 by optical flow
contact_sheet.py clip -o sheet.png  LOOK before choosing anything (also --timeline for cut/cue frames)
transcribe.py / filler_cut.py       speech clips only: word timings, filler-cut PROPOSAL for review
(write brief.json)                  step0, opener, segments (presenter first), hooks, lines, overlays, end_card, private_names
build_timeline.py brief --hook A    one timeline.json drives picture AND sound; cuts snap to downbeats
grade_segments.py timeline          crop to panel, half grade v1, frame-exact segments, footage_graded/ungraded.mp4
mix_audio.py timeline -o mix.wav    licence check, music + SFX at cue times, -14 LUFS / -1 dBTP linear
render.py timeline --ratio 9x16 4x5 Remotion picture (--stills first for review)
finish.py picture mix -o final.mp4  H.264 yuv420p 30 CFR BT.709 tv, AAC 48k, +faststart, exact frame count
qa.py final --timeline --ratio      Q1-Q13; exit 1 on any FAIL; writes _qa_report.json and _receipt.json
variants.py brief                   all of the above for every hook, one shared middle (one-variable rule)
```

Before choosing selects, OCR the source (`ocr_check.py` on the ingest clip with `--names`) and pick windows with
no private names. Do not blur or inpaint client text unless Karan asks (untested on food).

## QA gates

Q1 delivery spec, Q2 loudness, Q3 safe zones, Q4 caption timing, Q5 cut on beat, Q6 grain, Q7 colour,
Q7b LUT saturation (WARN, known half grade v1 behaviour), Q8 copy, Q9 end card, Q10 hook on frame 1,
Q11 privacy OCR, Q12 opener moves, Q13 speech privacy. HUMAN checks (never automated): the "remove the graphics,
does it still work?" look at `footage_graded.mp4`, headings up close, one full watch on a phone with sound.

## Hand-off rules

- One ad at a time; Karan approves each before the next.
- Approved ads only go to `C:\Users\kvsd1\OneDrive\Desktop\ads final\ads upload final\` after his approval.
- Never post, upload to Meta, push to git, or deploy as part of an edit.

Setup and the end-to-end test: `README.md`. Research behind each technique (PROVEN vs UNTESTED): `research/EXTRACTION.md`.
Status of this draft: `STATUS.md`.
