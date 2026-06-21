/**
 * Songs: arrange studio grids ("scenes") into a sequence, mirroring the CLI's
 * Section/Song model (src/audx/arrangement.py). Imports/exports the CLI's Song JSON
 * ({ bpm, sections, sequence }) so a song built here plays with `audx song render`
 * and vice-versa — the DSL bridge reuses the golden-vector-tested parser in dsl.ts.
 *
 * Note: the CLI's explicit-grid DSL is binary per step, so per-step accents don't
 * survive a CLI round-trip; multi-bar scenes export as 1-bar patterns tiled by the
 * section's bar count (matching the CLI's "pattern repeats across the section").
 */
import { parsePattern } from "./dsl";
import { canonicalVoice, type Voice } from "./synth";
import { BAR_STEPS, VEL_ACCENT, VEL_GHOST, VEL_NORMAL, type Track } from "./types";

export interface Scene {
  name: string;
  tracks: Track[];
  bars: number;
  swing: number;
}
export interface Song {
  bpm: number;
  scenes: Scene[];
  sequence: string[]; // scene names, in order (repeats allowed)
}

export function timeline(song: Song): { scene: Scene; startBar: number }[] {
  const byName = new Map(song.scenes.map((s) => [s.name, s]));
  const out: { scene: Scene; startBar: number }[] = [];
  let cursor = 0;
  for (const name of song.sequence) {
    const scene = byName.get(name);
    if (!scene) continue;
    out.push({ scene, startBar: cursor });
    cursor += scene.bars;
  }
  return out;
}

export const totalBars = (song: Song): number =>
  song.sequence.reduce((n, name) => n + (song.scenes.find((s) => s.name === name)?.bars ?? 0), 0);

/** Flatten a song into one entry per global 16th-step: which scene is playing and
 *  the local step within it. Length = totalBars*16. Drives live song playback. */
export function songStepPlan(song: Song): { scene: Scene; localStep: number }[] {
  const plan: { scene: Scene; localStep: number }[] = [];
  for (const { scene } of timeline(song)) {
    const steps = scene.bars * BAR_STEPS;
    for (let s = 0; s < steps; s++) plan.push({ scene, localStep: s });
  }
  return plan;
}

// ── DSL bridge ────────────────────────────────────────────────────────────────
const ON_LEVELS = [VEL_GHOST, VEL_NORMAL, VEL_ACCENT];
const nearestLevel = (v: number): number =>
  v <= 0 ? 0 : ON_LEVELS.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));

/** One track → an audx DSL pattern line (binary grid + pan; accents are lossy). */
export function trackToDSL(track: Track): string {
  const grid = track.steps.map((s) => (s > 0 ? "1" : "0")).join("");
  const pan = Math.abs(track.pan) > 0.01
    ? ` | pan ${track.pan < 0 ? "L" : "R"}${Math.round(Math.abs(track.pan) * 100)}`
    : "";
  return `${track.voice} [${grid}]${pan}`;
}

const firstToken = (dsl: string): string => dsl.trim().split(/[\s[|]/)[0];

/** A DSL pattern → a studio track, tiled across `bars` (CLI repetition semantics). */
export function dslToTrack(dsl: string, bars: number, id: number): Track {
  const p = parsePattern(dsl);
  const bar = new Array(BAR_STEPS).fill(0);
  for (const step of p.steps) {
    const idx = Math.round(step.beat / (4 / BAR_STEPS));
    if (idx >= 0 && idx < BAR_STEPS) bar[idx] = nearestLevel(step.velocity);
  }
  const steps: number[] = [];
  for (let b = 0; b < bars; b++) steps.push(...bar);
  const voice: Voice =
    canonicalVoice(p.steps[0]?.sample ?? "") ?? canonicalVoice(firstToken(dsl)) ?? "kick";
  return { id, voice, steps, mute: false, solo: false, gain: 0.9, pan: p.pan };
}

// ── CLI Song JSON interop ───────────────────────────────────────────────────────
export interface CliSong {
  bpm: number;
  sections: Record<string, { patterns: string[]; bars: number }>;
  sequence: string[];
}

export function songToCli(song: Song): CliSong {
  const sections: CliSong["sections"] = {};
  for (const scene of song.scenes) {
    sections[scene.name] = { patterns: scene.tracks.map(trackToDSL), bars: scene.bars };
  }
  return { bpm: song.bpm, sections, sequence: song.sequence };
}

let importId = 1;
export function cliToSong(cli: CliSong): Song {
  const scenes: Scene[] = Object.entries(cli.sections).map(([name, sec]) => {
    const bars = Math.max(1, sec.bars | 0);
    return {
      name,
      bars,
      swing: 0,
      tracks: (sec.patterns ?? []).map((dsl) => dslToTrack(dsl, bars, importId++)),
    };
  });
  return { bpm: cli.bpm, scenes, sequence: cli.sequence ?? [] };
}
