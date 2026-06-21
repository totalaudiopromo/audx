# Changelog

All notable changes to audx are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-21

### Added
- **Live MIDI jam** (`audx jam`): play the built-in synth kit in real time from a
  MIDI controller or Push 2 — hit a pad, hear a sound instantly. Drums mode maps
  General-MIDI notes to drum voices (and never leaves a pad silent); `--chromatic`
  plays a melodic voice across the keys. New `audx/live.py` mapping module + tests,
  and a guide at [docs/playing-live.md](docs/playing-live.md).
- **Push 2 pad LEDs**: audx now lights the Push 2 pads — `audx jam` auto-detects a
  Push 2, paints the drum kit (one colour per voice) and flashes each pad as it's
  struck. `audx push2 lights` lights the kit on its own for a quick check.
  Implemented to Ableton's Push 2 MIDI spec (SysEx colour palette + note-on LEDs).
- Bundle the `python-rtmidi` MIDI backend so `midi`/`jam`/Push 2 work out of the box.
- **Built-in synth kit** (`audx/synth.py`): 20 pure-numpy procedurally-synthesised
  voices with friendly aliases, per-voice tuning, velocity scaling and
  deterministic (seeded) output.
  - 14 drum/perc voices: `kick`, `sub`/`808`, `snare`, `clap`, `snap`, `hh`, `oh`,
    `rim`, `tom`, `cowbell`, `perc`, `ride`, `crash`, `shaker`.
  - 6 **melodic** voices: `bass`, `pluck`, `stab`, `keys` (alias `ep`), `saw`,
    `sine` — pitched (band-limited sawtooth) and transposed via `tune`, so audx
    does basslines, plucks and chord stabs, e.g. `bass e(5,16) | tune -7st`.
    (`bass` is now its own voice, no longer an alias of `sub`.)
- **Song arrangements** (`audx/arrangement.py` `Song`/`Section`/`render_song`) plus
  `audx song render <spec.json>` and `audx song info <spec.json>`: build
  multi-section tracks (intro/verse/drop/outro) from a JSON spec and render them
  to a single WAV.
- **Live finger-drum pads** in the TUI: keys `w e r a s d f z x c` (and `u i o`)
  trigger built-in synth voices on dedicated channels while a project is open.
- **Marketing assets**: an animated terminal demo GIF in the README
  (`scripts/make-demo-gif.py`, Pillow-only) and a runnable Remotion promo video
  project under `marketing/remotion/`.
- **Automated PyPI releases**: `.github/workflows/release.yml` publishes on a
  `v*` tag via PyPI Trusted Publishing (OIDC, no stored token).
- **Zero-config sound**: the offline renderer falls back to the synth kit when a
  sample of the same name isn't found, so `audx render "kick 4/4"` makes sound
  with no sample library. `--sample` is now optional.
- `audx demo [out.wav]` — render a full multi-track beat with the synth kit in
  one command. The flagship "try it in 10 seconds" experience.
- `audx synths` — list every built-in voice and its aliases.
- `SynthVoice` in the live engine, plus synth fallback in the real-time callback,
  so the TUI makes sound without any samples loaded.

### Changed
- **PortAudio is now optional for offline use.** `sounddevice` is imported lazily,
  so the CLI and all offline features (render, export, demo, diff, project ops)
  work on machines without the PortAudio system library. Only live real-time
  playback requires it, with a clear install hint when missing.
- Type checking now covers the **entire package** (was 4 files) and passes clean.

### Fixed
- `audx mix set <ch> gain -3` no longer errors on the negative dB value — the
  command accepts dash-leading values as documented.

### Quality
- Test suite expanded from 30 to 120+ tests; coverage raised from ~28% to ~43%.
  CI coverage gate raised to 40%.

## [0.2.0]

### Added
- Terminal-native DAW core: pattern DSL, fixed-grid scheduler, 16-channel audio
  engine with mute/gain/level meters, Textual TUI with mixer strips and tap tempo.
- Pattern DSL: `4/4`, `16x8`, Euclidean `e(k,n,rot)`, explicit `[1.0.1.0]` grids
  and `x---` grids, with `vel`, `channel`, `swing`, `humanize`, `chance`, `gain`,
  `pan` and `tune` pipe modifiers.
- Sample indexing/search, `.audx` JSON project save/load, offline WAV + stems
  rendering, project diffing, cheap forking, hot-reload `watch`, read-only `serve`
  dashboard.
- MIDI export to Standard MIDI File, MIDI clock-out, MIDI input recording.
- Pattern slots (A/B/C/D), vim-style macro registers, OS-keychain AI key store.
- Optional AI extras (librosa): text-to-pattern, sample similarity, auto-tagging,
  groove extraction.
- Honest scaffolds: plugin discovery, Push 2 MIDI map, Heartmula bridge,
  sadact-finisher bridge, minimal local `audxd` daemon, latency calibration.
- `audx doctor` diagnostics and CI across Python 3.10–3.12.

[Unreleased]: https://github.com/totalaudiopromo/audx/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/totalaudiopromo/audx/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/totalaudiopromo/audx/releases/tag/v0.2.0
