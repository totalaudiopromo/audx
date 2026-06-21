import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parsePattern, swungBeat } from "../src/dsl";

interface FixtureStep {
  sample: string;
  beat: number;
  velocity: number;
  channel: number;
  gain_db: number;
  pan: number;
  tune_semitones: number;
}
interface DslCase {
  dsl: string;
  length_beats: number;
  swing: number;
  humanize: number;
  chance: number;
  gain_db: number;
  pan: number;
  tune_semitones: number;
  steps: FixtureStep[];
}
interface SwingCase {
  swing: number;
  length_beats: number;
  beats: number[];
  expect: number[];
}

const load = <T,>(name: string): T =>
  JSON.parse(readFileSync(new URL(`../fixtures/${name}`, import.meta.url), "utf8"));

const dslCases = load<DslCase[]>("dsl.json");
const swingCases = load<SwingCase[]>("swing.json");

const TOL = 1e-9;
const near = (a: number, b: number) => expect(Math.abs(a - b)).toBeLessThan(TOL);

describe("DSL parser parity with Python", () => {
  for (const c of dslCases) {
    it(`parses ${JSON.stringify(c.dsl)}`, () => {
      const p = parsePattern(c.dsl);
      near(p.swing, c.swing);
      near(p.humanize, c.humanize);
      near(p.chance, c.chance);
      near(p.gainDb, c.gain_db);
      near(p.pan, c.pan);
      near(p.tuneSemitones, c.tune_semitones);
      expect(p.steps.length).toBe(c.steps.length);
      p.steps.forEach((s, i) => {
        const e = c.steps[i];
        expect(s.sample).toBe(e.sample);
        near(s.beat, e.beat);
        near(s.velocity, e.velocity);
        expect(s.channel).toBe(e.channel);
        near(s.gainDb, e.gain_db);
        near(s.pan, e.pan);
        near(s.tuneSemitones, e.tune_semitones);
      });
    });
  }
});

describe("swung_beat parity (banker's rounding)", () => {
  for (const c of swingCases) {
    it(`swing ${c.swing}`, () => {
      c.beats.forEach((b, i) => near(swungBeat(b, c.swing, c.length_beats), c.expect[i]));
    });
  }
});
