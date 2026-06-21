import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { cliToSong, songToCli, timeline, totalBars, trackToDSL, type Song } from "../src/song";
import { renderSong } from "../src/render";
import { VEL_NORMAL, type Track } from "../src/types";

interface SongFixture {
  spec: { bpm: number; sections: Record<string, { patterns: string[]; bars: number }>; sequence: string[] };
  total_bars: number;
  timeline: { name: string; start_bar: number; bars: number }[];
}
const fixtures: SongFixture[] = JSON.parse(
  readFileSync(new URL("../fixtures/song.json", import.meta.url), "utf8")
);

const track = (voice: string, hits: number[], over: Partial<Track> = {}): Track => {
  const steps = new Array(16).fill(0);
  for (const h of hits) steps[h] = VEL_NORMAL;
  return { id: 1, voice: voice as never, steps, mute: false, solo: false, gain: 0.9, pan: 0, ...over };
};

describe("song timeline parity with Python", () => {
  for (const fx of fixtures) {
    it(`timeline for [${fx.spec.sequence.join(",")}]`, () => {
      const song = cliToSong(fx.spec);
      expect(totalBars(song)).toBe(fx.total_bars);
      const tl = timeline(song).map((e) => ({ name: e.scene.name, start_bar: e.startBar, bars: e.scene.bars }));
      expect(tl).toEqual(fx.timeline);
    });
  }
});

describe("CLI Song JSON interop", () => {
  it("studio scene → CLI patterns → studio track preserves the grid", () => {
    const t = track("kick", [0, 4, 8, 12]);
    const dsl = trackToDSL(t);
    expect(dsl).toBe("kick [1000100010001000]");
    const cli = { bpm: 120, sections: { a: { patterns: [dsl], bars: 1 } }, sequence: ["a"] };
    const back = cliToSong(cli);
    expect(back.scenes[0].tracks[0].voice).toBe("kick");
    expect(back.scenes[0].tracks[0].steps).toEqual(t.steps);
  });

  it("round-trips bpm, section names and sequence", () => {
    const song: Song = {
      bpm: 128,
      scenes: [
        { name: "intro", bars: 1, swing: 0, tracks: [track("hh", [0, 2, 4, 6, 8, 10, 12, 14])] },
        { name: "drop", bars: 1, swing: 0, tracks: [track("kick", [0, 4, 8, 12])] },
      ],
      sequence: ["intro", "drop", "drop"],
    };
    const back = cliToSong(songToCli(song));
    expect(back.bpm).toBe(128);
    expect(back.scenes.map((s) => s.name)).toEqual(["intro", "drop"]);
    expect(back.sequence).toEqual(["intro", "drop", "drop"]);
  });

  it("imports CLI DSL patterns (kick 4/4 → four on the floor) and tiles bars", () => {
    const cli = { bpm: 120, sections: { a: { patterns: ["kick 4/4"], bars: 2 } }, sequence: ["a"] };
    const song = cliToSong(cli);
    const steps = song.scenes[0].tracks[0].steps;
    expect(steps.length).toBe(32); // 2 bars tiled
    expect(steps.map((v, i) => (v > 0 ? i : -1)).filter((i) => i >= 0)).toEqual([0, 4, 8, 12, 16, 20, 24, 28]);
  });
});

describe("renderSong", () => {
  it("places sections in sequence — a hit only in section 2 lands after section 1", () => {
    const SR = 48000;
    const song: Song = {
      bpm: 120, // 1 bar = 4 beats * 0.5s = 2s = 96000 frames
      scenes: [
        { name: "silent", bars: 1, swing: 0, tracks: [track("kick", [])] },
        { name: "hit", bars: 1, swing: 0, tracks: [track("kick", [0])] },
      ],
      sequence: ["silent", "hit"],
    };
    const r = renderSong(song, SR);
    // nothing in the first bar (0..~96000), energy starts at bar 2
    const firstBarPeak = Math.max(...Array.from(r.left.slice(0, 90000)).map(Math.abs));
    const secondBarPeak = Math.max(...Array.from(r.left.slice(96000, 100000)).map(Math.abs));
    expect(firstBarPeak).toBeLessThan(1e-6);
    expect(secondBarPeak).toBeGreaterThan(0);
  });
});
