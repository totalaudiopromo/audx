import { describe, expect, it } from "vitest";
import { renderProject, toWav } from "../src/render";
import { VEL_NORMAL, type ProjectState, type Track } from "../src/types";

const SR = 48000;

function track(voice: string, hits: number[], opts: Partial<Track> = {}, len = 16): Track {
  const steps = new Array(len).fill(0);
  for (const h of hits) steps[h] = VEL_NORMAL;
  return { id: 1, voice: voice as never, steps, mute: false, solo: false, gain: 1.0, pan: 0, ...opts };
}
const peakOf = (a: Float32Array) => a.reduce((m, x) => Math.max(m, Math.abs(x)), 0);

describe("offline render", () => {
  it("produces a non-silent stereo buffer of the right length", () => {
    const state: ProjectState = { bpm: 120, swing: 0, bars: 1, tracks: [track("kick", [0, 4, 8, 12])] };
    const r = renderProject(state, 1, SR); // 16 steps * 0.125s = 2s + 1s tail
    expect(Math.abs(r.frames - 3 * SR)).toBeLessThan(SR * 0.05);
    expect(peakOf(r.left)).toBeGreaterThan(0);
    expect(peakOf(r.left)).toBeLessThanOrEqual(1.0 + 1e-6);
  });

  it("renders multi-bar patterns at the right length", () => {
    const two: ProjectState = { bpm: 120, swing: 0, bars: 2, tracks: [track("kick", [0], {}, 32)] };
    const r = renderProject(two, 1, SR); // 32 steps * 0.125s = 4s + 1s tail
    expect(Math.abs(r.frames - 5 * SR)).toBeLessThan(SR * 0.05);
  });

  it("pans hard left → right channel stays near silent", () => {
    const state: ProjectState = { bpm: 120, swing: 0, bars: 1, tracks: [track("kick", [0], { pan: -1 })] };
    const r = renderProject(state, 1, SR);
    expect(peakOf(r.left)).toBeGreaterThan(0.1);
    expect(peakOf(r.right)).toBeLessThan(1e-3);
  });

  it("lower step velocity → lower peak", () => {
    const loud: ProjectState = { bpm: 120, swing: 0, bars: 1, tracks: [track("sine", [0], { gain: 0.5 })] };
    const soft: ProjectState = { bpm: 120, swing: 0, bars: 1, tracks: [{ ...track("sine", [0], { gain: 0.5 }), steps: ((): number[] => { const s = new Array(16).fill(0); s[0] = 0.4; return s; })() }] };
    expect(peakOf(renderProject(soft, 1, SR).left)).toBeLessThan(peakOf(renderProject(loud, 1, SR).left));
  });

  it("honours mute/solo", () => {
    const state: ProjectState = {
      bpm: 120, swing: 0, bars: 1,
      tracks: [{ ...track("kick", [0]), solo: true }, track("snare", [0])],
    };
    expect(peakOf(renderProject(state, 1, SR).left)).toBeGreaterThan(0);
  });

  it("writes a valid 16-bit stereo WAV header", () => {
    const state: ProjectState = { bpm: 120, swing: 0, bars: 1, tracks: [track("kick", [0])] };
    const wav = toWav(renderProject(state, 1, SR));
    const txt = (o: number, n: number) => String.fromCharCode(...wav.slice(o, o + n));
    expect(txt(0, 4)).toBe("RIFF");
    expect(txt(8, 4)).toBe("WAVE");
    const dv = new DataView(wav.buffer);
    expect(dv.getUint16(22, true)).toBe(2);
    expect(dv.getUint16(34, true)).toBe(16);
    expect(wav.length).toBe(44 + dv.getUint32(40, true));
  });
});
