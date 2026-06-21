import { describe, expect, it } from "vitest";
import { decodeProject, encodeProject } from "../src/project";
import { VEL_ACCENT, VEL_GHOST, VEL_NORMAL, VEL_OFF, type ProjectState } from "../src/types";

function steps(length: number, map: Record<number, number>): number[] {
  const s = new Array(length).fill(VEL_OFF);
  for (const [i, v] of Object.entries(map)) s[Number(i)] = v;
  return s;
}

const sample: ProjectState = {
  bpm: 128,
  swing: 0.18,
  bars: 2,
  tracks: [
    { id: 1, voice: "kick", steps: steps(32, { 0: VEL_ACCENT, 8: VEL_NORMAL, 16: VEL_ACCENT, 24: VEL_GHOST }), mute: false, solo: false, gain: 0.9, pan: -0.5 },
    { id: 2, voice: "hh", steps: new Array(32).fill(VEL_NORMAL), mute: true, solo: false, gain: 0.55, pan: 0.3, sampleRef: "abc123", sampleName: "myhat.wav" },
    { id: 3, voice: "bass", steps: new Array(32).fill(VEL_OFF), mute: false, solo: true, gain: 1.1, pan: 0 },
  ],
};

describe("project encode/decode (v2: velocity, bars, pan)", () => {
  it("round-trips a session exactly", () => {
    const out = decodeProject(encodeProject(sample));
    expect(out).not.toBeNull();
    expect(out!.bpm).toBe(128);
    expect(out!.swing).toBeCloseTo(0.18, 6);
    expect(out!.bars).toBe(2);
    expect(out!.tracks.length).toBe(3);
    out!.tracks.forEach((t, i) => {
      const s = sample.tracks[i];
      expect(t.voice).toBe(s.voice);
      expect(t.steps.length).toBe(32);
      t.steps.forEach((v, j) => expect(v).toBeCloseTo(s.steps[j], 6)); // /15 levels are exact
      expect(t.mute).toBe(s.mute);
      expect(t.solo).toBe(s.solo);
      expect(t.gain).toBeCloseTo(s.gain, 6);
      expect(t.pan).toBeCloseTo(s.pan, 6);
      expect(t.sampleRef).toBe(s.sampleRef);
      expect(t.sampleName).toBe(s.sampleName);
    });
  });

  it("produces a URL-hash-safe string", () => {
    expect(encodeProject(sample)).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  it("returns null on garbage or an older version", () => {
    expect(decodeProject("not-base64!!")).toBeNull();
    expect(decodeProject("")).toBeNull();
    expect(decodeProject(btoa('{"v":2}').replace(/=+$/, ""))).toBeNull();
  });
});
