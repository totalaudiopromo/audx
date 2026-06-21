/**
 * audx synth voices — TypeScript port of src/audx/synth.py.
 *
 * 20 procedural drum/percussion/melodic voices, pure DSP, mono one-shots in
 * [-1, 1]. The 11 noiseless voices (sub, rim, tom, cowbell, perc, bass, pluck,
 * stab, keys, saw, sine) are ported to match numpy sample-for-sample; the 9 noise
 * voices use a local PRNG (numpy's PCG64 can't be reproduced in JS), so they match
 * the Python ones structurally — same length, normalized peak and envelope shape.
 * Verified against golden vectors from the real synth — see web/tests/synth.test.ts.
 */

import { pyRound } from "./dsl";

export const SYNTH_VOICES = [
  "kick", "sub", "snare", "clap", "snap", "hh", "oh", "rim", "tom", "cowbell",
  "perc", "ride", "crash", "shaker", "bass", "pluck", "stab", "keys", "saw", "sine",
] as const;
export type Voice = (typeof SYNTH_VOICES)[number];

const VOICE_ALIASES: Record<string, Voice> = {
  bd: "kick", bassdrum: "kick", "808": "sub", sd: "snare", sn: "snare", cp: "clap",
  clp: "clap", ch: "hh", hat: "hh", hats: "hh", hihat: "hh", closedhat: "hh",
  openhat: "oh", ohh: "oh", rs: "rim", rimshot: "rim", clave: "rim", lt: "tom",
  mt: "tom", ht: "tom", floortom: "tom", cb: "cowbell", bell: "cowbell", cy: "crash",
  cym: "crash", shk: "shaker", maraca: "shaker", rd: "ride", ep: "keys",
  percussion: "perc",
};

export function canonicalVoice(name: string): Voice | null {
  const key = name.trim().toLowerCase();
  if ((SYNTH_VOICES as readonly string[]).includes(key)) return key as Voice;
  return VOICE_ALIASES[key] ?? null;
}
export const isSynthVoice = (name: string): boolean => canonicalVoice(name) !== null;

// ── deterministic PRNG for noise voices (mulberry32) ────────────────────────────
type Rng = () => number; // uniform in [-1, 1]
function makeRng(seed = 0): Rng {
  let a = (seed >>> 0) || 0x9e3779b9;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((((t ^ (t >>> 14)) >>> 0) / 4294967296) * 2 - 1);
  };
}

// ── helpers (mirror synth.py) ───────────────────────────────────────────────────
const PI2 = 2 * Math.PI;

function tAxis(seconds: number, sr: number): Float64Array {
  const n = Math.max(1, Math.floor(seconds * sr));
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) out[i] = (i * seconds) / n;
  return out;
}

/** np.linspace(0, 1, a) with endpoint=True. */
function linspaceInclusive(a: number): Float64Array {
  const out = new Float64Array(a);
  if (a === 1) { out[0] = 0; return out; }
  for (let i = 0; i < a; i++) out[i] = i / (a - 1);
  return out;
}

function expEnv(n: number, decay: number, sr: number, attack = 0.002): Float64Array {
  const env = new Float64Array(n);
  const k = Math.max(1.0, decay * sr);
  for (let i = 0; i < n; i++) env[i] = Math.exp(-i / k);
  const a = Math.max(1, Math.floor(attack * sr));
  if (a < n) {
    const ramp = linspaceInclusive(a);
    for (let i = 0; i < a; i++) env[i] *= ramp[i];
  }
  return env;
}

function highpass(x: Float64Array, amount = 0.92): Float64Array {
  const y = new Float64Array(x.length);
  y[0] = x[0];
  let prevX = x[0];
  let prevY = x[0];
  for (let i = 1; i < x.length; i++) {
    prevY = amount * (prevY + x[i] - prevX);
    prevX = x[i];
    y[i] = prevY;
  }
  return y;
}

