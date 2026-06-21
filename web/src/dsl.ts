/**
 * audx pattern DSL — TypeScript port of src/audx/pattern.py.
 *
 * Faithful to the Python parser, including the awkward bits that golden-vector
 * tests pin down: `16x8` means 16 hits (the trailing number is ignored),
 * `swung_beat` uses banker's rounding, sample-name aliases (bd→kick, hh→hihat…),
 * and modifier clamping. Validated against fixtures emitted by the real parser
 * (scripts/gen_web_fixtures.py) — see web/tests/dsl.test.ts.
 */

export interface Step {
  sample: string;
  velocity: number;
  channel: number;
  beat: number;
  gainDb: number;
  pan: number;
  tuneSemitones: number;
}

export interface ParsedPattern {
  lengthBeats: number;
  swing: number;
  humanize: number;
  chance: number;
  gainDb: number;
  pan: number;
  tuneSemitones: number;
  steps: Step[];
}

const clamp = (x: number, lo: number, hi: number): number => Math.max(lo, Math.min(x, hi));

/** Python's round() — round half to even. */
export function pyRound(x: number): number {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1; // exactly .5 → nearest even
}

function makeStep(s: Partial<Step> & { sample: string; beat: number }): Step {
  return {
    sample: s.sample,
    velocity: clamp(s.velocity ?? 1.0, 0, 1),
    channel: Math.max(0, Math.trunc(s.channel ?? 0)),
    beat: s.beat,
    gainDb: s.gainDb ?? 0,
    pan: clamp(s.pan ?? 0, -1, 1),
    tuneSemitones: s.tuneSemitones ?? 0,
  };
}

/** Split on `sep` but ignore separators inside [], (), or quotes. */
function smartSplit(text: string, sep: string): string[] {
  const parts: string[] = [];
  let buf = "";
  let depth = 0;
  let quote: string | null = null;
  for (const ch of text) {
    if (quote) {
      buf += ch;
      if (ch === quote) quote = null;
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      buf += ch;
    } else if (ch === "(" || ch === "[") {
      depth += 1;
      buf += ch;
    } else if (ch === ")" || ch === "]") {
      depth = Math.max(0, depth - 1);
      buf += ch;
    } else if (ch === sep && depth === 0) {
      parts.push(buf);
      buf = "";
    } else {
      buf += ch;
    }
  }
  parts.push(buf);
  return parts;
}

function parsePercent(value: string | number | undefined, def: number): number {
  if (value === undefined || value === "") return def;
  if (typeof value === "string") {
    const text = value.trim();
    if (text.endsWith("%")) {
      const n = parseFloat(text.slice(0, -1));
      return Number.isNaN(n) ? def : clamp(n / 100, 0, 1);
    }
    const n = parseFloat(text);
    return Number.isNaN(n) ? def : clamp(n, 0, 1);
  }
  return clamp(value, 0, 1);
}

function parseDb(value: string | number | undefined): number {
  if (value === undefined) return 0;
  if (typeof value === "number") return value;
  const text = String(value).trim().toLowerCase().replace(/[db]+$/, "");
  const n = parseFloat(text);
  return Number.isNaN(n) ? 0 : n;
}

function parsePan(value: string | number | undefined): number {
  if (value === undefined || value === "") return 0;
  if (typeof value === "number") return clamp(value, -1, 1);
  const text = String(value).trim().toUpperCase();
  if (text === "C" || text === "CENTRE" || text === "CENTER") return 0;
  if (text.startsWith("L")) {
    const n = parseFloat(text.slice(1));
    return Number.isNaN(n) ? 0 : Math.max(-1, -n / 100);
  }
  if (text.startsWith("R")) {
    const n = parseFloat(text.slice(1));
    return Number.isNaN(n) ? 0 : Math.min(1, n / 100);
  }
  const n = parseFloat(text);
  return Number.isNaN(n) ? 0 : clamp(n, -1, 1);
}

