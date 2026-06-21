import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { PAD_BASE_NOTE, Push2Lights, padLayout } from "../src/push2";

interface Push2Fixture {
  layout: Record<string, string>;
  setup: number[][];
  flash_kick: number[][];
}

const fx: Push2Fixture = JSON.parse(
  readFileSync(new URL("../fixtures/push2.json", import.meta.url), "utf8")
);

function record(): { send: (b: number[]) => void; msgs: number[][] } {
  const msgs: number[][] = [];
  return { send: (b) => msgs.push(b), msgs };
}

describe("Push 2 LED bytes match Python", () => {
  it("pad layout maps the same notes to the same voices", () => {
    const layout = padLayout();
    for (const [noteStr, voice] of Object.entries(fx.layout)) {
      expect(layout.get(Number(noteStr))?.voice).toBe(voice);
    }
    expect(layout.has(PAD_BASE_NOTE)).toBe(true);
  });

  it("setup() emits the exact SysEx + note_on byte stream", () => {
    const { send, msgs } = record();
    new Push2Lights(send).setup(padLayout());
    expect(msgs).toEqual(fx.setup);
  });

  it("flash() lights the struck pad white with the right bytes", () => {
    const { send, msgs } = record();
    const lights = new Push2Lights(send);
    lights.setup(padLayout());
    msgs.length = 0;
    lights.flash(PAD_BASE_NOTE, 1000);
    expect(msgs).toEqual(fx.flash_kick);
  });

  it("tick() restores a pad to its base colour after the flash window", () => {
    const { send, msgs } = record();
    const lights = new Push2Lights(send, 110);
    lights.setup(padLayout());
    lights.flash(PAD_BASE_NOTE, 1000);
    msgs.length = 0;
    lights.tick(1050); // still within flash window → nothing
    expect(msgs.length).toBe(0);
    lights.tick(1200); // elapsed → restore note_on to base palette index (1)
    expect(msgs).toEqual([[0x90, PAD_BASE_NOTE, 1]]);
  });
});
