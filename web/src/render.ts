/**
 * Offline render of a studio session to a stereo buffer + WAV — for "export".
 * Reuses the native synth and the same timing the live scheduler uses (16th-note
 * steps with a swing push on odd 16ths), including per-step velocity and pan, so
 * the file matches what you hear.
 */
import { synthVoice, type Voice } from "./synth";
import { BAR_STEPS, audibleTracks, panGains, type ProjectState, type Track } from "./types";
import { timeline, totalBars, type Song } from "./song";

export interface RenderResult {
  left: Float32Array;
  right: Float32Array;
  frames: number;
  sampleRate: number;
}

/** Resolves a track's loaded sample to stereo channels, or null for synth. */
export type SampleProvider = (ref: string) => { left: Float32Array; right: Float32Array } | null;

interface Timing {
  spb: number; // seconds per 16th step
  totalSteps: number;
  stepsPerLoop: number;
  frames: number;
}
function timing(state: ProjectState, loops: number, sampleRate: number): Timing {
  const spb = 60.0 / Math.max(20, state.bpm) / 4.0;
  const totalSteps = loops * state.bars * BAR_STEPS;
  return { spb, totalSteps, stepsPerLoop: state.bars * BAR_STEPS, frames: Math.ceil((totalSteps * spb + 1.0) * sampleRate) };
}

function makeVoiceCache(sampleRate: number): (v: Voice) => Float32Array {
  const cache = new Map<Voice, Float32Array>();
  return (v) => {
    let b = cache.get(v);
    if (!b) { b = synthVoice(v, sampleRate); cache.set(v, b); }
    return b;
  };
}

/** Add one track's hits into the given stereo buffers (no normalize). */
function placeTrack(
  track: Track, state: ProjectState, t: Timing, sampleRate: number,
  left: Float32Array, right: Float32Array,
  voiceBuf: (v: Voice) => Float32Array, sampleProvider?: SampleProvider,
): void {
  const [lg, rg] = panGains(track.pan);
  // a loaded sample wins; else the built-in synth voice (CLI precedence)
  const sample = track.sampleRef && sampleProvider ? sampleProvider(track.sampleRef) : null;
  for (let s = 0; s < t.totalSteps; s++) {
    const step = s % t.stepsPerLoop;
    const vel = track.steps[step] ?? 0;
    if (vel <= 0) continue;
    const swing = step % 2 === 1 ? t.spb * state.swing : 0;
    const start = Math.round((s * t.spb + swing) * sampleRate);
    const g = track.gain * vel;
    if (sample) {
      const end = Math.min(start + sample.left.length, t.frames);
      for (let i = start, j = 0; i < end; i++, j++) {
        left[i] += sample.left[j] * g * lg;
        right[i] += sample.right[j] * g * rg;
      }
    } else {
      const buf = voiceBuf(track.voice);
      const end = Math.min(start + buf.length, t.frames);
      for (let i = start, j = 0; i < end; i++, j++) {
        const v = buf[j] * g;
        left[i] += v * lg;
        right[i] += v * rg;
      }
    }
  }
}

function normalize(left: Float32Array, right: Float32Array, frames: number): void {
  let peak = 0;
  for (let i = 0; i < frames; i++) peak = Math.max(peak, Math.abs(left[i]), Math.abs(right[i]));
  if (peak > 1.0) {
    const inv = 1.0 / peak;
    for (let i = 0; i < frames; i++) { left[i] *= inv; right[i] *= inv; }
  }
}

/** Render `loops` full repeats of the session to a normalized stereo buffer. */
export function renderProject(
  state: ProjectState, loops = 2, sampleRate = 48000, sampleProvider?: SampleProvider
): RenderResult {
  const t = timing(state, loops, sampleRate);
  const left = new Float32Array(t.frames);
  const right = new Float32Array(t.frames);
  const voiceBuf = makeVoiceCache(sampleRate);
  for (const track of audibleTracks(state.tracks)) {
    placeTrack(track, state, t, sampleRate, left, right, voiceBuf, sampleProvider);
  }
  normalize(left, right, t.frames);
  return { left, right, frames: t.frames, sampleRate };
}

