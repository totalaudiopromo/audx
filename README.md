# audx

A terminal-native digital audio workstation for pattern sequencing and live-coded sample playback. Built for Chris's post-Ableton workflow: calm, local, hackable, no cloud dependency.

## Current reality

This is not a finished DAW yet. It is a playable core:

- Pattern DSL: `kick 4/4`, `hh 16x8`, `x--- -x-- --x- ---x`
- Fixed-grid scheduler that works with real audio callback sizes
- 16-channel audio engine with mute, gain and level meters
- Textual TUI with mixer strips, transport and tap tempo
- Sample indexing and lookup from your local sample folder
- `.audx` JSON project save/load
- Diagnostics via `audx doctor`

Now included as honest scaffolds: offline single-pattern rendering, plugin discovery, Push 2 MIDI map output, Heartmula subprocess bridge, Sadact HTTP bridge, and a minimal local `audxd` daemon. Not yet done: true plugin hosting, full arrangement editor, Push 2 LED/display integration, and production-grade shared audio daemon.

## Quick start

```bash
uv sync
uv run audx doctor
uv run audx pattern create main "kick 4/4"
uv run audx launch
```

If you installed it as a tool/package, drop `uv run`:

```bash
audx doctor
audx launch
```

## Commands

```bash
audx launch [project.audx]              # Start TUI
audx pattern create <name> "<dsl>"      # Parse/check a pattern
audx pattern list                       # List patterns in current process
audx samples index ~/Samples            # Index local samples
audx samples list --query kick          # Search indexed samples
audx save beat.audx                     # Save current in-process state
audx load beat.audx                     # Load and print project state
audx projects list                      # List saved project files
audx render "kick 4/4" --sample kick.wav # Offline WAV render
audx plugins scan                       # Discover AU/VST/VST3 plugins only
audx push2 map                          # Print MIDI mapping scaffold
audx heartmula status                   # Check local heartlib bridge
audx sadact status                      # Check local sadact-finisher bridge
audx daemon serve                       # Run minimal local audxd state daemon
audx doctor                             # Diagnostics
audx version                            # Print version
```

Flat backwards-compatible aliases also exist for early scripts: `pattern-create`, `patterns-list`, `samples-index`, `samples-list`, `projects-list`.

## Pattern DSL

```bash
audx pattern create kick "kick 4/4"
audx pattern create hats "hh 16x8 | vel 0.45 | channel 2"
audx pattern create groove "x--- -x-- --x- ---x"
```

Supported pipe options today:

- `vel` / `velocity`: `0.0` to `1.0`
- `channel` / `ch`: mixer channel index
- `swing`: delays odd 16th steps during scheduling. Example: `swing 50%` moves `0.25` beat events to `0.375`.

## Development

```bash
uv sync
uv run pytest -q
uv run ruff check src tests
uv run mypy src/audx
```

## Philosophy

Code is the controller. Sound is the canvas. Terminal is the dimension.

The bar for audx is not "does a test pass?". The bar is: can Chris open a terminal, hit play, and feel like he is controlling a musical instrument rather than debugging Python.
