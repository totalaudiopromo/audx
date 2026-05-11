"""Export patterns to a Standard MIDI File (spec §06: `audx export --midi`)."""

from __future__ import annotations

from pathlib import Path

import mido

from audx.pattern import Pattern

# General-MIDI drum map for the default sample names. Other names get a
# percussion default; mapping is conservative and easy to extend.
GM_DRUM_MAP: dict[str, int] = {
    "kick": 36,
    "snare": 38,
    "clap": 39,
    "hihat": 42,
    "openhat": 46,
    "rim": 37,
    "percussion": 60,
    "tom": 45,
    "crash": 49,
    "ride": 51,
}


def patterns_to_midi(
    patterns: dict[str, Pattern],
    out_path: Path,
    bpm: float = 128.0,
    bars: int = 1,
    ticks_per_beat: int = 480,
) -> Path:
    """Write a single-bar (or multi-bar) drum MIDI file."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))

    abs_events: list[tuple[int, str, int, int]] = []  # (tick, kind, note, velocity)
    note_len = max(1, ticks_per_beat // 8)
    for pattern in patterns.values():
        if not pattern.steps:
            pattern.parse_dsl()
        note = GM_DRUM_MAP.get(pattern.steps[0].sample if pattern.steps else "kick", 60)
        for bar in range(max(1, bars)):
            for step in pattern.steps:
                beat = bar * pattern.length_beats + pattern.swung_beat(step.beat)
                tick = round(beat * ticks_per_beat)
                velocity = max(1, min(127, int(step.velocity * 127)))
                abs_events.append((tick, "note_on", note, velocity))
                abs_events.append((tick + note_len, "note_off", note, 0))

    # Sort note_off before later note_on if ties; key by (tick, off-priority).
    abs_events.sort(key=lambda item: (item[0], 0 if item[1] == "note_off" else 1))

    last_tick = 0
    for tick, kind, note, velocity in abs_events:
        delta = max(0, tick - last_tick)
        track.append(mido.Message(kind, note=note, velocity=velocity, time=delta, channel=9))
        last_tick = tick

    mid.save(str(out_path))
    return out_path
