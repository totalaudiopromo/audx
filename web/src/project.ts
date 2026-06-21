/**
 * Compact, URL-safe encoding of a studio session — for shareable links and
 * localStorage autosave. No backend: the whole groove travels in the URL hash.
 */
import { SYNTH_VOICES, type Voice } from "./synth";
import { STEPS, type ProjectState, type Track } from "./types";

interface Wire {
  v: 1;
  b: number; // bpm
  s: number; // swing %, integer
  t: [number, number, number, number][]; // [voiceIdx, 16-bit stepMask, gain*100, flags]
}

const FLAG_MUTE = 1;
const FLAG_SOLO = 2;

function toWire(state: ProjectState): Wire {
  return {
    v: 1,
    b: Math.round(state.bpm),
    s: Math.round(state.swing * 100),
    t: state.tracks.map((tr) => {
      let mask = 0;
      for (let i = 0; i < STEPS; i++) if (tr.steps[i]) mask |= 1 << i;
      const flags = (tr.mute ? FLAG_MUTE : 0) | (tr.solo ? FLAG_SOLO : 0);
      return [SYNTH_VOICES.indexOf(tr.voice), mask, Math.round(tr.gain * 100), flags];
    }),
  };
}

let idCounter = 1;
function fromWire(w: Wire): ProjectState {
  const tracks: Track[] = w.t.map(([vi, mask, g100, flags]) => {
    const steps = new Array(STEPS).fill(false);
    for (let i = 0; i < STEPS; i++) steps[i] = (mask & (1 << i)) !== 0;
    const voice: Voice = SYNTH_VOICES[vi] ?? "kick";
    return {
      id: idCounter++,
      voice,
      steps,
      mute: (flags & FLAG_MUTE) !== 0,
      solo: (flags & FLAG_SOLO) !== 0,
      gain: g100 / 100,
    };
  });
  return { bpm: w.b, swing: w.s / 100, tracks };
}

/** base64url(JSON) — safe in a URL hash. */
export function encodeProject(state: ProjectState): string {
  const json = JSON.stringify(toWire(state));
  const b64 = typeof btoa === "function"
    ? btoa(json)
    : Buffer.from(json, "utf8").toString("base64");
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Inverse of encodeProject. Returns null on anything malformed. */
export function decodeProject(code: string): ProjectState | null {
  try {
    const b64 = code.replace(/-/g, "+").replace(/_/g, "/");
    const json = typeof atob === "function"
      ? atob(b64)
      : Buffer.from(b64, "base64").toString("utf8");
    const w = JSON.parse(json) as Wire;
    if (!w || w.v !== 1 || !Array.isArray(w.t)) return null;
    if (typeof w.b !== "number" || typeof w.s !== "number") return null;
    return fromWire(w);
  } catch {
    return null;
  }
}
