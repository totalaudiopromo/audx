// audx promo palette — "electric neon": saturated glowing pads on pure black.
export const COLORS = {
  bg: "#08080a",
  surface: "#141418",
  bar: "#101014",
  text: "#f2f2f6",
  muted: "#8a8a98",
  // neon accents
  cyan: "#34f5ff",
  magenta: "#ff2fb0",
  lime: "#b6ff3d",
  amber: "#ffb02e",
  violet: "#b86bff",
  blue: "#5b8cff",
  orange: "#ff6a3d",
  // legacy aliases kept so older scenes still resolve
  sage: "#b6ff3d",
  pink: "#ff2fb0",
  red: "#ff5f56",
  border: "#2a2a33",
} as const;

export const MONO =
  "'JetBrains Mono', 'SF Mono', 'Fira Code', ui-monospace, monospace";
