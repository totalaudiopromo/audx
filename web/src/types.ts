/** Shared types for the audx studio + its tools (project links, offline render). */
import type { Voice } from "./synth";

export const STEPS = 16;

export interface Track {
  id: number;
  voice: Voice;
  steps: boolean[];
  mute: boolean;
  solo: boolean;
  gain: number; // 0..1.4
}

/** The serializable part of a session (no transport/runtime state). */
export interface ProjectState {
  bpm: number;
  swing: number; // 0..1
  tracks: Track[];
}

/** Tracks that should sound, honouring solo then mute. */
export function audibleTracks(tracks: Track[]): Track[] {
  const soloed = tracks.filter((t) => t.solo);
  const pool = soloed.length ? soloed : tracks;
  return pool.filter((t) => !t.mute);
}
