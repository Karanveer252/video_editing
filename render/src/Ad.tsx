// Composition for one ratio. Everything is a pure function of the frame and timeline.json
// (Remotion best practice; no CSS transitions, no timers, no randomness at render time).
// Layer order (bottom to top): cream page -> graded footage panel -> overlays -> captions (LAST, video-use rule)
// -> end card (crossfades in over everything) -> paper grain (one texture, one opacity, every frame).
import React, { useEffect, useState } from "react";
import {
  AbsoluteFill, Easing, Img, OffthreadVideo, Sequence, continueRender, delayRender, interpolate,
  staticFile, useCurrentFrame,
} from "remotion";
import { loadFonts } from "./fonts";
import type { Box, CapLine, Props, RatioBoxes, Timeline } from "./types";

const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const PANEL = {
  "9x16": { x: 160, y: 640, w: 760, h: 1180, r: 36 },
  "4x5": { x: 270, y: 420, w: 540, h: 838, r: 30 },
} as const;
const CAP = { "9x16": { size: 66, lh: 1.2 }, "4x5": { size: 58, lh: 1.2 } } as const;
const CHIP = { "9x16": { size: 34, pad: 28 }, "4x5": { size: 30, pad: 24 } } as const;
const OFFER = { "9x16": { size: 54, sub: 30, pad: 40 }, "4x5": { size: 50, sub: 28, pad: 36 } } as const;
const END = { "9x16": { head: 108, url: 30 }, "4x5": { head: 104, url: 30 } } as const;

const Swipe: React.FC<{ box: Box; startF: number; durF: number; color: string }> = ({ box, startF, durF, color }) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [startF, startF + durF], [0, 1], { ...clamp, easing: easeOut });
  if (p <= 0) return null;
  const [x, y, w, h] = box;
  const hh = h * 0.75;
  return (
    <div style={{
      position: "absolute", left: x - 8, top: y + (h - hh) / 2 + 2, width: (w + 16) * p, height: hh,
      background: color, transform: "skewX(-2deg) rotate(-2deg)", transformOrigin: "left center",
      borderRadius: "10px 4px 12px 5px",
    }} />
  );
};

const CaptionLine: React.FC<{ line: CapLine; boxes: Box[]; tl: Timeline; ratio: Props["ratio"] }> = ({ line, boxes, tl, ratio }) => {
  const f = useCurrentFrame();
  const { size } = CAP[ratio];
  const fps = tl.fps;
  return (
    <>
      {line.words.map((w, i) => w.hl && w.swipe ? (
        <Swipe key={`s${i}`} box={boxes[i]} startF={Math.round(w.swipe[0] * fps)} durF={Math.round(w.swipe[1] * fps)} color={tl.brand.orange} />
      ) : null)}
      {line.words.map((w, i) => {
        const lit = interpolate(f, [w.frame - 2, w.frame], [0.28, 1], clamp) // full ink ON its light frame;
        const [x, y] = boxes[i];
        return (
          <span key={i} style={{
            position: "absolute", left: x, top: y, fontFamily: "Montserrat", fontWeight: 800, fontSize: size,
            lineHeight: `${CAP[ratio].lh}`, color: tl.brand.ink, opacity: lit, whiteSpace: "pre",
          }}>{w.w}</span>
        );
      })}
    </>
  );
};

const pop = (f: number, start: number) => {
  const p = interpolate(f, [start, start + 8], [0, 1], { ...clamp, easing: easeOut });
  return { opacity: p, transform: `scale(${0.9 + 0.1 * p})` }; // Envato: scale-in 90% -> 100%, fast ease-out
};