/** np.convolve(x, ones(w)/w, mode='same'). */
function lowpass(x: Float64Array, window = 8): Float64Array {
  const n = x.length;
  if (window <= 1 || n <= window) return x;
  const full = new Float64Array(n + window - 1);
  const inv = 1.0 / window;
  for (let i = 0; i < n; i++) {
    const xi = x[i] * inv;
    for (let j = 0; j < window; j++) full[i + j] += xi;
  }
  const start = Math.floor((window - 1) / 2);
  return full.slice(start, start + n);
}

function noise(n: number, rng: Rng): Float64Array {
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) out[i] = rng();
  return out;
}

function normalize(x: Float64Array, peak = 0.98): Float64Array {
  let m = 0;
  for (let i = 0; i < x.length; i++) m = Math.max(m, Math.abs(x[i]));
  if (m > 1e-9) {
    const g = (1 / m) * peak;
    for (let i = 0; i < x.length; i++) x[i] *= g;
  }
  return x;
}

function blSaw(freq: number, n: number, sr: number): Float64Array {
  const out = new Float64Array(n);
  if (freq <= 0) return out;
  const nyquist = sr / 2.0;
  let maxK = Math.max(1, Math.floor(nyquist / freq));
  maxK = Math.min(maxK, 64);
  for (let k = 1; k <= maxK; k++) {
    const w = (PI2 * freq * k) / sr;
    for (let i = 0; i < n; i++) out[i] += Math.sin(w * i) / k;
  }
  const g = 2.0 / Math.PI;
  for (let i = 0; i < n; i++) out[i] *= g;
  return out;
}

function blSine(freq: number, n: number, sr: number): Float64Array {
  const out = new Float64Array(n);
  const w = (PI2 * freq) / sr;
  for (let i = 0; i < n; i++) out[i] = Math.sin(w * i);
  return out;
}

const cumPhase = (pitch: Float64Array, sr: number): Float64Array => {
  const phase = new Float64Array(pitch.length);
  let acc = 0;
  for (let i = 0; i < pitch.length; i++) {
    acc += pitch[i];
    phase[i] = (PI2 * acc) / sr;
  }
  return phase;
};

const C2 = 65.41;
const C3 = 130.81;

// ── voices ──────────────────────────────────────────────────────────────────────
type Renderer = (sr: number, rng: Rng) => Float64Array;

