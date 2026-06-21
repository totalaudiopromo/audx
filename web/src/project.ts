/**
 * Compact, URL-safe encoding of a studio session — for shareable links and
 * localStorage autosave. No backend: the whole groove travels in the URL hash.
 *
 * v2 adds per-step velocity (one /15 hex digit per step, 0 = off), multi-bar
 * patterns (step count is implicit in the hex length) and per-track pan.
 */
import { SYNTH_VOICES, type Voice } from "./synth";
import { BAR_STEPS, type ProjectState, type Track } from "./types";

interface WireTrack {
  i: number; // voice index
  s: string; // per-step velocity, one hex digit each (0..15) → vel = n/15
  g: number; // gain * 100
  p: number; // pan * 100
  f: number; // flags
}
interface Wire {
  v: 2;
  b: number; // bpm
  w: number; // swing %
  r: number; // bars
  t: WireTrack[];
}

const FLAG_MUTE = 1;
const FLAG_SOLO = 2;

const toHex = (vel: number): string => Math.max(0, Math.min(15, Math.round(vel * 15))).toString(16);

function toWire(state: ProjectState): Wire {
  return {
    v: 2,
    b: Math.round(state.bpm),
    w: Math.round(state.swing * 100),
    r: state.bars,
    t: state.tracks.map((tr) => ({
      i: SYNTH_VOICES.indexOf(tr.voice),
      s: tr.steps.map(toHex).join(""),
      g: Math.round(tr.gain * 100),
      p: Math.round(tr.pan * 100),
      f: (tr.mute ? FLAG_MUTE : 0) | (tr.solo ? FLAG_SOLO : 0),
    })),
  };
}

let idCounter = 1;
function fromWire(w: Wire): ProjectState {
  const bars = w.r >= 1 ? w.r : 1;
  const tracks: Track[] = w.t.map((t) => {
    const steps = t.s.split("").map((ch) => (parseInt(ch, 16) || 0) / 15);
    if (steps.length !== bars * BAR_STEPS) {
      // tolerate mismatches by clamping/padding to the declared length
      steps.length = bars * BAR_STEPS;
      for (let i = 0; i < steps.length; i++) steps[i] = steps[i] ?? 0;
    }
    return {
      id: idCounter++,
      voice: (SYNTH_VOICES[t.i] ?? "kick") as Voice,
      steps,
      mute: (t.f & FLAG_MUTE) !== 0,
      solo: (t.f & FLAG_SOLO) !== 0,
      gain: t.g / 100,
      pan: (t.p ?? 0) / 100,
    };
  });
  return { bpm: w.b, swing: w.w / 100, bars, tracks };
}

/** base64url(JSON) — safe in a URL hash. */
export function encodeProject(state: ProjectState): string {
  const json = JSON.stringify(toWire(state));
  const b64 = typeof btoa === "function" ? btoa(json) : Buffer.from(json, "utf8").toString("base64");
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Inverse of encodeProject. Returns null on anything malformed. */
export function decodeProject(code: string): ProjectState | null {
  try {
    const b64 = code.replace(/-/g, "+").replace(/_/g, "/");
    const json = typeof atob === "function" ? atob(b64) : Buffer.from(b64, "base64").toString("utf8");
    const w = JSON.parse(json) as Wire;
    if (!w || w.v !== 2 || !Array.isArray(w.t)) return null;
    if (typeof w.b !== "number" || typeof w.w !== "number") return null;
    return fromWire(w);
  } catch {
    return null;
  }
}
