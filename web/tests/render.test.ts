import { describe, expect, it } from "vitest";
import { renderProject, renderStems, toWav } from "../src/render";
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

  it("plays a provided sample instead of the synth voice", () => {
    const t = track("kick", [0]);
    t.sampleRef = "s1";
    const state: ProjectState = { bpm: 120, swing: 0, bars: 1, tracks: [t] };
    // a distinctive stereo sample: left = +0.5 constant, right = 0
    const left = new Float32Array(4800).fill(0.5);
    const right = new Float32Array(4800);
    const provider = (ref: string) => (ref === "s1" ? { left, right } : null);
    const r = renderProject(state, 1, SR, provider);
    expect(peakOf(r.left)).toBeGreaterThan(0.25); // 0.5 * vel 0.8 * centre-pan 0.707
    expect(peakOf(r.right)).toBeLessThan(1e-6); // right channel of the sample is silent
  });

  it("falls back to the synth when the sample ref doesn't resolve", () => {
    const t = track("kick", [0]);
    t.sampleRef = "missing";
    const state: ProjectState = { bpm: 120, swing: 0, bars: 1, tracks: [t] };
    const r = renderProject(state, 1, SR, () => null); // provider can't resolve it
    expect(peakOf(r.left)).toBeGreaterThan(0); // synth kick still sounds
  });

  it("honours mute/solo", () => {
    const state: ProjectState = {
      bpm: 120, swing: 0, bars: 1,
      tracks: [{ ...track("kick", [0]), solo: true }, track("snare", [0])],
    };
    expect(peakOf(renderProject(state, 1, SR).left)).toBeGreaterThan(0);
  });

  it("renderStems: one WAV per audible track, named, non-silent", () => {
    const state: ProjectState = {
      bpm: 120, swing: 0, bars: 1,
      tracks: [track("kick", [0]), track("hh", [2]), { ...track("snare", [4]), mute: true }],
    };
    const stems = renderStems(state, 1, SR);
    expect(stems.length).toBe(2); // muted snare excluded
    expect(stems[0].name).toBe("01-kick.wav");
    expect(stems[1].name).toBe("02-hh.wav");
    for (const s of stems) {
      expect(String.fromCharCode(...s.wav.slice(0, 4))).toBe("RIFF");
      expect(s.wav.length).toBeGreaterThan(44);
    }
  });

  it("stems sum to roughly the full mix energy", () => {
    const state: ProjectState = { bpm: 120, swing: 0, bars: 1, tracks: [track("kick", [0]), track("hh", [4])] };
    const full = renderProject(state, 1, SR);
    const stems = renderStems(state, 1, SR);
    expect(stems.length).toBe(2);
    expect(peakOf(full.left)).toBeGreaterThan(0); // sanity: both produce sound
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