const renderers: Record<Voice, Renderer> = {
  kick(sr, rng) {
    const t = tAxis(0.34, sr); const n = t.length;
    const pitch = new Float64Array(n);
    for (let i = 0; i < n; i++) pitch[i] = 48 + (115 - 48) * Math.exp(-t[i] / 0.035);
    const phase = cumPhase(pitch, sr);
    const env = expEnv(n, 0.16, sr);
    const click = noise(n, rng); const cenv = expEnv(n, 0.004, sr, 0.0005);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = Math.sin(phase[i]) * env[i] + click[i] * cenv[i] * 0.4;
    return normalize(out);
  },
  sub(sr) {
    const t = tAxis(0.8, sr); const n = t.length;
    const pitch = new Float64Array(n);
    for (let i = 0; i < n; i++) pitch[i] = 44 + (70 - 44) * Math.exp(-t[i] / 0.06);
    const phase = cumPhase(pitch, sr);
    const env = expEnv(n, 0.34, sr);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = Math.tanh(Math.sin(phase[i]) * 1.4) * env[i];
    return normalize(out);
  },
  snare(sr, rng) {
    const t = tAxis(0.22, sr); const n = t.length;
    const te = expEnv(n, 0.09, sr); const ne = expEnv(n, 0.11, sr);
    const hp = highpass(noise(n, rng), 0.86);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const tone = (Math.sin(PI2 * 185 * t[i]) + 0.6 * Math.sin(PI2 * 330 * t[i])) * te[i];
      out[i] = 0.55 * tone + 0.9 * (hp[i] * ne[i]);
    }
    return normalize(out);
  },
  clap(sr, rng) {
    const n = Math.floor(0.26 * sr);
    const out = new Float64Array(n);
    const base = highpass(noise(n, rng), 0.8);
    for (const [offset, decay] of [[0.0, 0.012], [0.009, 0.012], [0.018, 0.013], [0.028, 0.07]]) {
      const start = Math.floor(offset * sr);
      if (start >= n) continue;
      const env = expEnv(n - start, decay, sr, 0.0003);
      for (let i = 0; i < n - start; i++) out[start + i] += base[i] * env[i];
    }
    return normalize(out);
  },
  snap(sr, rng) {
    const t = tAxis(0.14, sr); const n = t.length;
    const ne = expEnv(n, 0.03, sr, 0.0003); const tnE = expEnv(n, 0.01, sr);
    const hp = highpass(noise(n, rng), 0.9);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = hp[i] * ne[i] + Math.sin(PI2 * 1600 * t[i]) * tnE[i] * 0.3;
    return normalize(out);
  },
  hh(sr, rng) {
    const n = Math.floor(0.05 * sr);
    const env = expEnv(n, 0.014, sr, 0.0002);
    const hp = highpass(noise(n, rng), 0.95);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = hp[i] * env[i];
    return normalize(out);
  },
  oh(sr, rng) {
    const n = Math.floor(0.35 * sr);
    const env = expEnv(n, 0.16, sr, 0.0002);
    const hp = highpass(noise(n, rng), 0.95);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = hp[i] * env[i];
    return normalize(out);
  },
  rim(sr) {
    const t = tAxis(0.06, sr); const n = t.length;
    const env = expEnv(n, 0.012, sr, 0.0002);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++)
      out[i] = (Math.sin(PI2 * 1700 * t[i]) + 0.5 * Math.sin(PI2 * 2600 * t[i])) * env[i];
    return normalize(out);
  },
  tom(sr) {
    const t = tAxis(0.3, sr); const n = t.length;
    const pitch = new Float64Array(n);
    for (let i = 0; i < n; i++) pitch[i] = 110 + (180 - 110) * Math.exp(-t[i] / 0.08);
    const phase = cumPhase(pitch, sr);
    const env = expEnv(n, 0.14, sr);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = Math.sin(phase[i]) * env[i];
    return normalize(out);
  },
  cowbell(sr) {
    const t = tAxis(0.3, sr); const n = t.length;
    const mix = new Float64Array(n);
    for (let i = 0; i < n; i++)
      mix[i] = 0.5 * (Math.sign(Math.sin(PI2 * 540 * t[i])) + Math.sign(Math.sin(PI2 * 800 * t[i])));
    const tone = lowpass(mix, 6);
    const env = expEnv(n, 0.12, sr, 0.001);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = tone[i] * env[i];
    return normalize(out);
  },
  perc(sr) {
    const t = tAxis(0.16, sr); const n = t.length;
    const env = expEnv(n, 0.06, sr, 0.001);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const mod = Math.sin(PI2 * 430 * t[i]) * 4.0;
      out[i] = Math.sin(PI2 * 720 * t[i] + mod) * env[i];
    }
    return normalize(out);
  },
  ride(sr, rng) {
    const t = tAxis(0.5, sr); const n = t.length;
    const env = expEnv(n, 0.22, sr, 0.0005);
    const hp = highpass(noise(n, rng), 0.95);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      let p = 0;
      for (const f of [520, 1370, 2050, 3400]) p += Math.sin(PI2 * f * t[i]);
      out[i] = (p / 4 + hp[i] * 0.4) * env[i];
    }
    return normalize(out);
  },
  crash(sr, rng) {
    const n = Math.floor(0.9 * sr);
    const env = expEnv(n, 0.4, sr, 0.001);
    const hp = highpass(noise(n, rng), 0.97);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = hp[i] * env[i];
    return normalize(out);
  },
  shaker(sr, rng) {
    const n = Math.floor(0.1 * sr);
    const env = expEnv(n, 0.035, sr, 0.006);
    const hp = highpass(noise(n, rng), 0.93);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = hp[i] * env[i];
    return normalize(out);
  },
  bass(sr) {
    const n = Math.floor(0.5 * sr);
    const saw = blSaw(C2, n, sr); const sub = blSine(C2 / 2.0, n, sr);
    const tone = new Float64Array(n);
    for (let i = 0; i < n; i++) tone[i] = 0.7 * saw[i] + 0.6 * sub[i];
    const lp = lowpass(tone, 8);
    const env = expEnv(n, 0.22, sr, 0.004);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = Math.tanh(lp[i] * 1.2) * env[i];
    return normalize(out);
  },
  pluck(sr) {
    const n = Math.floor(0.3 * sr);
    const saw = blSaw(C3, n, sr);
    const bright = lowpass(saw, 3); const dark = lowpass(saw, 24);
    const env = expEnv(n, 0.09, sr, 0.002);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const m = n === 1 ? 0 : i / (n - 1);
      out[i] = ((1 - m) * bright[i] + m * dark[i]) * env[i];
    }
    return normalize(out);
  },
  stab(sr) {
    const n = Math.floor(0.4 * sr);
    const chord = new Float64Array(n);
    for (const st of [0, 3, 7]) {
      const f = C3 * 2.0 ** (st / 12.0);
      const a = blSaw(f * 0.997, n, sr); const b = blSaw(f * 1.003, n, sr);
      for (let i = 0; i < n; i++) chord[i] += a[i] + b[i];
    }
    const lp = lowpass(chord, 4);
    const env = expEnv(n, 0.14, sr, 0.004);
    for (let i = 0; i < n; i++) lp[i] *= env[i];
    return normalize(lp);
  },
  keys(sr) {
    const n = Math.floor(0.6 * sr);
    const f = C3;
    const h1 = blSine(f, n, sr); const h2 = blSine(f * 2, n, sr); const h3 = blSine(f * 3, n, sr);
    const tr = blSine(f * 4, n, sr); const trE = expEnv(n, 0.04, sr, 0.0);
    const env = expEnv(n, 0.28, sr, 0.012);
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const tone = h1[i] + 0.5 * h2[i] + 0.18 * h3[i];
      out[i] = tone * env[i] + tr[i] * trE[i] * 0.25 * env[i];
    }
    return normalize(out);
  },
  saw(sr) {
    const n = Math.floor(0.5 * sr);
    const tone = blSaw(C3, n, sr); const env = expEnv(n, 0.3, sr, 0.006);
    for (let i = 0; i < n; i++) tone[i] *= env[i];
    return normalize(tone);
  },
  sine(sr) {
    const n = Math.floor(0.5 * sr);
    const tone = blSine(C3, n, sr); const env = expEnv(n, 0.3, sr, 0.006);
    for (let i = 0; i < n; i++) tone[i] *= env[i];
    return normalize(tone);
  },
};

