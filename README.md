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
uv run audx init my-loop --parent /tmp --no-git
uv run audx load ~/Samples/kick.wav --ch 0 --project /tmp/my-loop/project.audx
uv run audx render-project /tmp/my-loop/project.audx --output /tmp/my-loop/renders/my-loop.wav
uv run audx open /tmp/my-loop/project.audx
```

If you installed it as a tool/package, drop `uv run`:

```bash
audx doctor
audx launch
```

## Commands

```bash
audx init <name>                        # Scaffold project folder (stems/, renders/, git init)
audx open [project]                     # Open TUI on a project file or folder
audx launch [project.audx]              # Same as `open`, legacy spelling
audx pattern create <name> "<dsl>"      # Parse/check a pattern
audx pattern set <ch> "<dsl>"           # Replace a channel's DSL line
audx pattern step <ch> <n> [on|off]     # Toggle/set one step in a channel grid
audx pattern list                       # List patterns in current process
audx load sample.wav --ch 0 --project project.audx
                                        # Copy audio into stems/ and bind to channel
audx track add <name> "<dsl>" -c 2      # Add a track to the in-process engine
audx track rm <name>                    # Remove a track
audx mix set <ch> gain <dB>             # Set channel gain
audx mix set <ch> mute on|off           # Set channel mute
audx mute <ch>                          # Toggle channel mute
audx samples index ~/Samples            # Index local samples
audx stems index ~/Samples              # Alias matching spec §06
audx stems search 909 kick              # Fuzzy-search the sample index
audx render "kick 4/4" --sample k.wav   # Offline WAV render
audx render-project project.audx        # Render a saved project to WAV
audx render ... --stems                 # Per-track stems render
audx render ... --variations 10         # Stochastic variations
audx diff a.audx b.audx                 # Human-readable project diff
audx finish project.audx --profile ukg  # Render + master via sadact-finisher
audx fork project new-name              # Cheap branching
audx save beat.audx                     # Save current in-process state
audx load beat.audx                     # Load and print project state
audx projects list                      # List saved project files
audx watch project.audx                 # Hot-reload .audx on save
audx serve --port 8080                  # Monitor dashboard + /app playable browser UI
audx voice                              # Probe on-device voice control
audx rec --calibrate                    # Measure round-trip latency
audx export midi out.mid                # Export patterns to Standard MIDI File
audx midi list                          # List MIDI inputs/outputs
audx midi out "Push 2"                  # Send MIDI clock to a device
audx midi rec name --bars 1             # Record incoming MIDI as a pattern
audx slot set project.audx A            # Save current patterns into slot A
audx slot next project.audx B           # Activate slot B
audx slot list project.audx             # Show all four slots
audx macro record a "x j x j"           # Store a macro in register a
audx macro replay a                     # Print register a
audx ai key sk-...                      # Store AI API key in OS keychain
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
audx pattern create kick "kick 4/4"                          # four on the floor
audx pattern create snare "snare 2/8"                        # beats 2 and 4
audx pattern create hats "hh 16x8 | vel 0.45 | channel 2"    # 8 hats over 16 steps
audx pattern create groove "x--- -x-- --x- ---x"             # x/rest grid
audx pattern create perc "perc e(5,16,2)"                    # Euclidean, rotated
audx pattern create clap "clap [1.0.1.0.1.1.0.0]"            # explicit grid
```

Supported pipe operators:

- `vel` / `velocity`: `0.0` to `1.0`
- `channel` / `ch`: mixer channel index
- `swing`: delays odd 16th steps. Example: `swing 50%` moves `0.25` beat events to `0.375`.
- `humanize`: percent jitter on velocity per fire (e.g. `humanize 8%`)
- `chance`: per-step trigger probability (`chance 70%`)
- `gain`: ±dB on the track (`gain -3db`)
- `pan`: `L100..R100` or `-1..1` (`pan L50`)
- `tune`: ±semitones (`tune -2st`)

## Project files

`audx init my-loop` lays out:

```
my-loop/
  project.audx          # JSON: bpm, patterns, slots, mixer, finisher config
  stems/                # WAV/AIFF source material
  renders/              # rendered output (gitignored)
  .git/                 # optional, created by default
```

The project file carries a `[finisher]` block that maps 1:1 to sadact-finisher
CLI flags (`profile`, `platform`, `loudness`, `tone`, `energy`, `reference`,
`use_stems`, `drums_up`, `bass_down`). `audx finish` uses these to drive the
mastering pass.

## Browser mode

`audx serve` is still local-first. It serves a small browser UI from your own
machine, with no cloud relay:

```bash
uv run audx serve --port 8080
open http://127.0.0.1:8080/app?project=/tmp/my-loop/project.audx
```

The browser app reads the `.audx` project via localhost, plays patterns with
Web Audio, and can load extra audio files directly in the browser session.

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
