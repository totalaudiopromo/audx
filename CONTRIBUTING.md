# Contributing to audx

Thanks for hacking on audx. It's a terminal-native DAW that should feel like an
instrument, so the bar is high on both correctness and feel.

## Setup

```bash
uv sync                 # install runtime + dev deps into .venv
uv run audx demo loop.wav   # smoke test: should render a beat with no setup
```

For live real-time audio (the TUI / `audx play`) you also need PortAudio:

```bash
brew install portaudio          # macOS
sudo apt install libportaudio2  # Debian/Ubuntu
```

Offline work (rendering, MIDI export, the synth kit, project ops) needs none of
this — it's pure Python + numpy.

## Quality bar

Every change must keep these green:

```bash
uv run pytest -q             # tests
uv run ruff check src tests  # lint + import order
uv run mypy src/audx         # types (whole package, must stay clean)
```

- **Tests are required** for new behaviour. Offline features should be testable
  without an audio device — follow the `typer.testing.CliRunner` pattern in
  `tests/test_cli.py` and the synth/render tests.
- **Types matter.** mypy checks the entire `src/audx` package. `warn_return_any`
  is intentionally off (numpy stubs return `Any`); everything else is strict.
- **No silent failures.** Unfinished features should print an honest "not wired
  up yet" message, never pretend or crash.

## How the pieces fit

- `pattern.py` — the DSL parser + deterministic step scheduler. A `Pattern`
  parses its `dsl` string into `Step`s (instrument, beat, velocity, channel, …).
- `synth.py` — the built-in synth kit. Each voice is a pure-numpy function that
  returns a mono `float32` one-shot. Add a voice by writing a `_name(sr, rng)`
  renderer, registering it in `_RENDERERS`/`SYNTH_VOICES`, and adding aliases.
- `arrangement.py` — offline rendering. `render_arrangement` resolves each step
  to audio via `_voice_audio`: a real sample if the library has one, otherwise
  the synth kit, otherwise skipped.
- `engine.py` — the real-time engine. `sounddevice` is imported lazily inside
  `start()`; never import it at module top.
- `cli.py` — the typer command surface. Keep help text accurate to behaviour.

## Pull requests

- Branch from `main`, keep PRs focused, write a clear description.
- Make sure `pytest`, `ruff` and `mypy` pass locally before pushing.
- Update `CHANGELOG.md` (`[Unreleased]`) and the docs when behaviour changes.

## Philosophy

> Code is the controller. Sound is the canvas. Terminal is the dimension.

If a change makes audx feel more like an instrument and less like a program,
you're on the right track.
