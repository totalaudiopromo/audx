# audx promo video (Remotion)

A 24-second promo video for audx, built with [Remotion](https://www.remotion.dev)
(React → MP4/GIF). It animates the audx terminal aesthetic: the hook, the
10-second `pip install audx && audx demo` moment, a features grid and a closing
call to action — all in the app's warm amber / sage / pink palette.

## Run it

```bash
cd marketing/remotion
npm install

# live preview in the browser
npm run studio

# render to video (needs Chrome Headless Shell + ffmpeg, which Remotion fetches)
npm run render        # → out/audx-promo.mp4 (1920×1080, 30fps)
npm run render-gif    # → out/audx-promo.gif
npm run still         # → out/poster.png  (a single poster frame)
```

`npm run render` downloads a headless browser and an ffmpeg binary on first use,
so it needs network access and a few hundred MB of disk. The composition itself
(`src/AudxPromo.tsx`) is pure React + Remotion primitives — no external assets —
so it's easy to edit: tweak copy, colours (`src/theme.ts`) or timing
(`src/Root.tsx`) and re-render.

## Structure

```
src/
  index.ts        # registerRoot
  Root.tsx        # <Composition> — id, fps, dimensions, duration
  AudxPromo.tsx   # the video: Background, Terminal, scenes (hook/install/features/CTA)
  theme.ts        # palette + font, mirrors src/audx/config.py THEME
```

The lighter-weight animated GIF embedded in the top-level README
(`docs/assets/audx-demo.gif`) is generated separately and offline by
`scripts/make-demo-gif.py` (Pillow only — no browser/ffmpeg required).
