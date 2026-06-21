# Getting started

A guided first session. By the end you'll have rendered a beat, built a few
patterns, and saved a project — all from the terminal, no samples needed.

## 1. Install

```bash
pip install audx        # or: uv sync  (to hack on audx itself)
audx doctor             # sanity check: version, audio devices, paths
```

## 2. Hear audx immediately

```bash
audx demo loop.wav
```

This renders a full multi-track beat (kick, sub, clap, hats, perc) with the
[built-in synth kit](synth-kit.md). Play `loop.wav` in anything. No samples, no
audio hardware, no config.

## 3. Render your own patterns

The [pattern language](pattern-language.md) is small. Try these:

```bash
audx render "kick 4/4"                       -o kick.wav     # four on the floor
audx render "snare 2/8"                      -o snare.wav    # backbeat
audx render "hh 16x8 | swing 12% | vel 0.5"  -o hats.wav     # swung hats
audx render "perc e(5,16,2)"                 -o perc.wav     # Euclidean groove
audx render "sub e(3,8) | tune -5st"         -o bass.wav     # tuned sub bass
```

See every available instrument:

```bash
audx synths
```

## 4. Start a project

```bash
audx init my-track --template techno
```

That scaffolds a folder with `project.audx`, `stems/` and `renders/`. Open the
TUI on it (needs PortAudio for live audio — see the README):

```bash
audx open my-track
```

## 5. Live-coding workflow

Edit `my-track/project.audx` in your editor while audx hot-reloads it:

```bash
audx watch my-track/project.audx
```

Capture variations into slots and switch between them:

```bash
audx slot set  my-track/project.audx A
audx slot next my-track/project.audx B
audx slot list my-track/project.audx
```

Branch a project cheaply, or diff two snapshots:

```bash
audx fork my-track my-track-dub
audx diff my-track/project.audx my-track-dub/project.audx
```

## 6. Export

```bash
audx export midi out.mid           # patterns → Standard MIDI File
audx midi out "Push 2"             # clock-out to external gear
```

## Where to next

- [pattern-language.md](pattern-language.md) — the full DSL reference
- [synth-kit.md](synth-kit.md) — every built-in voice
- `audx --help` — the complete command surface
