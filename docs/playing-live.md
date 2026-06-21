# Playing audx live with a MIDI controller or Push 2

A practical, kid-proof guide to plugging in a controller and making sound *now*.
No samples, no project, no setup — every pad makes a noise.

> **TL;DR**
> ```bash
> audx midi list      # check your controller shows up
> audx jam            # hit the pads → drums!
> ```

---

## 1. What you need

- audx installed (`pip install audx`).
- **PortAudio** for live sound (only needed for real-time play):
  - macOS: `brew install portaudio`
  - Linux: `sudo apt install libportaudio2`
- A USB MIDI controller **or** an Ableton Push 2.
- Headphones or speakers. (Headphones = fewer surprises with kids 🙂)

Sanity check everything first:

```bash
audx doctor          # shows version + audio devices
audx midi list       # should list your controller under "inputs"
```

If your controller shows up under `inputs:`, you're ready.

---

## 2. Jam — pads make drums

```bash
audx jam
```

Hit the pads. That's it. You'll see each hit print as it plays:

```
  MIDI in: MPK Mini
  ♪ jam mode: drums  (hit some pads!)
  Ctrl-C to stop.
     36 → kick     ████
     38 → snare    ███
     42 → hh       ██
```

- Pads follow the **General MIDI drum map** (the standard most controllers use):
  kick, snare, hi-hat, clap, toms, cymbals, cowbell…
- **No pad is ever silent** — any pad that isn't a "standard" drum still triggers
  a drum, so kids can mash the whole grid and always get sound.
- Harder hit = louder (velocity sensitive).

Stop with **Ctrl-C**.

### Pick a specific controller

If you have more than one device, name it (any part of the name works):

```bash
audx midi list                 # copy the name you want
audx jam --port "Push 2"
```

---

## 3. Jam — play melodies

Switch to **chromatic** mode and the whole keyboard/grid plays one pitched voice:

```bash
audx jam --chromatic                 # plays the 'keys' voice
audx jam --chromatic --voice bass    # a bassline
audx jam --chromatic --voice pluck   # plucky lead
```

Middle C plays the voice at its natural pitch; up/down the keys transpose it.
Melodic voices: `bass`, `pluck`, `stab`, `keys`, `saw`, `sine`
(see [the synth kit](synth-kit.md)).

---

## 4. Push 2 notes

Push 2 works as a standard MIDI controller over USB — **and audx lights its pads.**

1. Plug it in (USB). For pads + LEDs, bus power is fine; the screen wants Push 2's
   power supply.
2. Quick LED check (no audio needed):
   ```bash
   audx push2 lights        # lights the drum kit on the pads; Ctrl-C to clear
   ```
   You should see the bottom two rows light up — one colour per drum.
3. Play it:
   ```bash
   audx jam                 # auto-detects Push 2, lights the kit, flashes on hit
   ```
   audx finds the Push 2 automatically (you don't need `--port`). Each pad in the
   bottom two rows is a drum, lit in its own colour; hitting a pad flashes it white.
4. The whole 8×8 grid still plays in drums mode (unlit pads make sound too). Try
   `--chromatic` to turn the grid into a pitched instrument (lights stay off in
   chromatic mode). Disable lights with `audx jam --no-lights`.

**Pad colours** (bottom row, left→right): kick · snare · clap · hh · oh · rim · tom,
then cowbell · sub · ride · crash · shaker on the next row up.

> Notes: audx drives the pad **LEDs**; the Push 2 **screen** is still on the
> roadmap. If lights don't appear, make sure no other app (Ableton/Live) has
> grabbed the Push 2 — pick its **User** port. Send Push 2 a tempo clock with
> `audx midi out "Push 2" --bpm 120`.

---

## 5. No controller? Play from the keyboard

Open the TUI and use the computer keyboard as drum pads — no MIDI needed:

```bash
audx open
```

Pad keys: `w` kick · `e` snare · `r` clap · `a` hh · `s` oh · `d` rim · `f` tom ·
`z` cowbell · `x` perc · `c` sub · `u` ride · `i` crash · `o` shaker.

---

## 6. Keep what you played

Record a controller performance into a pattern, then render it to a WAV you can
keep or send to grandma:

```bash
audx midi rec jam1 --bars 2      # records 2 bars from your controller
audx render "kick 4/4" -o keep.wav   # or render any pattern to a file
```

Build a whole track from sections with [songs](../README.md#songs):

```bash
audx song render track.json -o track.wav
```

---

## Troubleshooting

**No sound when I hit pads**
- Is PortAudio installed? (`brew install portaudio` / `apt install libportaudio2`)
- Check your output device + volume; try headphones.
- Run `audx doctor` — it lists detected audio devices.

**My controller isn't in `audx midi list`**
- Re-seat the USB cable; some controllers need a moment after plugging in.
- Close other music apps (Ableton, GarageBand) — they can grab the port
  exclusively so audx can't open it.
- On Push 2, pick the first/"Live" port name.

**There's a delay between hitting a pad and the sound**
- Some latency is normal. Measure and note your round-trip:
  `audx rec --calibrate`.
- Close other heavy apps; use wired headphones rather than Bluetooth (Bluetooth
  adds noticeable lag).

**It played a weird drum for that pad**
- In drums mode, non-standard pads fall back to a drum based on the note, so the
  mapping is "always something" rather than "always the same". Use a controller's
  drum/GM mode for the classic layout, or `--chromatic` for pitched play.

---

Have fun. The whole point of audx is that you can plug in, hit a pad, and be
making music in ten seconds — kids very much included.
