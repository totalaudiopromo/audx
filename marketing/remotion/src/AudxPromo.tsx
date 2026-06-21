import {
  AbsoluteFill,
  Audio,
  Easing,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { COLORS, MONO } from "./theme";
import beat from "./beat-data.json";

const FPS = beat.fps;
const FPS_PER_STEP = beat.framesPerStep;
const STEPS = beat.stepsPerBar;

// ── timing helpers ────────────────────────────────────────────────────────────

const ease = Easing.inOut(Easing.cubic);

/** Smooth 0→1→0 opacity for a scene window with eased fades. */
function band(
  frame: number,
  inStart: number,
  inEnd: number,
  outStart: number,
  outEnd: number
): number {
  return (
    interpolate(frame, [inStart, inEnd], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: ease,
    }) *
    interpolate(frame, [outStart, outEnd], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: ease,
    })
  );
}

/** Level of a track at `frame`: 1 on a hit, decaying exponentially after. */
function trackLevel(hits: number[], frame: number, decay = 9): number {
  let last = -1e9;
  for (const h of hits) {
    if (h <= frame && h > last) last = h;
    if (h > frame) break;
  }
  const dt = frame - last;
  return dt < 0 ? 0 : Math.exp(-dt / decay);
}

const envAt = (frame: number): number =>
  beat.envelope[Math.max(0, Math.min(beat.envelope.length - 1, frame))] ?? 0;

// ── background ────────────────────────────────────────────────────────────────

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const e = envAt(frame);
  // neon glows that breathe with the beat — magenta top-right, cyan lower-left
  const glow = 0.1 + e * 0.22;
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(1500px 820px at 80% ${
            -10 + e * 8
          }%, rgba(255,47,176,${glow}), transparent),
            radial-gradient(1200px 760px at 2% 18%, rgba(52,245,255,${
              0.08 + e * 0.16
            }), transparent),
            radial-gradient(900px 600px at 50% 120%, rgba(184,107,255,${
              0.06 + e * 0.12
            }), transparent)`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage: "radial-gradient(circle at 50% 45%, black, transparent 75%)",
        }}
      />
    </AbsoluteFill>
  );
};

// ── hero ──────────────────────────────────────────────────────────────────────

const Hero: React.FC = () => {
  const frame = useCurrentFrame();
  const o = band(frame, 4, 28, 78, 100);
  const rise = interpolate(frame, [4, 30], [26, 0], {
    extrapolateRight: "clamp",
    easing: ease,
  });
  const e = envAt(frame);
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: o,
        fontFamily: MONO,
      }}
    >
      <div style={{ textAlign: "center", transform: `translateY(${rise}px)` }}>
        <div
          style={{
            color: COLORS.amber,
            fontSize: 40,
            letterSpacing: 10,
            textShadow: `0 0 ${10 + e * 30}px rgba(212,165,116,0.7)`,
          }}
        >
          ▸ audx
        </div>
        <div
          style={{
            color: COLORS.text,
            fontSize: 104,
            fontWeight: 800,
            lineHeight: 1.08,
            marginTop: 20,
          }}
        >
          Code your music.
          <br />
          <span style={{ color: COLORS.pink }}>Own your sound.</span>
        </div>
        <div style={{ color: COLORS.muted, fontSize: 34, marginTop: 30 }}>
          A terminal-native DAW that makes sound the second you install it.
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── the live sequencer (the star) ─────────────────────────────────────────────

const LABEL_W = 360;
const CELL = 70;
const GAP = 10;
const VU_W = 130;

const Sequencer: React.FC = () => {
  const frame = useCurrentFrame();
  const o = band(frame, 78, 104, 498, 522);

  // continuous play position in steps, wrapping each bar
  const stepPos = frame / FPS_PER_STEP;
  const colF = ((stepPos % STEPS) + STEPS) % STEPS;

  const gridW = STEPS * CELL + (STEPS - 1) * GAP;
  const rise = interpolate(frame, [78, 110], [40, 0], {
    extrapolateRight: "clamp",
    easing: ease,
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: o,
        fontFamily: MONO,
      }}
    >
      <div style={{ transform: `translateY(${rise}px)` }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 22,
            color: COLORS.muted,
            fontSize: 26,
          }}
        >
          <span style={{ color: COLORS.amber, fontWeight: 700 }}>audx · live</span>
          <span>124 BPM</span>
          <span style={{ color: COLORS.sage }}>▍ synth kit · no samples</span>
        </div>

        <div
          style={{
            position: "relative",
            width: LABEL_W + gridW + VU_W + 48,
            padding: "26px 24px",
            borderRadius: 18,
            background: "rgba(30,30,30,0.72)",
            border: `1px solid ${COLORS.border}`,
            boxShadow: "0 40px 120px rgba(0,0,0,0.5)",
          }}
        >
          {/* moving playhead column */}
          <div
            style={{
              position: "absolute",
              left: 24 + LABEL_W + colF * (CELL + GAP) - 4,
              top: 18,
              width: CELL + 8,
              bottom: 18,
              borderRadius: 12,
              background:
                "linear-gradient(rgba(52,245,255,0.26), rgba(52,245,255,0.04))",
              border: "1px solid rgba(52,245,255,0.5)",
              boxShadow: "0 0 40px rgba(52,245,255,0.25)",
            }}
          />
          {beat.tracks.map((track) => {
            const level = trackLevel(track.hits, frame);
            return (
              <div
                key={track.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  height: CELL,
                  marginBottom: GAP,
                }}
              >
                <div
                  style={{
                    width: LABEL_W,
                    paddingRight: 22,
                    textAlign: "right",
                    fontSize: 26,
                  }}
                >
                  <span style={{ color: track.color, fontWeight: 700 }}>
                    {track.name}
                  </span>
                </div>
                <div style={{ display: "flex", gap: GAP }}>
                  {track.steps.map((on, col) => {
                    // distance (in steps) since the playhead last crossed this column
                    let d = colF - col;
                    if (d < 0) d += STEPS;
                    const fresh = Math.exp(-d / 1.6); // 1 just-played → 0
                    const lit = on ? 0.32 + fresh * 0.68 : 0.05;
                    const scale = on ? 1 + fresh * 0.14 : 1;
                    const beatCol = col % 4 === 0;
                    return (
                      <div
                        key={col}
                        style={{
                          width: CELL,
                          height: CELL,
                          borderRadius: 12,
                          transform: `scale(${scale})`,
                          background: on ? track.color : "rgba(255,255,255,0.04)",
                          opacity: lit,
                          border: beatCol
                            ? "1px solid rgba(255,255,255,0.16)"
                            : "1px solid rgba(255,255,255,0.06)",
                          boxShadow:
                            on && fresh > 0.12
                              ? `0 0 ${10 + fresh * 46}px ${track.color}`
                              : "none",
                        }}
                      />
                    );
                  })}
                </div>
                {/* per-track VU */}
                <div
                  style={{
                    width: VU_W,
                    marginLeft: 24,
                    height: 16,
                    borderRadius: 8,
                    background: "rgba(255,255,255,0.05)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${level * 100}%`,
                      height: "100%",
                      background: track.color,
                      borderRadius: 8,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <Scope />
      </div>
    </AbsoluteFill>
  );
};

