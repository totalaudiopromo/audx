# Changelog

All notable changes to audx are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Built-in synth kit** (`audx/synth.py`): 14 pure-numpy procedurally-synthesised
  drum/percussion voices (`kick`, `sub`/`808`, `snare`, `clap`, `snap`, `hh`, `oh`,
  `rim`, `tom`, `cowbell`, `perc`, `ride`, `crash`, `shaker`) with friendly
  aliases, per-voice tuning, velocity scaling and deterministic (seeded) output.
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

[Unreleased]: https://github.com/totalaudiopromo/audx/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/totalaudiopromo/audx/releases/tag/v0.2.0