export const Ad: React.FC<Props> = ({ tl, ratio, showGraphics }) => {
  const f = useCurrentFrame();
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => { loadFonts().then(() => continueRender(handle)); }, [handle]);

  const B: RatioBoxes = tl.boxes[ratio];
  const P = PANEL[ratio];
  const end = tl.overlays.find((o) => o.type === "end_card")!;
  const endBox = B.overlays.find((o) => o.type === "end_card")!;
  const xf = end.xfade_frames ?? 12;
  const endOpacity = interpolate(f, [end.frame_start, end.frame_start + xf], [0, 1], clamp);
  const footFrames = Math.round((tl.footage.end + tl.footage.xfade_s) * tl.fps);
  const panelIn = interpolate(f, [0, 10], [0.965, 1], { ...clamp, easing: easeOut }); // start mid-animation
  // 3D by default: the phone panel settles from a gentle perspective tilt (starts mid-move, flat by frame 14)
  const tiltX = interpolate(f, [0, 14], [6, 0], { ...clamp, easing: easeOut });
  const tiltY = interpolate(f, [0, 14], [-5, 0], { ...clamp, easing: easeOut });
  // presenter opener: subtle push-in ON TOP of real motion (AD_VIDEO_STANDARD 2: about 3% about the face)
  const s0 = tl.segments?.[0];
  const isPresenter = s0?.kind === "presenter" && f < s0.frame_end;
  const push = isPresenter ? 1 + (s0.push_in ?? 0.03) * interpolate(f, [s0.frame_start, s0.frame_end - 1], [0, 1], clamp) : 1;
  const origin = s0?.push_origin ?? [0.5, 0.3];

  return (
    <AbsoluteFill style={{ backgroundColor: tl.brand.cream }}>
      {/* footage panel: graded file, the ONLY layer the grade touched */}
      <Sequence durationInFrames={footFrames} premountFor={30}>
        <div style={{
          position: "absolute", left: P.x, top: P.y, width: P.w, height: P.h, borderRadius: P.r, overflow: "hidden",
          boxShadow: "0 14px 28px rgba(31,33,40,.18)",
          transform: `perspective(1600px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) scale(${panelIn})`,
        }}>
          <OffthreadVideo src={staticFile(tl.footage.file)} muted style={{ width: "100%", height: "100%", objectFit: "cover",
            transform: `scale(${push})`, transformOrigin: `${origin[0] * 100}% ${origin[1] * 100}%` }} />
        </div>
      </Sequence>

      {showGraphics && tl.overlays.map((o, i) => {
        if (o.type === "end_card" || f < o.frame_start || f >= o.frame_end + 6) return null;
        const ob = B.overlays[i];
        const out = interpolate(f, [o.frame_end, o.frame_end + 6], [1, 0], clamp);
        const st = pop(f, o.frame_start);
        if (o.type === "dish_label") {
          const c = CHIP[ratio]; const [x, y, w, h] = ob.box;
          return (
            <div key={i} style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: h / 2,
              background: tl.brand.ink, color: tl.brand.cream, fontFamily: "Inter", fontWeight: 700, fontSize: c.size,
              display: "flex", alignItems: "center", justifyContent: "center", opacity: st.opacity * out,
              transform: st.transform, transformOrigin: "left center", whiteSpace: "nowrap" }}>{o.text}</div>
          );
        }
        if (o.type === "offer_card") {
          const c = OFFER[ratio]; const [x, y, w, h] = ob.box;
          return (
            <div key={i} style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: 22,
              background: tl.brand.cream, border: `3px solid ${tl.brand.ink}`, boxShadow: "0 14px 28px rgba(31,33,40,.18)",
              padding: c.pad, boxSizing: "border-box", opacity: st.opacity * out, transform: st.transform, transformOrigin: "left top" }}>
              {(ob.head_lines ?? []).map((l, j) => (
                <div key={j} style={{ fontFamily: "Montserrat", fontWeight: 800, fontSize: c.size, lineHeight: 1.15, color: tl.brand.ink, whiteSpace: "nowrap" }}>{l}</div>
              ))}
              <div style={{ height: 16 }} />
              {(ob.sub_lines ?? []).map((l, j) => (
                <div key={j} style={{ fontFamily: "Inter", fontWeight: 700, fontSize: c.sub, lineHeight: 1.3, color: tl.brand.ink, opacity: 0.75, whiteSpace: "nowrap" }}>{l}</div>
              ))}
            </div>
          );
        }
        return null;
      })}

      {showGraphics && tl.captions.lines.map((ln, i) =>
        f >= ln.frame_start && f < ln.frame_end ? <CaptionLine key={i} line={ln} boxes={B.captions[i]} tl={tl} ratio={ratio} /> : null
      )}

      {/* end card: crossfades in over everything (AD_VIDEO_STANDARD), then holds; footage gone after the fade */}
      {f >= end.frame_start && showGraphics && (
        <AbsoluteFill style={{ backgroundColor: tl.brand.cream, opacity: endOpacity }}>
          <Img src={staticFile("domin8te_logo_lockup.png")} style={{ position: "absolute", left: endBox.logo![0], top: endBox.logo![1], width: endBox.logo![2], height: endBox.logo![3] }} />
          {(endBox.head_lines ?? []).map((l, j) => {
            const hs = END[ratio].head; const y = endBox.head![1] + j * hs * 1.1;
            const isAccent = j === (endBox.head_lines!.length - 1);
            const w = (endBox as unknown as { head_widths: number[] }).head_widths[j];
            return (
              <React.Fragment key={j}>
                {isAccent && <Swipe box={[endBox.head![0], y, w, hs * 1.1]} startF={end.frame_start + xf} durF={6} color={tl.brand.orange} />}
                <div style={{ position: "absolute", left: endBox.head![0], top: y, fontFamily: "Montserrat", fontWeight: 800,
                  fontSize: hs, lineHeight: 1.1, color: tl.brand.ink, whiteSpace: "nowrap" }}>{l}</div>
              </React.Fragment>
            );
          })}
          <div style={{ position: "absolute", left: endBox.url![0], top: endBox.url![1], fontFamily: "Inter", fontWeight: 700,
            fontSize: END[ratio].url, lineHeight: 1.4, color: tl.brand.ink, opacity: 0.8, whiteSpace: "nowrap" }}>{end.url}</div>
        </AbsoluteFill>
      )}

      {/* paper grain: one file, same opacity/scale/seed on every frame and layer */}
      <Img src={staticFile(tl.grain.file)} style={{ position: "absolute", left: 0, top: 0, width: "100%", height: "100%",
        objectFit: "cover", objectPosition: "left top", opacity: tl.grain.opacity, pointerEvents: "none" }} />
    </AbsoluteFill>
  );
};
