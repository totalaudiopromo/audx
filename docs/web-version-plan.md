# Plan: audx in the browser

How audx could become playable at a public URL — honestly scoped, with the
trade-offs spelled out so we choose with eyes open.

## The starting point

audx today is Python: a numpy synth kit, an offline renderer, a PortAudio
real-time engine, a Textual TUI, and `mido` MIDI. **None of that runs in a
browser as-is** — PortAudio, Textual and the OS MIDI backend are all native.
So a web version is a *port of the core*, not a deploy flag. The good news: the
parts that matter (the synth DSP and the pattern DSL) are small and self-contained.

## Three routes

### A. Pyodide — run the real Python in WASM  *(fast to a demo)*
[Pyodide](https://pyodide.org) runs CPython + numpy in the browser. We could load
`audx.synth` and `audx.arrangement` unchanged, render a pattern to a numpy buffer,
and play it through the Web Audio API.
- ✅ Reuses our exact, tested Python — the sound is identical, no re-port.
- ✅ "Type a pattern → render → hear it" works in-browser quickly.
- ❌ Not real-time: Pyodide isn't suited to low-latency audio callbacks, so live
  jam/playhead would be choppy. Best for the **offline** features.
- ❌ ~10 MB runtime download.

### B. TypeScript + Web Audio  *(the real instrument)*  ← recommended target
Re-implement the core in TypeScript against the Web Audio API:
- **Synth kit** → `AudioWorklet`/buffer synthesis. The voices are short numpy DSP
  (sine sweeps, filtered noise, band-limited saws) — a direct, small port.
- **Pattern DSL** → port `pattern.py`'s parser (it's pure string→steps logic).
- **Scheduler** → Web Audio's sample-accurate clock (lookahead scheduling).
- **UI** → reuse what we've already built: the monochrome sequencer grid from the
  promo and `audx serve` is the exact visual language.
- **MIDI / Push 2** → the **Web MIDI API** works in Chrome/Edge, *including SysEx*,
  so the Push 2 pad-lighting we just shipped ports directly (same note/SysEx bytes).
- ✅ True real-time play, live grid, controller + Push 2 LEDs, shareable URLs.
- ❌ A real rewrite of the core in TS; Web MIDI is Chromium-only.

### C. Rust/C core compiled to WASM  *(overkill for now)*
Best performance and one shared engine for native + web, but the largest effort.
Revisit only if the TS engine hits perf limits.

## Attack plan

### ✅ Phase 1 — "Try it" in the browser  *(shipped)*
A Pyodide-backed playground at **`/play.html`** on the landing site: a DSL editor +
play button that runs the **real** `audx.pattern` parser and `audx.synth` kit in
the browser (numpy via Pyodide), mixes to a stereo buffer and plays it through Web
Audio. Presets, a WAV download, no server — nothing leaves the visitor's machine.

- Code: `site/play.html`, `site/audx_web/webrender.py` (dual-imports the real
  package in tests, flat modules in Pyodide).
- No drift: `scripts/sync-web-modules.sh` copies `synth.py`/`pattern.py` into the
  bundle; the Pages deploy runs it automatically and a test asserts the copies
  equal `src/` (`tests/test_webrender.py`).
- Reused real code, so the in-browser sound is identical to the CLI.

### Phase 2 — The live instrument *(medium, ~1–2 weeks)*
Goal: real-time play in the browser with the sequencer grid and a MIDI controller.

**M2.2 — DSL parser in TS.** ✅ *shipped.* `web/src/dsl.ts` is a faithful port of
`pattern.py` (steps + modifiers + swing). The golden-vector harness is live:
`scripts/gen_web_fixtures.py` emits `web/fixtures/*.json` from the **real** parser;
vitest (`web/tests/dsl.test.ts`) asserts the TS output matches within 1e-9 — 30
cases covering every grammar branch, the `16x8`=16-hits quirk, banker's rounding in
swing, sample aliases and modifier clamping. A Python test guards the fixtures
against drift, and CI runs both sides (`web` job in `ci.yml`).

**M2.1 — TS synth engine.** ✅ *shipped.* All 20 voices ported to `web/src/synth.ts`
(rendered buffers, played through Web Audio). Golden-vector verified: the 10
noiseless voices match numpy **sample-for-sample** (mean err < 2e-4), cowbell + the
9 noise voices match structurally (normalized peak, envelope correlation, energy),
and the repitch resampler is checked too — 44 vitest assertions. Also fixed a latent
bug: `perc` had no `percussion` alias so those steps dropped silently.

