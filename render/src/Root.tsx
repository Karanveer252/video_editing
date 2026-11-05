import React from "react";
import { Composition } from "remotion";
import { Ad } from "./Ad";
import type { Props } from "./types";

const SIZES = { "9x16": [1080, 1920], "4x5": [1080, 1350] } as const;

export const Root: React.FC = () => (
  <>
    {(Object.keys(SIZES) as (keyof typeof SIZES)[]).map((r) => (
      <Composition
        key={r}
        id={`ad-${r}`}
        component={Ad as unknown as React.FC<Record<string, unknown>>}
        width={SIZES[r][0]}
        height={SIZES[r][1]}
        fps={30}
        durationInFrames={30}
        defaultProps={{ ratio: r, showGraphics: true } as unknown as Record<string, unknown>}
        calculateMetadata={({ props }) => {
          const p = props as unknown as Props;
          return { durationInFrames: p.tl.frames, fps: p.tl.fps, props: { ...p, ratio: r } as unknown as Record<string, unknown> };
        }}
      />
    ))}
  </>
);
