# The built-in synth kit

audx ships a tiny procedural drum machine **and** a handful of pitched melodic
voices so it makes sound with **zero setup** — no sample library required. It's
pure `numpy` (no audio backend, no scipy), so it imports anywhere and renders
arrangements offline.

## How fallback works

When the renderer (or the live engine) resolves a pattern step, it looks for
audio in this order:

1. A **real sample** in your library whose name matches the instrument
   (`kick.wav`, `snare.aif`, …). Your audio always wins.
2. Otherwise, a **built-in synth voice** of that name (or one of its aliases).
3. Otherwise the step is **skipped** silently — no crash.

So `audx render "kick 4/4"` synthesises a kick today, and the day you drop a
`kick.wav` into your stems folder it uses that instead. Nothing else changes.

## Voices

| Voice | Aliases | Character |
|-------|---------|-----------|
| `kick` | `bd`, `bassdrum` | Punchy 115→48 Hz pitch-swept kick with a transient click |
| `sub` | `808`, `bass` | Long sub-bass with gentle saturation (an 808-ish tone) |
| `snare` | `sd`, `sn` | Tonal body + high-passed noise |
| `clap` | `cp`, `clp` | Three fast noise bursts + a longer tail |
| `snap` | — | Tight finger-snap (noise + short tone) |
| `hh` | `hat`, `hats`, `hihat`, `ch`, `closedhat` | Short high-passed noise (closed hat) |
| `oh` | `openhat`, `ohh` | Longer high-passed noise (open hat) |
| `rim` | `rs`, `rimshot`, `clave` | Bright metallic ping |
| `tom` | `lt`, `mt`, `ht`, `floortom` | Pitched, decaying drum |
| `cowbell` | `cb`, `bell` | Two detuned square tones (the 808 cowbell trick) |
| `perc` | — | 2-operator FM metallic stab |
| `ride` | `rd` | Shimmering struck-cymbal partials |
| `crash` | `cy`, `cym` | Long high-passed noise wash |
| `shaker` | `shk`, `maraca` | Short filtered-noise shaker |
| `bass` | — | Punchy synth bass: band-limited saw + sub sine, lowpassed (~C2) |
| `pluck` | — | Short plucked saw with a downward lowpass sweep (~C3) |
| `stab` | — | Bright detuned-saw minor-chord stab (root + min 3rd + 5th, ~C3) |
| `keys` | `ep` | Soft electric-piano-ish tone: sine + harmonics, gentle attack (~C3) |
| `saw` | — | Raw band-limited sawtooth building block (~C3) |
| `sine` | — | Pure sine tone building block (~C3) |

### Melodic voices

The last six voices above are **pitched**, so audx can do basslines, stabs and
chords — not just beats. Each renders at a sensible fixed base pitch (`bass` near
**C2 ≈ 65 Hz**, the rest near **C3 ≈ 131 Hz**; `stab` is a minor triad rooted at
C3). There is no note-name syntax in the DSL — you set pitch entirely with the
existing `tune` modifier, which transposes by resampling:

```bash
audx render "bass e(3,8) | tune -5st"     -o bassline.wav   # down a fourth
audx render "stab e(3,8,2) | tune 5st"    -o stabs.wav      # up a fourth
audx render "keys 4/4 | tune 7st | vel 0.6"                 # up a fifth, softer
```

Their sawtooth content is band-limited (additive synthesis of a bounded set of
harmonics), so repitching them up or down stays clean instead of aliasing harshly.

List them any time:

```bash
audx synths
```

## Using voices

Any voice name works as an instrument in the DSL:

```bash
audx render "cowbell e(5,16,2)"          -o bell.wav
audx render "sub e(3,8) | tune -5st"     -o bass.wav
audx render "hh 16x8 | swing 12% | vel 0.5"
```

Modifiers apply to synth voices exactly as they do to samples:

- `vel` scales amplitude.
- `tune` repitches the voice (negative = lower/longer). Implemented by resampling.
- `pan`, `gain`, `swing`, `humanize`, `chance` behave as in the
  [pattern language](pattern-language.md).

## Programmatic API

```python
from audx.synth import synth_voice, is_synth_voice, list_voices

buf = synth_voice("kick", 44100, velocity=0.9, tune_semitones=-2.0)
# -> mono float32 numpy array in [-1, 1]

is_synth_voice("808")   # True (alias of 'sub')
list_voices()           # ['kick', 'sub', 'snare', ...]
```

Output is deterministic by default (seeded RNG), so renders are reproducible.
Pass `seed=None` to vary the noise components, or a different integer `seed` per
hit for natural variation.