function parseSemitones(value: string | number | undefined): number {
  if (value === undefined) return 0;
  if (typeof value === "number") return value;
  const text = String(value).trim().toLowerCase().replace(/[st]+$/, "");
  const n = parseFloat(text);
  return Number.isNaN(n) ? 0 : n;
}

const EUCLID_RE = /e\(\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(-?\d+))?\s*\)/i;

function euclideanGrid(pulses: number, steps: number, rotation = 0): number[] {
  if (pulses < 0 || steps <= 0) return new Array(Math.max(steps, 0)).fill(0);
  pulses = Math.min(pulses, steps);
  const grid = new Array(steps).fill(0);
  let bucket = 0;
  for (let i = 0; i < steps; i++) {
    bucket += pulses;
    if (bucket >= steps) {
      bucket -= steps;
      grid[i] = 1;
    }
  }
  if (rotation) {
    const r = ((rotation % steps) + steps) % steps;
    return grid.slice(steps - r).concat(grid.slice(0, steps - r));
  }
  return grid;
}

const SAMPLE_ALIASES: Record<string, string> = {
  bd: "kick",
  kick: "kick",
  sd: "snare",
  snare: "snare",
  hh: "hihat",
  hat: "hihat",
  hihat: "hihat",
  oh: "openhat",
  clap: "clap",
  rim: "rim",
  perc: "percussion",
};

const sampleName = (instr: string): string => SAMPLE_ALIASES[instr.toLowerCase()] ?? instr;

function beatsForSpec(spec: string, lengthBeats: number): number[] {
  spec = spec.trim();
  const lower = spec.toLowerCase();
  // 16x8 → number before the 'x' is the hit count; remainder ignored.
  if (lower.includes("x") && !spec.includes("/")) {
    const hitsStr = lower.split("x")[0];
    const hits = Math.max(1, parseInt(hitsStr || "1", 10));
    const width = lengthBeats / hits;
    return Array.from({ length: hits }, (_, i) => i * width);
  }
  if (spec.includes("/")) {
    const [nStr, mStr] = spec.split("/");
    const n = Math.max(1, parseInt(nStr || "1", 10));
    const m = Math.max(1, parseInt(mStr || "4", 10));
    if (n === m || m === 4) {
      const width = lengthBeats / n;
      return Array.from({ length: n }, (_, i) => i * width);
    }
    if (m === 8) {
      if (n === 2) return [1.0 * (lengthBeats / 4.0), 3.0 * (lengthBeats / 4.0)];
      const width = lengthBeats / m;
      return Array.from({ length: n }, (_, i) => (2 * i + 1) * width);
    }
    const width = lengthBeats / n;
    return Array.from({ length: n }, (_, i) => i * width);
  }
  return [0.0];
}

interface Ctx {
  velocity: number;
  channel: number;
  lengthBeats: number;
  name: string;
}

function explicitGrid(inner: string, ctx: Ctx, sampleHint?: string): Step[] {
  let cells = inner.split(/[\s,]+/).filter((c) => c);
  if (cells.length === 1 && cells[0].length > 1) cells = cells[0].split("");
  if (!cells.length) return [];
  const width = ctx.lengthBeats / cells.length;
  const sample = sampleName(sampleHint ?? ctx.name);
  const out: Step[] = [];
  cells.forEach((cell, i) => {
    const c = cell.trim().toLowerCase();
    if (c === "1" || c === "x" || c === "*") {
      out.push(makeStep({ sample, velocity: ctx.velocity, channel: ctx.channel, beat: i * width }));
    }
  });
  return out;
}

/**
 * Parse a single pattern DSL line into steps + pattern-level modifiers.
 * Mirrors Pattern.parse_dsl in src/audx/pattern.py.
 */