// ── waveform scope under the grid ─────────────────────────────────────────────

const Scope: React.FC = () => {
  const frame = useCurrentFrame();
  const W = 1700;
  const H = 150;
  const mid = H / 2;
  const n = beat.waveform.length;
  const playX =
    (Math.min(frame, beat.audioDurationFrames) / beat.audioDurationFrames) * W;

  const path = beat.waveform
    .map((p, i) => {
      const x = (i / (n - 1)) * W;
      const y = mid - p * (mid - 6);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const pathB = beat.waveform
    .map((p, i) => {
      const x = (i / (n - 1)) * W;
      const y = mid + p * (mid - 6);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg
      width={W}
      height={H}
      style={{ display: "block", margin: "30px auto 0", overflow: "visible" }}
    >
      <defs>
        <linearGradient id="played" x1="0" x2="1">
          <stop offset="0" stopColor={COLORS.cyan} />
          <stop offset="0.5" stopColor={COLORS.violet} />
          <stop offset="1" stopColor={COLORS.magenta} />
        </linearGradient>
        <clipPath id="reveal">
          <rect x="0" y="0" width={playX} height={H} />
        </clipPath>
      </defs>
      <path d={path} stroke={COLORS.border} strokeWidth={2} fill="none" />
      <path d={pathB} stroke={COLORS.border} strokeWidth={2} fill="none" />
      <g clipPath="url(#reveal)">
        <path d={path} stroke="url(#played)" strokeWidth={2.5} fill="none" />
        <path d={pathB} stroke="url(#played)" strokeWidth={2.5} fill="none" />
      </g>
      <line
        x1={playX}
        x2={playX}
        y1={0}
        y2={H}
        stroke={COLORS.cyan}
        strokeWidth={3}
      />
    </svg>
  );
};

// ── CTA ───────────────────────────────────────────────────────────────────────

const CTA: React.FC = () => {
  const frame = useCurrentFrame();
  const o = band(frame, 506, 532, 999, 1000);
  const rise = interpolate(frame, [506, 540], [30, 0], {
    extrapolateRight: "clamp",
    easing: ease,
  });
  const blink = Math.abs(Math.sin((frame / FPS) * Math.PI * 1.4));
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: o,
        fontFamily: MONO,
      }}
    >
      <div style={{ textAlign: "center", transform: `translateY(${rise}px)` }}>
        <div style={{ color: COLORS.text, fontSize: 70, fontWeight: 800 }}>
          Open a terminal. Hit play.
        </div>
        <div
          style={{
            marginTop: 38,
            display: "inline-block",
            background: "rgba(30,30,30,0.85)",
            border: `1px solid ${COLORS.border}`,
            borderRadius: 14,
            padding: "24px 42px",
            fontSize: 42,
            color: COLORS.text,
          }}
        >
          <span style={{ color: COLORS.pink }}>$ </span>
          pip install audx
          <span style={{ opacity: blink, color: COLORS.amber }}> ▌</span>
        </div>
        <div
          style={{
            color: COLORS.sage,
            fontSize: 27,
            marginTop: 42,
            fontStyle: "italic",
          }}
        >
          Code is the controller. Sound is the canvas. Terminal is the dimension.
        </div>
        <div style={{ color: COLORS.muted, fontSize: 26, marginTop: 16 }}>
          github.com/totalaudiopromo/audx
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── composition ───────────────────────────────────────────────────────────────

export const AudxPromo: React.FC = () => {
  return (
    <AbsoluteFill>
      <Audio src={staticFile("audx-beat.wav")} />
      <Background />
      <Hero />
      <Sequencer />
      <CTA />
    </AbsoluteFill>
  );
};
