/**
 * Offline render of a studio session to a stereo buffer + WAV — for "export".
 * Reuses the native synth and the same timing the live scheduler uses (16th-note
 * steps with a swing push on odd 16ths), so the file matches what you hear.
 */
import { synthVoice, type Voice } from "./synth";
import { STEPS, audibleTracks, type ProjectState } from "./types";

export interface RenderResult {
  left: Float32Array;
  right: Float32Array;
  frames: number;
  sampleRate: number;
}

/** Render `bars` loops of the session to a normalized stereo buffer. */
export function renderProject(state: ProjectState, bars = 2, sampleRate = 48000): RenderResult {
  const spb = 60.0 / Math.max(20, state.bpm) / 4.0; // seconds per 16th step
  const totalSteps = bars * STEPS;
  const frames = Math.ceil((totalSteps * spb + 1.0) * sampleRate); // +1s tail
  const left = new Float32Array(frames);
  const right = new Float32Array(frames);

  const cache = new Map<Voice, Float32Array>();
  const voiceBuf = (v: Voice): Float32Array => {
    let b = cache.get(v);
    if (!b) { b = synthVoice(v, sampleRate); cache.set(v, b); }
    return b;
  };

  const audible = audibleTracks(state.tracks);
  for (let s = 0; s < totalSteps; s++) {
    const step = s % STEPS;
    const swing = step % 2 === 1 ? spb * state.swing : 0;
    const start = Math.round((s * spb + swing) * sampleRate);
    for (const track of audible) {
      if (!track.steps[step]) continue;
      const buf = voiceBuf(track.voice);
      const g = track.gain;
      const end = Math.min(start + buf.length, frames);
      for (let i = start, j = 0; i < end; i++, j++) {
        const v = buf[j] * g;
        left[i] += v;
        right[i] += v;
      }
    }
  }

  let peak = 0;
  for (let i = 0; i < frames; i++) peak = Math.max(peak, Math.abs(left[i]));
  if (peak > 1.0) {
    const inv = 1.0 / peak;
    for (let i = 0; i < frames; i++) { left[i] *= inv; right[i] *= inv; }
  }
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
