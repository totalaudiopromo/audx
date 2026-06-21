/** Shared types for the audx studio + its tools (project links, offline render). */
import type { Voice } from "./synth";

export const BAR_STEPS = 16;

/** Discrete step levels: off, ghost, normal, accent — chosen to round-trip
 *  exactly through the /15 hex encoding in project.ts. */
export const VEL_OFF = 0;
export const VEL_GHOST = 0.4;
export const VEL_NORMAL = 0.8;
export const VEL_ACCENT = 1.0;

export interface Track {
  id: number;
  voice: Voice;
  steps: number[]; // length = bars*16; 0 = off, else velocity in (0,1]
  mute: boolean;
  solo: boolean;
  gain: number; // 0..1.4
  pan: number; // -1..1
}

/** The serializable part of a session (no transport/runtime state). */
export interface ProjectState {
  bpm: number;
  swing: number; // 0..1
  bars: number; // 1, 2 or 4
  tracks: Track[];
}

/** Tracks that should sound, honouring solo then mute. */
export function audibleTracks(tracks: Track[]): Track[] {
  const soloed = tracks.filter((t) => t.solo);
  const pool = soloed.length ? soloed : tracks;
  return pool.filter((t) => !t.mute);
}

/** Equal-power pan gains for a mono source — matches StereoPannerNode. */
export function panGains(pan: number): [number, number] {
  const x = ((Math.max(-1, Math.min(1, pan)) + 1) / 2) * (Math.PI / 2);
  return [Math.cos(x), Math.sin(x)];
}

/** Resize a step array to `length`, preserving existing hits. */
export function resizeSteps(steps: number[], length: number): number[] {
  const out = new Array(length).fill(VEL_OFF);
  for (let i = 0; i < Math.min(length, steps.length); i++) out[i] = steps[i];
  return out;
}
