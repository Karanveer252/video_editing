export type Box = [number, number, number, number];
export interface Word { w: string; spoken: number; light: number; frame: number; hl: boolean; swipe?: [number, number] }
export interface CapLine { start: number; end: number; frame_start: number; frame_end: number; text: string; words: Word[] }
export interface Overlay {
  type: "dish_label" | "offer_card" | "end_card"; text?: string; sub?: string; headline?: string; url?: string;
  start: number; end: number; frame_start: number; frame_end: number; xfade_frames?: number;
}
export interface RatioBoxes {
  captions: Box[][];
  overlays: { type: string; box: Box; head_lines?: string[]; sub_lines?: string[]; logo?: Box; head?: Box; url?: Box }[];
}
export interface Segment { id: number; frame_start: number; frame_end: number; kind?: string; push_in?: number; push_origin?: [number, number] }
export interface Timeline {
  fps: number; duration: number; frames: number; hook_id: string;
  brand: { cream: string; ink: string; orange: string };
  footage: { file: string; end: number; xfade_s: number };
  segments: Segment[];
  captions: { lines: CapLine[] }; overlays: Overlay[];
  grain: { file: string; opacity: number; seed: number; scale: number };
  boxes: Record<string, RatioBoxes>;
}
export interface Props { tl: Timeline; ratio: "9x16" | "4x5"; showGraphics: boolean }