export interface Stem { name: string; wav: Uint8Array; }

/** Render each audible track to its own normalized WAV (like `audx render --stems`). */
export function renderStems(
  state: ProjectState, loops = 2, sampleRate = 48000, sampleProvider?: SampleProvider
): Stem[] {
  const t = timing(state, loops, sampleRate);
  const voiceBuf = makeVoiceCache(sampleRate);
  const safe = (s: string) => s.replace(/[^a-z0-9._-]+/gi, "_");
  return audibleTracks(state.tracks).map((track, i) => {
    const left = new Float32Array(t.frames);
    const right = new Float32Array(t.frames);
    placeTrack(track, state, t, sampleRate, left, right, voiceBuf, sampleProvider);
    normalize(left, right, t.frames);
    const label = track.sampleName ? track.sampleName.replace(/\.[^.]+$/, "") : track.voice;
    return {
      name: `${String(i + 1).padStart(2, "0")}-${safe(label)}.wav`,
      wav: toWav({ left, right, frames: t.frames, sampleRate }),
    };
  });
}

/** Render a whole Song (sections laid out along the timeline) to a stereo buffer. */
export function renderSong(song: Song, sampleRate = 48000, sampleProvider?: SampleProvider): RenderResult {
  const spb = 60.0 / Math.max(20, song.bpm) / 4.0;
  const total16 = totalBars(song) * BAR_STEPS;
  const frames = Math.max(1, Math.ceil((total16 * spb + 1.0) * sampleRate));
  const left = new Float32Array(frames);
  const right = new Float32Array(frames);
  const voiceBuf = makeVoiceCache(sampleRate);

  for (const { scene, startBar } of timeline(song)) {
    for (const track of audibleTracks(scene.tracks)) {
      const [lg, rg] = panGains(track.pan);
      const sample = track.sampleRef && sampleProvider ? sampleProvider(track.sampleRef) : null;
      const len = scene.bars * BAR_STEPS;
      for (let s = 0; s < len; s++) {
        const vel = track.steps[s] ?? 0;
        if (vel <= 0) continue;
        const swing = s % 2 === 1 ? spb * scene.swing : 0;
        const start = Math.round(((startBar * BAR_STEPS + s) * spb + swing) * sampleRate);
        const g = track.gain * vel;
        if (sample) {
          const end = Math.min(start + sample.left.length, frames);
          for (let i = start, j = 0; i < end; i++, j++) {
            left[i] += sample.left[j] * g * lg;
            right[i] += sample.right[j] * g * rg;
          }
        } else {
          const buf = voiceBuf(track.voice);
          const end = Math.min(start + buf.length, frames);
          for (let i = start, j = 0; i < end; i++, j++) {
            const v = buf[j] * g;
            left[i] += v * lg;
            right[i] += v * rg;
          }
        }
      }
    }
  }
  normalize(left, right, frames);
  return { left, right, frames, sampleRate };
}

/** Encode a stereo render as a 16-bit PCM WAV. */
export function toWav(r: RenderResult): Uint8Array {
  const { left, right, frames, sampleRate } = r;
  const bytes = frames * 2 * 2;
  const buf = new ArrayBuffer(44 + bytes);
  const view = new DataView(buf);
  const wr = (o: number, s: string) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  wr(0, "RIFF"); view.setUint32(4, 36 + bytes, true); wr(8, "WAVE");
  wr(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 2, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 4, true); view.setUint16(32, 4, true);
  view.setUint16(34, 16, true); wr(36, "data"); view.setUint32(40, bytes, true);
  let o = 44;
  for (let i = 0; i < frames; i++) {
    for (const ch of [left, right]) {
      const s = Math.max(-1, Math.min(1, ch[i]));
      view.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      o += 2;
    }
  }
  return new Uint8Array(buf);
}
