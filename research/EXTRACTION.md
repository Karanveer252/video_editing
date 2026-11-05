# EXTRACTION: phone footage to restaurant ad (research, 2026-11-04 CT)

Proof rule (Karan): a technique is **PROVEN** only when a source shows a measured or
reproducible result, or when we measured it ourselves on this box. Everything else is
**UNTESTED**, however popular the repo. Stars and downloads are popularity, not proof.
No numbers below are invented: each figure is quoted from the named source.

Tags used:
- **PROVEN (local)**: we ran it on this box on 2026-11-04 and measured the result (see `test-output/qa_report.json`).
- **PROVEN (source)**: the source publishes a measured or reproducible result.
- **UNTESTED**: a claim, a guide, or code we have read but not measured for ads.

Ad performance (CTR, CPL, hook rate) is UNTESTED for every technique in this file. Nothing
here has been run as a paid ad yet.

Repos were shallow-cloned to `research/_src/` (not committed). Licences checked: video-use MIT,
ffmpeg-skill MIT, claudeclip MIT, ad-video-skills MIT, AdAnvil MIT (wheel), Kinocut Apache-2.0,
remotion-dev/skills (Remotion licence: free for individuals and companies of up to 3 people).

---

## 1. Remotion Agent Skills
Source: https://github.com/remotion-dev/skills (commit c7cb2fd, 6.3k stars per GitHub API in the earlier research), install `npx skills add remotion-dev/skills`.

| Technique | Tag | Note |
|---|---|---|
| Every animated value is a pure function of `useCurrentFrame()`; no CSS transitions or timers | UNTESTED (source rule), PROVEN (local) that our overlays render deterministically | Two renders of the same timeline give identical overlay frames in our test (grain gate). |
| `premountFor` on Sequences so media is loaded before it shows | UNTESTED | Used in `render/src/Ad.tsx`. |
| Fonts loaded before render (no module-level delayRender) | UNTESTED | We load Montserrat from `public/fonts` with `@font-face` + `delayRender` inside the component. |
| `lut()` from `@remotion/effects/lut` takes .cube text, per layer | UNTESTED | We grade in ffmpeg instead (`lut3d`) so the LUT is applied to footage before Remotion and can never touch cream or graphics. Remotion per-layer LUT is the alternative. |
| Captions rules (word timing pages, `createTikTokStyleCaptions`) | UNTESTED | Our caption layer follows the Domin8te caption spec, not TikTok style. |
| Licence | Fact | Free for up to 3 people; Domin8te must re-check if the team grows. |

## 2. Pixel & Oak: timeline.json workflow
Source: https://pixelandoak.com/blog/remotion-agent-skills-claude-code/ (a studio's lessons from 5 films incl. a restaurant POS ad).

| Technique | Tag | Note |
|---|---|---|
| One `timeline.json` drives picture AND sound; move a cue once, both follow | UNTESTED (source anecdote) / PROVEN (local) for sync | Our `mix_audio.py` and Remotion both read `timeline.json`; the cut-on-beat gate measures it. |
| "Move the receipt print from frame 142 to 136" style instructions instead of vibes | UNTESTED | Built into the prompt template. |
| Stills/contact sheet review (10 to 20 stills at cues and cuts) before the full render | UNTESTED (source practice) | `contact_sheet.py --at-cues`. |
| Check loudness and true peak with ffmpeg before upload | PROVEN (local) | Gate Q2. |
| Pin Remotion package versions | UNTESTED | `render/package.json` pins 4.0.539 (the version already installed on the box). |

## 3. video-use (browser-use)
Source: https://github.com/browser-use/video-use (commit 43cfc56, MIT, 30.5k stars). Proof offered: README and stars only.

