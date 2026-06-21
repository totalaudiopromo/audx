// audx promo palette — near-monochrome, one accent. No gradients, no glows.
// Inspired by Swiss/Teenage-Engineering restraint: warm off-white on true black,
// a single amber accent for "now" (maximum contrast, minimum palette).
export const COLORS = {
  bg: "#0a0a0a",
  surface: "#101010",
  ink: "#ececea", // warm off-white — text + active cells
  inkDim: "#9a9a95", // secondary labels
  grey: "#56554f", // tertiary
  line: "#23231f", // hairlines, inactive cell outlines
  accent: "#d79a4e", // the single accent (warm amber) — used sparingly
} as const;

export const MONO =
  "'JetBrains Mono', 'SF Mono', 'Fira Code', ui-monospace, monospace";