/** np.interp(newX, oldX, x) with the linspace(endpoint=False) axes from synth.py. */
function resampleLinear(x: Float64Array, ratio: number): Float64Array {
  if (Math.abs(ratio - 1.0) < 1e-6 || x.length < 2) return x;
  const n = x.length;
  const target = Math.max(1, pyRound(n * ratio));
  const out = new Float64Array(target);
  // oldX[i] = i/n ; newX[j] = j/target ; interp with clamping at the ends.
  for (let j = 0; j < target; j++) {
    const pos = (j / target) * n; // position in old index space
    if (pos <= 0) { out[j] = x[0]; continue; }
    if (pos >= n - 1) { out[j] = x[n - 1]; continue; }
    const i0 = Math.floor(pos); const frac = pos - i0;
    out[j] = x[i0] * (1 - frac) + x[i0 + 1] * frac;
  }
  return out;
}

export interface SynthOpts {
  velocity?: number;
  tuneSemitones?: number;
  seed?: number;
}

/** Render a built-in voice to a mono Float32Array one-shot. Mirrors synth_voice(). */
export function synthVoice(name: string, sampleRate = 44100, opts: SynthOpts = {}): Float32Array {
  const voice = canonicalVoice(name);
  if (!voice) throw new Error(`unknown synth voice: ${name}`);
  const rng = makeRng(opts.seed ?? 0);
  let buf = renderers[voice](sampleRate, rng);
  const tune = opts.tuneSemitones ?? 0;
  if (tune) buf = resampleLinear(buf, 2.0 ** (-tune / 12.0));
  const vel = Math.max(0, Math.min(opts.velocity ?? 1.0, 1.0));
  const out = new Float32Array(buf.length);
  for (let i = 0; i < buf.length; i++) out[i] = buf[i] * vel;
  return out;
}