| Technique | Tag | Note |
|---|---|---|
| Word-level verbatim ASR, cached per source | UNTESTED | `transcribe.py` caches `words.json` by file hash. video-use uses ElevenLabs Scribe; we default to local faster-whisper if installed (no account calls). |
| Filler cut judged from a packed transcript, phrases split on silences of 0.5 s or more; silences of 400 ms or more are the cleanest cut points | UNTESTED | `filler_cut.py` marks fillers and gaps and writes a proposal Claude reviews. |
| Never cut inside a word; pad cuts 30 to 200 ms | UNTESTED | Enforced by `filler_cut.py` (default pad 0.05 s). |
| 30 ms audio fades at every segment boundary | PROVEN (local) no clicks in test (audio join check) | `grade_segments.py`. |
| Per-segment extract then lossless concat | UNTESTED for us | We extract graded segments, then concat. |
| Auto-grade from signalstats, bounded to +/-8% (contrast, gamma, saturation, no hue shift) | UNTESTED | Not used: Domin8te uses the fixed half grade v1 so every ad matches. Kept as an idea in open items. |
| 2-word UPPERCASE caption chunks (CHUNK_MAX_WORDS=3, CHUNK_MIN_S=0.35, CHUNK_PAUSE_S=0.3) | UNTESTED | Not used: Domin8te captions are sentence case, top-left, word-by-word. |
| Subtitles applied LAST, after overlays | UNTESTED | Captions are the top layer in `Ad.tsx`. |
| Parallel sub-agents build overlays; critic sub-agent self-check, max 3 passes | UNTESTED | Kept in SKILL.md as optional; our gates replace most of the critic's job. |
| Self-eval: look at frames around every cut (+/-1.5 s) and run ebur128 | UNTESTED (source) / PROVEN (local) as a gate | `contact_sheet.py --cuts`, Q2. |

## 4. ffmpeg-skill (kajisho5)
Source: https://github.com/kajisho5/ffmpeg-skill (commit 1ce2c18, MIT, 4.5k stars). 42 stdlib-only tools.

| Technique | Tag | Note |
|---|---|---|
| Fixed chain order: colour, cut, join, silence, fit, caption/overlay, sync, audio, loudness, export | UNTESTED | Our pipeline follows the same order (grade before cut is applied per segment). |
| Filler list `um, uh, erm, hmm, mm, mhm, er, ah`, trimmed 0.02 s either side; ambiguous words flagged not cut | UNTESTED | Same list and behaviour in `filler_cut.py`. |
| Untagged sources are assumed BT.709; BT.601 sources must be converted, not just retagged | UNTESTED (source rule), relevant: the Le Cookie mid is untagged and was made from a BT.601-decoded source | `ingest.py --assume-matrix`. |
| HDR to SDR tone map before any grade | UNTESTED | `ingest.py` tone-maps when it sees PQ/HLG transfer. |
| TikTok/Reels UI covers the bottom fifth and the right column | UNTESTED (guide) | Our safe zones are stricter (below). |

## 5. claudeclip
Source: https://github.com/gulkoa/claudeclip (commit 045b32b, MIT, 0 stars).

| Technique | Tag | Note |
|---|---|---|
| `sample_frames`: evenly spaced frames, timestamp burned in, tiled (default 12 frames, 4 columns, 320 px tiles) so Claude SEES the clip before editing | PROVEN (local) as a working tool | `contact_sheet.py` reimplements it (ffmpeg fps + drawtext + tile). Whether it improves edits is UNTESTED. |

## 6. ad-video-skills (iart-ai)
Source: https://github.com/iart-ai/ad-video-skills (commit 0de0f2a, MIT, 20 stars).

| Technique | Tag | Note |
|---|---|---|
| One variable per variant: hold layout, motion, colour, timing; swap only the hook (or the CTA) | UNTESTED | `variants.py` keeps one middle and swaps only the hook. |
| Hook and CTA message-matched in every row | UNTESTED | Prompt template asks for it. |
| Brand-lock theme object; dataset is a prop, nothing testable hardcoded | UNTESTED | `brand` block in timeline.json. |
| Safe-zone table (Meta 9:16 top ~14% / ~270 px, bottom ~20-35%, sides ~6%; 4:5 top ~5%, bottom ~10%) | UNTESTED (they say: verify in Ads Manager) | Our 9:16 zone is the stricter Domin8te one. |
| Design inside the centre so one master reframes to every ratio (re-centre, never letterbox) | UNTESTED | 4:5 is recomposed from the same timeline, not cropped from the 9:16 render. |

## 7. AdAnvil 0.4.0
Source: https://pypi.org/project/adanvil/ (MIT, alpha, about 60 downloads a week). Wheel kept in `_src/adanvil_pkg/` but NOT installed into the skill.

