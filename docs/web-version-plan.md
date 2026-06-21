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

## Recommended phasing

1. **Phase 1 — "Try it" (small).** Pyodide-backed page on the landing site: a DSL
   box + "render" button that plays the result. Reuses Python as-is. High wow, low
   risk. Lives at the same URL as the marketing site.
2. **Phase 2 — Live core (medium).** Port synth + DSL + scheduler to TS + Web Audio;
   wire the existing sequencer-grid UI; add Web MIDI (controllers + Push 2 LEDs).
   This is the actual browser instrument.
3. **Phase 3 — Parity.** Mixer, songs, project save/load (localStorage + share
   links), sample upload via the File API.

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
