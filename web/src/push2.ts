/**
 * Push 2 pad LED control — TypeScript port of src/audx/push2.py.
 *
 * Generates the exact MIDI bytes the CLI sends (Ableton user SysEx for palette
 * colours + note_on for pad lights), so a Push 2 lights up identically whether
 * driven from the terminal or the browser (Web MIDI). The byte sequences are
 * golden-vector tested against the Python module — see web/tests/push2.test.ts.
 */

const SYSEX_HEADER = [0x00, 0x21, 0x1d, 0x01, 0x01];
const CMD_SET_PALETTE = 0x03;
const CMD_REAPPLY_PALETTE = 0x05;
export const PAD_BASE_NOTE = 36;
export const WHITE_INDEX = 122;
export const OFF_INDEX = 0;

export const PUSH2_PAD_ORDER = [
  "kick", "snare", "clap", "hh", "oh", "rim", "tom",
  "cowbell", "perc", "sub", "ride", "crash", "shaker",
] as const;

export const PUSH2_VOICE_COLORS: Record<string, [number, number, number]> = {
  kick: [255, 80, 24], snare: [255, 196, 40], clap: [255, 64, 156], hh: [40, 220, 230],
  oh: [36, 210, 168], rim: [170, 230, 64], tom: [232, 150, 48], cowbell: [220, 200, 60],
  perc: [170, 92, 240], sub: [60, 110, 255], ride: [120, 184, 255], crash: [230, 72, 230],
  shaker: [92, 220, 96],
};

/** 8-bit colour value → (low 7 bits, high 1 bit) for Push 2 SysEx. */
function split(value: number): [number, number] {
  value = Math.max(0, Math.min(255, value));
  return [value & 0x7f, (value >> 7) & 0x01];
}

/** Full SysEx message (incl. F0/F7) to define palette entry `index` as `rgb`. */
export function setColorSysex(index: number, rgb: [number, number, number], white = 0): number[] {
  const [r, g, b] = rgb;
  return [
    0xf0, ...SYSEX_HEADER, CMD_SET_PALETTE, index,
    ...split(r), ...split(g), ...split(b), ...split(white), 0xf7,
  ];
}

export function reapplySysex(): number[] {
  return [0xf0, ...SYSEX_HEADER, CMD_REAPPLY_PALETTE, 0xf7];
}

/** note_on channel 0, velocity = palette index → lights pad `note`. */
export function lightNote(note: number, index: number): number[] {
  return [0x90, note, index];
}

export interface PadInfo {
  voice: string;
  color: [number, number, number];
}

/** Pad note → kit voice + colour, voices laid out from PAD_BASE_NOTE up. */
export function padLayout(): Map<number, PadInfo> {
  const layout = new Map<number, PadInfo>();
  PUSH2_PAD_ORDER.forEach((voice, i) => {
    layout.set(PAD_BASE_NOTE + i, { voice, color: PUSH2_VOICE_COLORS[voice] });
  });
  return layout;
}

type Sender = (bytes: number[]) => void;

/** Paint, flash and clear Push 2 pads. Mirrors push2.py Push2Lights. */
export class Push2Lights {
  private base = new Map<number, number>(); // pad note → palette index
  private revert = new Map<number, number>(); // pad note → restore time (ms)
  constructor(private send: Sender, private flashMs = 110) {}

  setup(layout: Map<number, PadInfo>): void {
    this.send(setColorSysex(OFF_INDEX, [0, 0, 0]));
    this.send(setColorSysex(WHITE_INDEX, [255, 255, 255], 255));
    this.base.clear();
    const notes = [...layout.entries()].sort((a, b) => a[0] - b[0]);
    notes.forEach(([note, info], i) => {
      const idx = i + 1; // palette slots 1..N
      this.send(setColorSysex(idx, info.color));
      this.base.set(note, idx);
    });
    this.send(reapplySysex());
    for (const [note, idx] of this.base) this.send(lightNote(note, idx));
  }

  flash(note: number, now = performance.now()): void {
    if (this.base.has(note)) {
      this.send(lightNote(note, WHITE_INDEX));
      this.revert.set(note, now + this.flashMs);
    }
  }

  tick(now = performance.now()): void {
    for (const [note, t] of [...this.revert]) {
      if (now >= t) {
        this.send(lightNote(note, this.base.get(note)!));
        this.revert.delete(note);
      }
    }
  }

  clear(): void {
    for (const note of this.base.keys()) this.send(lightNote(note, OFF_INDEX));
    this.revert.clear();
  }
}
