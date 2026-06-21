import { describe, expect, it } from "vitest";
import { audibleTracks, panGains, resizeSteps, trackUsesSample, type Track } from "../src/types";

const base = (over: Partial<Track> = {}): Track => ({
  id: 1, voice: "kick", steps: [], mute: false, solo: false, gain: 1, pan: 0, ...over,
});

describe("trackUsesSample (CLI precedence)", () => {
  it("uses the sample only when the ref resolves", () => {
    const has = (r: string) => r === "present";
    expect(trackUsesSample(base({ sampleRef: "present" }), has)).toBe(true);
    expect(trackUsesSample(base({ sampleRef: "missing" }), has)).toBe(false); // → synth
    expect(trackUsesSample(base(), has)).toBe(false); // no sample → synth
  });
});

describe("audibleTracks", () => {
  it("solo wins over mute pool", () => {
    const a = base({ id: 1 });
    const b = base({ id: 2, solo: true });
    const c = base({ id: 3, mute: true });
    expect(audibleTracks([a, b, c]).map((t) => t.id)).toEqual([2]);
  });
  it("without solo, drops muted", () => {
    const a = base({ id: 1 });
    const c = base({ id: 3, mute: true });
    expect(audibleTracks([a, c]).map((t) => t.id)).toEqual([1]);
  });
});

describe("panGains (equal-power)", () => {
  it("centre is ~-3dB on both sides; hard pans isolate a channel", () => {
    const [cl, cr] = panGains(0);
    expect(cl).toBeCloseTo(Math.SQRT1_2, 4);
    expect(cr).toBeCloseTo(Math.SQRT1_2, 4);
    expect(panGains(-1)).toEqual([expect.closeTo(1, 6), expect.closeTo(0, 6)]);
    expect(panGains(1)).toEqual([expect.closeTo(0, 6), expect.closeTo(1, 6)]);
  });
});

describe("resizeSteps", () => {
  it("pads and truncates while preserving hits", () => {
    expect(resizeSteps([0.8, 0, 0.4], 5)).toEqual([0.8, 0, 0.4, 0, 0]);
    expect(resizeSteps([0.8, 0, 0.4, 1, 1], 2)).toEqual([0.8, 0]);
  });
});