| Technique | Tag | Note |
|---|---|---|
| variants_build: hooks x bodies x CTAs (up to 24), render_batch, render_formats 9:16 / 4:5 / 1:1 | UNTESTED (claimed) | Same idea, narrower: hooks only, one shared middle. |
| storyboard_snap to beats | UNTESTED | `build_timeline.py` snaps cuts to downbeats. |
| qc_run, ad_score | UNTESTED | We do not "score" ads (Domin8te copy rule: nothing framed as a score). Our QA is pass/fail gates. |
| HDR to SDR, burned-text removal | UNTESTED | HDR handled in ingest; burned-text: we detect and avoid, we do not remove. |

## 8. Kinocut
Source: https://github.com/KyaniteLabs/kinocut (commit 22c3eeb, Apache-2.0, 243 stars in the earlier research; its own docs list 107 stars on 2026-08-12).

| Technique | Tag | Note |
|---|---|---|
| Quality checks run BEFORE a job may report success; a failed check persists a failed receipt | UNTESTED | `qa.py` exits non-zero on any FAIL; `run_test_ad.sh` stops. |
| Video Receipt: user intent, source sha256, tool calls, edits, guardrails fired, quality, review artifacts, final sha256 | UNTESTED | `qa.py` writes `receipt.json` with the same fields. |
| "A successful tool call does not establish that every quality property was evaluated"; technical vs semantic results kept separate | UNTESTED (principle) | Report separates AUTO gates from HUMAN checks. |

## 9. BEF (cafe and restaurant Reels)
Source: https://befagency.com/en/blog/reels-for-cafes-and-restaurants. Practitioner advice, no measured results.

All UNTESTED: open on movement (pour, cut, tear, steam, milk into a cup); a location line as a hook; soft side window light, no overhead tubes, no mixed light; record espresso machine / pan sound separately and mix it under the music; shoot vertically and keep the bottom and right edge clear, text near the centre; let shots run longer at start and end for cutting; cut mid-movement and on the beat; end on the location / CTA. These go into `references/shoot-guide.md` for the client.

## 10. Envato: short-form motion graphics
Source: https://elements.envato.com/learn/motion-graphics-for-short-form-video. Guide.

All UNTESTED: 1080x1920; centre-weighted, clear of the bottom quarter and the right rail; hook engineered for the first 1.5 s (scale-in type 90% to 100% with fast ease-out, colour wipe reveal, start mid-animation, never a static logo); captions for sound-off; block the frame once and reuse it across a series; QC on a real phone. The article's "roughly 51% jump" is about vertical HD uploads year over year, not ad results; do not quote it as performance.

## 11. DSNRY
Source: https://dsnry.com/motion-graphics-for-social-media-storytelling/. Opinion.

UNTESTED: restrained graphics (short title cards, ingredient callouts, timing text); match motion speed to the venue; the test "if you remove the graphics, does the footage still work?". We make this a HUMAN gate: `qa.py` renders a footage-only contact sheet (`no_graphics_sheet.png`) for Karan to judge.

---

## 12. Carried over from Domin8te's own rules (not external research)
- `avatar-motion-explainer` v2.2 (local skill): STEP 0 five questions, caption spec, safe zones, grain, beats.json, -14 LUFS, prompt template, banned copy. Status there: v2.2 beat and grain test PASSED on a 6 s synthetic clip (`/workspace/skill-v2.2-test/measure.txt`: cuts within 0.20 frames of downbeats; grain patch identical across scenes). That is PROVEN (local) for the mechanism only.
- `motion-graphics-skill` main: `COLOR.md` (BT.709 tv tags, G10 colour thresholds, "no LUT on the picture"), `SOUND.md` (sources, LICENCES.csv, licence check before render), `qa_gates.py` G1-G10.
- `/workspace/ads-post/AD_VIDEO_STANDARD.md`: delivery spec, end card crossfade, no reverb, brand-neutral "business", no end glitch.
- Half grade v1 (`/workspace/research/color-grade/`): its REPORT says it has NOT been tested on ads. Status: UNTESTED for performance; PROVEN (local) only that our pipeline applies it to footage and leaves graphics exact (gate Q7).

## 13. What we chose NOT to copy
- video-use's auto-grade and UPPERCASE 2-word captions (conflict with house style).
- AdAnvil's ad_score / any scoring (copy rule: nothing framed as a score or grade).
- Any burned-text removal or AI inpainting (risk of artefacts on food; untested).
