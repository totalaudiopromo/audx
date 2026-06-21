/**
 * Web MIDI bridge for the studio: play voices from a controller's pads and light
 * up a Push 2 via the LED byte port. Device I/O only — the byte generation it
 * relies on (push2.ts) is golden-vector tested; this file is thin glue.
 */
import { PAD_BASE_NOTE, Push2Lights, padLayout, type PadInfo } from "./push2";

// Minimal Web MIDI typings (not in the default DOM lib).
interface MIDIMessageEvent { data: Uint8Array }
interface MIDIPort { name?: string }
interface MIDIInput extends MIDIPort { onmidimessage: ((e: MIDIMessageEvent) => void) | null }
interface MIDIOutput extends MIDIPort { send(data: number[] | Uint8Array): void }
interface MIDIAccess { inputs: Map<string, MIDIInput>; outputs: Map<string, MIDIOutput> }
interface NavigatorMIDI { requestMIDIAccess(opts?: { sysex?: boolean }): Promise<MIDIAccess> }

const PLAY_NOTE = 85;
const STOP_NOTE = 86;

export interface MidiHandlers {
  onPad: (voice: string) => void;
  onTransport: (action: "play" | "stop") => void;
}

export class MidiBridge {
  private access: MIDIAccess | null = null;
  private lights: Push2Lights | null = null;
  private layout = padLayout();
  private noteToVoice = new Map<number, string>();

  constructor(private handlers: MidiHandlers) {
    for (const [note, info] of this.layout) this.noteToVoice.set(note, info.voice);
  }

  get supported(): boolean {
    return typeof navigator !== "undefined" && "requestMIDIAccess" in navigator;
  }

  /** Returns a short status string describing what connected. */
  async connect(): Promise<string> {
    if (!this.supported) throw new Error("Web MIDI isn't available in this browser");
    this.access = await (navigator as unknown as NavigatorMIDI).requestMIDIAccess({ sysex: true });

    const inputs = [...this.access.inputs.values()];
    const input = inputs.find((p) => (p.name ?? "").toLowerCase().includes("push 2")) ?? inputs[0];
    if (input) input.onmidimessage = (e) => this.onMessage(e.data);

    const outputs = [...this.access.outputs.values()];
    const push = outputs.filter((p) => (p.name ?? "").toLowerCase().includes("push 2"));
    const out = push.find((p) => (p.name ?? "").toLowerCase().includes("user")) ?? push[0];
    if (out) {
      this.lights = new Push2Lights((bytes) => out.send(bytes));
      this.lights.setup(this.layout);
      return "Push 2 connected — pads lit";
    }
    if (input) return `controller connected: ${input.name ?? "MIDI in"}`;
    return "no MIDI devices found";
  }

  private onMessage(data: Uint8Array): void {
    const [status, d1, d2] = data;
    const isNoteOn = (status & 0xf0) === 0x90 && d2 > 0;
    if (!isNoteOn) return;
    if (d1 === PLAY_NOTE) { this.handlers.onTransport("play"); return; }
    if (d1 === STOP_NOTE) { this.handlers.onTransport("stop"); return; }
    const voice = this.noteToVoice.get(d1);
    if (voice) {
      this.handlers.onPad(voice);
      this.lights?.flash(d1);
    }
  }

  /** Flash the pad for a voice (e.g. as the sequencer plays it). */
  flashVoice(voice: string): void {
    if (!this.lights) return;
    for (const [note, info] of this.layout) {
      if (info.voice === voice) { this.lights.flash(note); return; }
    }
  }

  tick(): void { this.lights?.tick(); }
  clear(): void { this.lights?.clear(); }
}

export { PAD_BASE_NOTE };
export type { PadInfo };