**M2.4 — Web UI.** ✅ *first cut shipped:* **audx studio** (`site/studio.html`) — a
16-step grid drum machine driven by the native synth, with a sample-accurate Web
Audio lookahead scheduler, per-track mute/solo/volume, swing, a master meter, drag-
to-paint, spacebar transport, and **copy-as-audx-DSL** (the CLI bridge). Bundled
with esbuild (`web/src/studio.ts` → `site/studio.js`); built in the Pages deploy.

**M2.3 — Lookahead scheduler.** ✅ landed as part of the studio (25 ms tick /
100 ms lookahead, real swing offset on odd 16ths).
**M2.3 — Lookahead scheduler.** Web Audio sample-accurate clock (the standard
25 ms-tick / 100 ms-lookahead pattern). *Acceptance:* steady timing at 124 BPM, no
drift over 5 minutes.
**M2.4 — Web UI.** Reuse the monochrome sequencer grid from `audx serve` /the promo:
editable pattern, moving playhead, transport, mixer faders.
**M2.5 — Web MIDI.** ✅ *shipped.* `web/src/midi.ts` wires
`navigator.requestMIDIAccess({ sysex: true })` into the studio: controller pads
play voices and drive the sequencer's transport. **Push 2 pad LEDs** port directly —
`web/src/push2.ts` regenerates the exact Ableton SysEx palette + note_on bytes from
`audx/push2.py`, **golden-vector verified** (`web/tests/push2.test.ts`), so the kit
lights up in-browser on Chrome/Edge. The sequencer flashes pads as it plays.

### Phase 3 — Parity & sharing *(incremental)*
- **M3.1 Mixer** — ✅ per-track mute/solo/volume **and pan** (equal-power, matches
  `StereoPannerNode`; tested in `render.ts`). Plus **per-step velocity/accents**
  (ghost/normal/accent, right-click to cycle) and **multi-bar patterns** (1/2/4).
- **M3.2 Songs** — port the `Song`/section model; render/arrange in-browser.
- **M3.3 Projects** — ✅ *shipped.* `localStorage` autosave + **share links** that
  encode the whole session in the URL hash (no backend) — `web/src/project.ts`,
  round-trip tested (`web/tests/project.test.ts`).
- **M3.4 Your samples** — ✅ *shipped.* Drop an audio file on a track (or 📁) →
  `decodeAudioData` → it plays instead of the synth, with the CLI's precedence (a
  resolvable sample wins, else synth; `web/src/samples.ts`). Persisted as raw bytes in
  **IndexedDB** (survives reload); share links carry the sample *ref/name* only, so a
  link on another machine falls back to the synth. v3 project encoding; render takes a
  sample provider. Logic tested (`types`/`project`/`render` tests); decode + IndexedDB
  are browser-only (manual QA).
- **M3.5 Export** — ✅ *shipped:* offline render-to-WAV **and per-track stems**
  (`renderStems` → one normalized WAV per audible track, bundled with a dependency-
  free store-only ZIP writer `web/src/zip.ts`). Reuses the native synth + scheduler
  timing; honours samples/velocity/pan/multi-bar. Tested (render + CRC32/zip).

### Sequencing & ownership
Phase 2 is the real build and the natural next sprint. Do **M2.2 (DSL) and M2.1
(synth) first** behind golden-vector tests — they're the fidelity-critical core and
unblock everything else. M2.3–M2.5 are then mostly UI + plumbing on top. Phase 3
items are independent and can land in any order once the engine exists.

## Keeping native and web honest

The DSL is the contract between the two engines. To stop them drifting, generate
**golden test vectors** from the Python side (pattern → expected steps, and short
render → expected samples/RMS) and assert the TS port reproduces them. That keeps
"the web version sounds like audx" a tested guarantee, not a hope.

## Rough effort

- Phase 1: ~1–2 days (Pyodide glue + a small page).
- Phase 2: ~1–2 weeks for a solid MVP (synth + DSL + scheduler + grid + Web MIDI).
- Phase 3: incremental.

## Risks

- **Browser support**: Web MIDI/SysEx is Chromium-only; Safari/Firefox users get
  audio + keyboard but not hardware controllers.
- **Audio latency**: fine for a step sequencer; live finger-drumming wants
  `AudioWorklet` + careful scheduling.
- **Two codebases**: mitigated by the golden-vector tests above.

If we want, Phase 1 can ship onto the existing landing page so the site doubles as
a playable teaser — a real "use it at a URL" moment without the full rewrite.
