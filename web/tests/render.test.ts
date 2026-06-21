import { describe, expect, it } from "vitest";
import { renderProject, toWav } from "../src/render";
import type { ProjectState } from "../src/types";

const SR = 48000;

function beat(voice: string, hits: number[], gain = 1.0): ProjectState["tracks"][number] {
  const steps = new Array(16).fill(false);
  for (const h of hits) steps[h] = true;
  return { id: 1, voice: voice as never, steps, mute: false, solo: false, gain };
}

describe("offline render", () => {
  it("produces a non-silent stereo buffer of the right length", () => {
    const state: ProjectState = { bpm: 120, swing: 0, tracks: [beat("kick", [0, 4, 8, 12])] };
    const r = renderProject(state, 1, SR);
    // 16 steps * (60/120/4 = 0.125s) = 2s + 1s tail
    expect(Math.abs(r.frames - 3 * SR)).toBeLessThan(SR * 0.05);
    expect(r.left.length).toBe(r.frames);
    let peak = 0;
    for (const v of r.left) peak = Math.max(peak, Math.abs(v));
    expect(peak).toBeGreaterThan(0);
    expect(peak).toBeLessThanOrEqual(1.0 + 1e-6);
  });

  it("honours mute/solo", () => {
    const state: ProjectState = {
      bpm: 120, swing: 0,
      tracks: [
        { ...beat("kick", [0]), solo: true },
        beat("snare", [0]),
      ],
    };
    const r = renderProject(state, 1, SR);
    let peak = 0;
    for (const v of r.left) peak = Math.max(peak, Math.abs(v));
    expect(peak).toBeGreaterThan(0); // soloed kick still sounds
  });

  it("renders silence without clipping or NaNs", () => {
    const state: ProjectState = { bpm: 120, swing: 0, tracks: [beat("kick", [])] };
    const r = renderProject(state, 1, SR);
    expect(r.left.every((v) => v === 0)).toBe(true);
  });

  it("writes a valid 16-bit stereo WAV header", () => {
    const state: ProjectState = { bpm: 120, swing: 0, tracks: [beat("kick", [0])] };
    const wav = toWav(renderProject(state, 1, SR));
    const txt = (o: number, n: number) => String.fromCharCode(...wav.slice(o, o + n));
    expect(txt(0, 4)).toBe("RIFF");
    expect(txt(8, 4)).toBe("WAVE");
    expect(txt(36, 4)).toBe("data");
    const dv = new DataView(wav.buffer);
    expect(dv.getUint16(22, true)).toBe(2); // channels
    expect(dv.getUint16(34, true)).toBe(16); // bits
    expect(wav.length).toBe(44 + dv.getUint32(40, true));
  });
});
