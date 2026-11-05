import { staticFile } from "remotion";

// Fonts load inside the component tree (Pixel & Oak lesson: no module-level delayRender at import time).
let loaded: Promise<void> | null = null;
export const loadFonts = (): Promise<void> => {
  if (loaded) return loaded;
  const faces = [
    new FontFace("Montserrat", `url(${staticFile("fonts/Montserrat-Variable.ttf")})`, { weight: "100 900" }),
    new FontFace("Inter", `url(${staticFile("fonts/Inter-Variable.ttf")})`, { weight: "100 900" }),
  ];
  loaded = Promise.all(faces.map((f) => f.load().then((ff) => { document.fonts.add(ff); }))).then(() => undefined);
  return loaded;
};