export function parsePattern(dsl: string, lengthBeats = 4.0, channel0 = 0): ParsedPattern {
  const empty: ParsedPattern = {
    lengthBeats,
    swing: 0,
    humanize: 0,
    chance: 1.0,
    gainDb: 0,
    pan: 0,
    tuneSemitones: 0,
    steps: [],
  };
  const trimmed = dsl.trim();
  if (!trimmed) return empty;

  const parts = smartSplit(trimmed, "|").map((p) => p.trim());
  const base = parts[0];
  const opts: Record<string, string> = {};
  for (const opt of parts.slice(1)) {
    if (!opt) continue;
    const idx = opt.search(/\s/);
    if (idx === -1) opts[opt.toLowerCase()] = "true";
    else opts[opt.slice(0, idx).toLowerCase()] = opt.slice(idx).trim();
  }

  const swing = parsePercent(opts.swing, 0);
  const humanize = parsePercent(opts.humanize, 0);
  const chance = parsePercent(opts.chance, 1.0);
  const gainDb = parseDb(opts.gain);
  const pan = parsePan(opts.pan);
  const tuneSemitones = parseSemitones(opts.tune);

  const rawVel = opts.vel ?? opts.velocity ?? 0.8;
  const velocity = parseFloat(String((rawVel as string | number) || 0.8));
  const rawCh = opts.ch ?? opts.channel ?? channel0;
  const channel = parseInt(String((rawCh as string | number) || 0), 10);

  const ctx: Ctx = { velocity, channel, lengthBeats, name: "t" };
  let steps: Step[];

  const gridMatch = base.match(/\[([^\[\]]+)\]/);
  if (base.startsWith("[") && base.endsWith("]")) {
    steps = explicitGrid(base.slice(1, -1), ctx);
  } else if (gridMatch) {
    const prefix = base.slice(0, gridMatch.index).trim();
    if (prefix) {
      const instr = prefix.split(/\s+/)[0];
      steps = explicitGrid(gridMatch[1], ctx, instr);
    } else {
      steps = explicitGrid(gridMatch[1], ctx);
    }
  } else if (EUCLID_RE.test(base)) {
    const m = base.match(EUCLID_RE)!;
    const pulses = Math.max(0, parseInt(m[1], 10));
    const stepsN = Math.max(1, parseInt(m[2], 10));
    const rotation = m[3] ? parseInt(m[3], 10) : 0;
    const prefix = base.slice(0, m.index).trim();
    const instr = prefix ? prefix.split(/\s+/)[0] : ctx.name;
    const sample = sampleName(instr);
    const grid = euclideanGrid(pulses, stepsN, rotation);
    const width = lengthBeats / stepsN;
    steps = [];
    grid.forEach((hit, i) => {
      if (hit) steps.push(makeStep({ sample, velocity, channel, beat: i * width }));
    });
  } else if (/^[\sxX.\-]+$/.test(base)) {
    const cleaned = base.replace(/ /g, "");
    const sample = sampleName(ctx.name);
    const width = lengthBeats / cleaned.length;
    steps = [];
    for (let i = 0; i < cleaned.length; i++) {
      if (cleaned[i].toLowerCase() === "x") {
        steps.push(makeStep({ sample, velocity, channel, beat: i * width }));
      }
    }
  } else {
    const idx = base.search(/\s/);
    const instr = idx === -1 ? base : base.slice(0, idx);
    const spec = idx === -1 ? "1/4" : base.slice(idx).trim();
    const sample = sampleName(instr);
    steps = beatsForSpec(spec, lengthBeats).map((beat) =>
      makeStep({ sample, velocity, channel, beat })
    );
  }

  for (const step of steps) {
    step.gainDb = gainDb;
    step.pan = pan;
    step.tuneSemitones = tuneSemitones;
  }

  return { lengthBeats, swing, humanize, chance, gainDb, pan, tuneSemitones, steps };
}

/** Real-timing swing offset — mirrors Pattern.swung_beat (banker's rounding). */
export function swungBeat(beat: number, swing: number, lengthBeats = 4.0): number {
  if (swing <= 0) return beat % lengthBeats;
  const sixteenth = lengthBeats / 16.0;
  const index = pyRound(beat / sixteenth);
  if (index % 2 === 1) beat += sixteenth * swing;
  return beat % lengthBeats;
}
