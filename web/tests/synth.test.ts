import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { synthVoice } from "../src/synth";

interface VoiceRef {
  voice: string;
  tune: number;
  exact: boolean;
  n: number;
  stride: number;
  peak: number;
  rms: number;
  decimated: number[];
  env: number[];
}

const refs: VoiceRef[] = JSON.parse(
  readFileSync(new URL("../fixtures/synth.json", import.meta.url), "utf8")
);
const SR = 48000;

function decimate(buf: Float32Array, stride: number): number[] {
  const out: number[] = [];
  for (let i = 0; i < buf.length; i += stride) out.push(buf[i]);
  return out;
}
function rmsOf(buf: Float32Array): number {
  let s = 0;
  for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
  return Math.sqrt(s / buf.length);
}
function windowedRms(buf: Float32Array, windows: number): number[] {
  const n = buf.length;
  const out: number[] = [];
  for (let i = 0; i < windows; i++) {
    const a = Math.floor((i * n) / windows);
    const b = Math.floor(((i + 1) * n) / windows);
    let s = 0;
    for (let j = a; j < b; j++) s += buf[j] * buf[j];
    out.push(b > a ? Math.sqrt(s / (b - a)) : 0);
  }
  return out;
}
function pearson(a: number[], b: number[]): number {
  const n = a.length;
  const ma = a.reduce((x, y) => x + y, 0) / n;
  const mb = b.reduce((x, y) => x + y, 0) / n;
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) {
    const x = a[i] - ma, y = b[i] - mb;
    num += x * y; da += x * x; db += y * y;
  }
  return da > 0 && db > 0 ? num / Math.sqrt(da * db) : 1;
}

describe("synth voice parity with Python", () => {
  for (const ref of refs) {
    const label = `${ref.voice}${ref.tune ? ` @${ref.tune}st` : ""}`;
    it(`${label} — length & normalized peak`, () => {
      const buf = synthVoice(ref.voice, SR, { tuneSemitones: ref.tune });
      expect(buf.length).toBe(ref.n);
      expect(Math.abs(buf.reduce((m, x) => Math.max(m, Math.abs(x)), 0) - ref.peak)).toBeLessThan(2e-3);
    });

    if (ref.exact) {
      it(`${label} — waveform matches sample-for-sample`, () => {
        const buf = synthVoice(ref.voice, SR, { tuneSemitones: ref.tune });
        const dec = decimate(buf, ref.stride);
        expect(dec.length).toBe(ref.decimated.length);
        const errs = dec.map((v, i) => Math.abs(v - ref.decimated[i])).sort((a, b) => a - b);
        const mean = errs.reduce((a, b) => a + b, 0) / errs.length;
        const p99 = errs[Math.floor(0.99 * (errs.length - 1))];
        // mean stays tiny for a faithful port; a real bug breaks it across the board.
        // p99 (not max) tolerates the rare zero-crossing sign-flip in sign()-based voices.
        expect(mean).toBeLessThan(2e-4);
        expect(p99).toBeLessThan(1.5e-3);
        expect(Math.abs(rmsOf(buf) - ref.rms)).toBeLessThan(1e-3);
      });
    } else {
      it(`${label} — envelope shape & energy match`, () => {
        const buf = synthVoice(ref.voice, SR, { tuneSemitones: ref.tune });
        expect(pearson(windowedRms(buf, ref.env.length), ref.env)).toBeGreaterThan(0.9);
        const ratio = rmsOf(buf) / ref.rms;
        expect(ratio).toBeGreaterThan(0.8);
        expect(ratio).toBeLessThan(1.25);
      });
    }
  }
});
