"""Built-in synthesized drum, percussion and melodic voices.

audx ships a tiny procedural drum machine *and* a handful of tonal voices so it
makes sound with *zero* setup — no sample library required. Everything here is
pure ``numpy`` (no scipy, no audio backend), which keeps it importable on any
machine and fast enough to render arrangements offline.

Each voice maps a pattern DSL instrument name (``kick``, ``snare``, ``hh`` …) to a
mono ``float32`` one-shot in ``[-1, 1]`` at a requested sample rate. The engine and
the offline renderer both fall back to these voices whenever a sample of the same
name is not found in the user's library, so a brand-new pattern like ``kick 4/4``
plays immediately.

Melodic voices
--------------
Alongside the drums there are pitched voices — ``bass``, ``pluck``, ``stab``,
``keys`` (alias ``ep``), ``saw`` and ``sine`` — so audx can do basslines, stabs
and chords, not just beats. These render at a sensible base pitch (``bass`` near
C2, the rest near C3) and are transposed purely via the existing
``tune_semitones`` parameter, e.g. ``bass e(3,8) | tune 3st``. Their sawtooth
content is band-limited (additive synthesis of a bounded number of harmonics) so
repitching them stays clean rather than aliasing harshly.

Design notes
------------
* Deterministic by default (seeded RNG) so renders are reproducible; pass a
  ``seed`` to vary the noise on percussive voices.
* Voices are short one-shots; the caller mixes/places them on the timeline.
* ``tune_semitones`` repitches a voice by resampling, so ``kick | tune -2st`` works.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "SYNTH_VOICES",
    "VOICE_ALIASES",
    "canonical_voice",
    "is_synth_voice",
    "list_voices",
    "synth_voice",
]


# Canonical voice names that the synth knows how to render.
SYNTH_VOICES: tuple[str, ...] = (
    "kick",
    "sub",
    "snare",
    "clap",
    "snap",
    "hh",
    "oh",
    "rim",
    "tom",
    "cowbell",
    "perc",
    "ride",
    "crash",
    "shaker",
    "bass",
    "pluck",
    "stab",
    "keys",
    "saw",
    "sine",
)

# Friendly aliases → canonical voice. Lets people write `bd`, `hat`, `808`, etc.
VOICE_ALIASES: dict[str, str] = {
    "bd": "kick",
    "bassdrum": "kick",
    "808": "sub",
    "sd": "snare",
    "sn": "snare",
    "cp": "clap",
    "clp": "clap",
    "ch": "hh",
    "hat": "hh",
    "hats": "hh",
    "hihat": "hh",
    "closedhat": "hh",
    "openhat": "oh",
    "ohh": "oh",
    "rs": "rim",
    "rim shot": "rim",
    "rimshot": "rim",
    "clave": "rim",
    "lt": "tom",
    "mt": "tom",
    "ht": "tom",
    "floortom": "tom",
    "cb": "cowbell",
    "bell": "cowbell",
    "cy": "crash",
    "cym": "crash",
    "shk": "shaker",
    "maraca": "shaker",
    "rd": "ride",
    "ep": "keys",
    # pattern.py maps the `perc` instrument to "percussion"; alias it back so those
    # steps render instead of silently dropping (`openhat` is already aliased above).
    "percussion": "perc",
}


def canonical_voice(name: str) -> str | None:
    """Return the canonical synth voice for ``name`` (via alias), or ``None``."""
    key = name.strip().lower()
    if key in SYNTH_VOICES:
        return key
    return VOICE_ALIASES.get(key)


def is_synth_voice(name: str) -> bool:
    """True if ``name`` (or one of its aliases) is a built-in synth voice."""
    return canonical_voice(name) is not None


def list_voices() -> list[str]:
    """All canonical voice names, in a musically sensible order."""
    return list(SYNTH_VOICES)


# ── envelope / noise helpers ──────────────────────────────────────────────────


def _t(seconds: float, sr: int) -> np.ndarray:
    """Time axis of ``seconds`` length at sample rate ``sr``."""
    return np.linspace(0.0, seconds, max(1, int(seconds * sr)), endpoint=False, dtype=np.float64)


def _exp_env(n: int, decay: float, sr: int, attack: float = 0.002) -> np.ndarray:
    """Percussive amp envelope: short linear attack then exponential decay."""
    env = np.exp(-np.arange(n, dtype=np.float64) / max(1.0, decay * sr))
    a = max(1, int(attack * sr))
    if a < n:
        env[:a] *= np.linspace(0.0, 1.0, a)
    return env


def _highpass(x: np.ndarray, amount: float = 0.92) -> np.ndarray:
    """Cheap one-pole high-pass (first difference style). amount→1 = brighter."""
    y = np.empty_like(x)
    y[0] = x[0]
    prev_x = x[0]
    prev_y = x[0]
    for i in range(1, len(x)):
        prev_y = amount * (prev_y + x[i] - prev_x)
        prev_x = x[i]
        y[i] = prev_y
    return y


def _lowpass(x: np.ndarray, window: int = 8) -> np.ndarray:
    """Cheap moving-average low-pass to tame harsh noise."""
    if window <= 1 or len(x) <= window:
        return x
    kernel = np.ones(window, dtype=np.float64) / window
    return np.convolve(x, kernel, mode="same")


def _noise(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, n)


def _normalize(x: np.ndarray, peak: float = 0.98) -> np.ndarray:
    m = float(np.max(np.abs(x))) if x.size else 0.0
    if m > 1e-9:
        x = x / m * peak
    return x


def _bl_saw(freq: float, n: int, sr: int) -> np.ndarray:
    """Band-limited sawtooth via additive synthesis.

    Sums harmonics ``sin(k·2π·f·t)/k`` up to just below Nyquist, so the tone has
    the bright buzz of a saw without the aliasing of a naive ramp — which matters
    because these voices get repitched by resampling.
    """
    t = np.arange(n, dtype=np.float64) / sr
    out = np.zeros(n, dtype=np.float64)
    if freq <= 0.0:
        return out
    nyquist = sr / 2.0
    max_k = max(1, int(nyquist / freq))
    max_k = min(max_k, 64)  # bound the work; plenty of brightness
    for k in range(1, max_k + 1):
        out += np.sin(2 * np.pi * freq * k * t) / k
    # ideal saw is (2/π)·Σ(-1)^(k+1) sin/k; here we keep all-positive phases for a
    # consistent bright timbre and just normalise the amplitude below.
    return out * (2.0 / np.pi)


def _bl_sine(freq: float, n: int, sr: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    return np.sin(2 * np.pi * freq * t)


# ── individual voices ─────────────────────────────────────────────────────────


def _kick(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.34
    t = _t(dur, sr)
    n = len(t)
    # Pitch sweep 115Hz → 48Hz
    f0, f1 = 115.0, 48.0
    pitch = f1 + (f0 - f1) * np.exp(-t / 0.035)
    phase = 2 * np.pi * np.cumsum(pitch) / sr
    body = np.sin(phase) * _exp_env(n, 0.16, sr)
    # Transient click for definition
    click = _noise(n, rng) * _exp_env(n, 0.004, sr, attack=0.0005) * 0.4
    return _normalize(body + click)


def _sub(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.8
    t = _t(dur, sr)
    n = len(t)
    f0, f1 = 70.0, 44.0
    pitch = f1 + (f0 - f1) * np.exp(-t / 0.06)
    phase = 2 * np.pi * np.cumsum(pitch) / sr
    body = np.sin(phase)
    # a touch of saturation for an 808 growl
    body = np.tanh(body * 1.4)
    return _normalize(body * _exp_env(n, 0.34, sr))


def _snare(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.22
    t = _t(dur, sr)
    n = len(t)
    tone = (np.sin(2 * np.pi * 185 * t) + 0.6 * np.sin(2 * np.pi * 330 * t)) * _exp_env(n, 0.09, sr)
    noise = _highpass(_noise(n, rng), 0.86) * _exp_env(n, 0.11, sr)
    return _normalize(0.55 * tone + 0.9 * noise)


def _clap(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.26
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float64)
    base = _highpass(_noise(n, rng), 0.8)
    # three fast bursts then a longer tail — the classic clap stack
    for offset, decay in ((0.0, 0.012), (0.009, 0.012), (0.018, 0.013), (0.028, 0.07)):
        start = int(offset * sr)
        if start >= n:
            continue
        env = _exp_env(n - start, decay, sr, attack=0.0003)
        out[start:] += base[: n - start] * env
    return _normalize(out)


def _snap(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.14
    n = int(dur * sr)
    noise = _highpass(_noise(n, rng), 0.9) * _exp_env(n, 0.03, sr, attack=0.0003)
    tone = np.sin(2 * np.pi * 1600 * _t(dur, sr)) * _exp_env(n, 0.01, sr) * 0.3
    return _normalize(noise + tone)


def _hh(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.05
    n = int(dur * sr)
    noise = _highpass(_noise(n, rng), 0.95) * _exp_env(n, 0.014, sr, attack=0.0002)
    return _normalize(noise)


def _oh(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.35
    n = int(dur * sr)
    noise = _highpass(_noise(n, rng), 0.95) * _exp_env(n, 0.16, sr, attack=0.0002)
    return _normalize(noise)


def _rim(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.06
    t = _t(dur, sr)
    n = len(t)
    tone = (np.sin(2 * np.pi * 1700 * t) + 0.5 * np.sin(2 * np.pi * 2600 * t))
    return _normalize(tone * _exp_env(n, 0.012, sr, attack=0.0002))


def _tom(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.3
    t = _t(dur, sr)
    n = len(t)
    f0, f1 = 180.0, 110.0
    pitch = f1 + (f0 - f1) * np.exp(-t / 0.08)
    phase = 2 * np.pi * np.cumsum(pitch) / sr
    body = np.sin(phase) * _exp_env(n, 0.14, sr)
    return _normalize(body)


def _cowbell(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.3
    t = _t(dur, sr)
    n = len(t)
    # two detuned square-ish tones — the 808 cowbell trick
    a = np.sign(np.sin(2 * np.pi * 540 * t))
    b = np.sign(np.sin(2 * np.pi * 800 * t))
    tone = _lowpass(0.5 * (a + b), 6)
    return _normalize(tone * _exp_env(n, 0.12, sr, attack=0.001))


def _perc(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.16
    t = _t(dur, sr)
    n = len(t)
    # simple 2-op FM blip for a metallic stab
    mod = np.sin(2 * np.pi * 430 * t) * 4.0
    tone = np.sin(2 * np.pi * 720 * t + mod)
    return _normalize(tone * _exp_env(n, 0.06, sr, attack=0.001))


def _ride(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.5
    t = _t(dur, sr)
    n = len(t)
    partials = np.zeros(n, dtype=np.float64)
    for f in (520, 1370, 2050, 3400):
        partials += np.sin(2 * np.pi * f * t)
    shimmer = _highpass(_noise(n, rng), 0.95) * 0.4
    return _normalize((partials / 4 + shimmer) * _exp_env(n, 0.22, sr, attack=0.0005))


def _crash(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.9
    n = int(dur * sr)
    noise = _highpass(_noise(n, rng), 0.97) * _exp_env(n, 0.4, sr, attack=0.001)
    return _normalize(noise)


def _shaker(sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = 0.1
    n = int(dur * sr)
    noise = _highpass(_noise(n, rng), 0.93) * _exp_env(n, 0.035, sr, attack=0.006)
    return _normalize(noise)


# ── melodic / tonal voices ────────────────────────────────────────────────────
# These render at a fixed base pitch and are transposed by ``tune_semitones``
# via the resampler in ``synth_voice``. Base pitches: bass ≈ C2 (65.4 Hz), the
# rest ≈ C3 (130.8 Hz). Saw content is band-limited so repitching stays clean.

_C2 = 65.41
_C3 = 130.81


def _bass(sr: int, rng: np.random.Generator) -> np.ndarray:
    """Punchy synth bass: band-limited saw + a sub sine, lowpassed, ~0.5s decay."""
    dur = 0.5
    n = int(dur * sr)
    saw = _bl_saw(_C2, n, sr)
    sub = _bl_sine(_C2 / 2.0, n, sr)  # an octave below for weight
    tone = 0.7 * saw + 0.6 * sub
    tone = _lowpass(tone, 8)  # tame the upper harmonics
    tone = np.tanh(tone * 1.2)  # gentle drive for punch
    env = _exp_env(n, 0.22, sr, attack=0.004)
    return _normalize(tone * env)


def _pluck(sr: int, rng: np.random.Generator) -> np.ndarray:
    """Short plucked synth: fast-decay band-limited saw with a lowpass sweep, ~0.3s."""
    dur = 0.3
    n = int(dur * sr)
    saw = _bl_saw(_C3, n, sr)
    # cheap downward lowpass sweep: cross-fade a bright tap into a dark tap over
    # the note so it starts open and closes as it decays.
    bright = _lowpass(saw, 3)
    dark = _lowpass(saw, 24)
    mix = np.linspace(0.0, 1.0, n)  # 0 = bright, 1 = dark
    out = (1.0 - mix) * bright + mix * dark
    env = _exp_env(n, 0.09, sr, attack=0.002)
    return _normalize(out * env)


def _stab(sr: int, rng: np.random.Generator) -> np.ndarray:
    """Bright detuned-saw minor chord stab (root + min 3rd + 5th), ~0.4s."""
    dur = 0.4
    n = int(dur * sr)
    # minor triad rooted at C3: root, minor third (+3 st), fifth (+7 st)
    intervals = (0, 3, 7)
    chord = np.zeros(n, dtype=np.float64)
    for st in intervals:
        f = _C3 * (2.0 ** (st / 12.0))
        # two slightly detuned saws per note for width
        chord += _bl_saw(f * 0.997, n, sr)
        chord += _bl_saw(f * 1.003, n, sr)
    chord = _lowpass(chord, 4)
    env = _exp_env(n, 0.14, sr, attack=0.004)
    return _normalize(chord * env)


def _keys(sr: int, rng: np.random.Generator) -> np.ndarray:
    """Soft electric-piano-ish tone: sine + a couple of harmonics, gentle attack, ~0.6s."""
    dur = 0.6
    n = int(dur * sr)
    f = _C3
    tone = (
        1.0 * _bl_sine(f, n, sr)
        + 0.5 * _bl_sine(f * 2.0, n, sr)
        + 0.18 * _bl_sine(f * 3.0, n, sr)
    )
    # a faint bell-like attack transient from a higher partial that decays fast
    transient = _bl_sine(f * 4.0, n, sr) * _exp_env(n, 0.04, sr, attack=0.0) * 0.25
    env = _exp_env(n, 0.28, sr, attack=0.012)  # gentle attack
    return _normalize(tone * env + transient * env)


def _saw(sr: int, rng: np.random.Generator) -> np.ndarray:
    """Raw band-limited sawtooth building block, ~0.5s."""
    dur = 0.5
    n = int(dur * sr)
    tone = _bl_saw(_C3, n, sr)
    env = _exp_env(n, 0.3, sr, attack=0.006)
    return _normalize(tone * env)


def _sine(sr: int, rng: np.random.Generator) -> np.ndarray:
    """Pure sine tone building block, ~0.5s."""
    dur = 0.5
    n = int(dur * sr)
    tone = _bl_sine(_C3, n, sr)
    env = _exp_env(n, 0.3, sr, attack=0.006)
    return _normalize(tone * env)


_RENDERERS = {
    "kick": _kick,
    "sub": _sub,
    "snare": _snare,
    "clap": _clap,
    "snap": _snap,
    "hh": _hh,
    "oh": _oh,
    "rim": _rim,
    "tom": _tom,
    "cowbell": _cowbell,
    "perc": _perc,
    "ride": _ride,
    "crash": _crash,
    "shaker": _shaker,
    "bass": _bass,
    "pluck": _pluck,
    "stab": _stab,
    "keys": _keys,
    "saw": _saw,
    "sine": _sine,
}


def _resample_linear(x: np.ndarray, ratio: float) -> np.ndarray:
    """Resample ``x`` by ``ratio`` (>1 = longer/lower) using linear interpolation."""
    if abs(ratio - 1.0) < 1e-6 or len(x) < 2:
        return x
    target_len = max(1, round(len(x) * ratio))
    old_x = np.linspace(0.0, 1.0, len(x), endpoint=False)
    new_x = np.linspace(0.0, 1.0, target_len, endpoint=False)
    return np.interp(new_x, old_x, x)


def synth_voice(
    name: str,
    sample_rate: int = 44100,
    *,
    velocity: float = 1.0,
    tune_semitones: float = 0.0,
    seed: int | None = 0,
) -> np.ndarray:
    """Render a built-in voice to a mono ``float32`` one-shot.

    Parameters
    ----------
    name:
        Voice or alias (``kick``, ``bd``, ``hh``, ``808`` …). Unknown names raise
        ``KeyError`` — call :func:`is_synth_voice` first if unsure.
    sample_rate:
        Output sample rate in Hz.
    velocity:
        Linear amplitude scale, clamped to ``[0, 1]``.
    tune_semitones:
        Repitch the voice. Negative = lower/longer, positive = higher/shorter.
    seed:
        RNG seed for the noise components. ``None`` = nondeterministic.
    """
    voice = canonical_voice(name)
    if voice is None:
        raise KeyError(f"unknown synth voice: {name!r}")
    rng = np.random.default_rng(seed)
    buffer = _RENDERERS[voice](sample_rate, rng)
    if tune_semitones:
        # Lower pitch → longer buffer. ratio = 2**(-semitones/12).
        buffer = _resample_linear(buffer, 2.0 ** (-tune_semitones / 12.0))
    buffer = buffer * float(np.clip(velocity, 0.0, 1.0))
    return buffer.astype(np.float32)
