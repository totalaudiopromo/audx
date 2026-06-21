import { describe, expect, it } from "vitest";
import { decodeProject, encodeProject } from "../src/project";
import type { ProjectState } from "../src/types";

const sample: ProjectState = {
  bpm: 128,
  swing: 0.18,
  tracks: [
    { id: 1, voice: "kick", steps: [true, false, false, false, true, false, false, false, true, false, false, false, true, false, false, false], mute: false, solo: false, gain: 0.9 },
    { id: 2, voice: "hh", steps: new Array(16).fill(true), mute: true, solo: false, gain: 0.55 },
    { id: 3, voice: "bass", steps: new Array(16).fill(false), mute: false, solo: true, gain: 1.1 },
  ],
};

describe("project encode/decode", () => {
  it("round-trips a session", () => {
    const out = decodeProject(encodeProject(sample));
    expect(out).not.toBeNull();
    expect(out!.bpm).toBe(128);
    expect(out!.swing).toBeCloseTo(0.18, 6);
    expect(out!.tracks.length).toBe(3);
    out!.tracks.forEach((t, i) => {
      const s = sample.tracks[i];
      expect(t.voice).toBe(s.voice);
      expect(t.steps).toEqual(s.steps);
      expect(t.mute).toBe(s.mute);
      expect(t.solo).toBe(s.solo);
      expect(t.gain).toBeCloseTo(s.gain, 6);
    });
  });

  it("produces a URL-hash-safe string", () => {
    expect(encodeProject(sample)).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  it("returns null on garbage", () => {
    expect(decodeProject("not-base64!!")).toBeNull();
    expect(decodeProject("")).toBeNull();
    expect(decodeProject(btoa('{"v":2}').replace(/=+$/, ""))).toBeNull();
  });
});
