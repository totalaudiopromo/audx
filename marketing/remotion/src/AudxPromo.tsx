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

// calm, consistent easing — restraint over flourish
const ease = Easing.bezier(0.4, 0, 0.2, 1);

/** Smooth eased 0→1→0 for a scene window. */
function band(
  f: number,
  inA: number,
  inB: number,
  outA: number,
  outB: number
): number {
  return (
    interpolate(f, [inA, inB], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: ease,
    }) *
    interpolate(f, [outA, outB], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: ease,
    })
  );
}

/** Blend two #rrggbb colours by t∈[0,1] (flat per-frame, not a CSS gradient). */
function mix(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

// ── persistent frame: a quiet passe-partout + wordmark ────────────────────────

const Frame: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: MONO }}>
    <div
      style={{
        position: "absolute",
        inset: 64,
        border: `1px solid ${COLORS.line}`,
      }}
    />
    <div
      style={{
        position: "absolute",
        top: 90,
        left: 96,
        color: COLORS.inkDim,
        fontSize: 24,
        letterSpacing: 2,
      }}
    >
      audx
    </div>
    <div
      style={{
        position: "absolute",
        top: 90,
        right: 96,
        color: COLORS.grey,
        fontSize: 22,
        letterSpacing: 2,
      }}
    >
      terminal-native daw
    </div>
  </AbsoluteFill>
);

// ── hero ──────────────────────────────────────────────────────────────────────

const Hero: React.FC = () => {
  const f = useCurrentFrame();
  const o = band(f, 6, 34, 84, 108);
  const y = interpolate(f, [6, 40], [18, 0], {
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
      <div
        style={{ textAlign: "center", transform: `translateY(${y}px)` }}
      >
        <div
          style={{
            color: COLORS.ink,
            fontSize: 92,
            fontWeight: 600,
            lineHeight: 1.16,
            letterSpacing: -1,
          }}
        >
          code your music.
          <br />
          own your sound.
        </div>
        <div
          style={{
            marginTop: 40,
            display: "inline-block",
            borderTop: `1px solid ${COLORS.line}`,
            paddingTop: 28,
            color: COLORS.inkDim,
            fontSize: 28,
            letterSpacing: 0.5,
          }}
        >
          a digital audio workstation you play from the keyboard
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── the sequencer (monochrome LED matrix) ─────────────────────────────────────

const LABEL_W = 230;
const CELL = 62;
const GAP = 12;

const Sequencer: React.FC = () => {
  const f = useCurrentFrame();
  const o = band(f, 84, 112, 500, 524);

  const stepPos = f / FPS_PER_STEP;
  const colF = ((stepPos % STEPS) + STEPS) % STEPS;
  const gridW = STEPS * CELL + (STEPS - 1) * GAP;
  const y = interpolate(f, [84, 118], [22, 0], {
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
      <div style={{ transform: `translateY(${y}px)` }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: 26,
            color: COLORS.inkDim,
            fontSize: 24,
            letterSpacing: 1,
          }}
        >
          <span>sequencer</span>
          <span style={{ color: COLORS.grey }}>124 bpm · synth kit · no samples</span>
        </div>

        <div style={{ position: "relative" }}>
          {/* thin precise playhead rule */}
          <div
            style={{
              position: "absolute",
              left: LABEL_W + colF * (CELL + GAP) + CELL / 2 - 1,
              top: -10,
              width: 2,
              height: beat.tracks.length * (CELL + GAP) + 8,
              background: COLORS.accent,
              opacity: 0.9,
            }}
          />
          {beat.tracks.map((track) => (
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
                  paddingRight: 26,
                  textAlign: "right",
                  color: COLORS.inkDim,
                  fontSize: 25,
                }}
              >
                {track.name}
              </div>
              <div style={{ display: "flex", gap: GAP }}>
                {track.steps.map((on, col) => {
                  let d = colF - col;
                  if (d < 0) d += STEPS;
                  const fresh = Math.exp(-d / 1.3); // 1 just under playhead → 0
                  const beatCol = col % 4 === 0;
                  // inactive: hairline square. active: off-white, amber at the play head.
                  const fill = on
                    ? mix(COLORS.ink, COLORS.accent, fresh)
                    : "transparent";
                  const opacity = on ? 0.3 + fresh * 0.7 : 1;
                  return (
                    <div
                      key={col}
                      style={{
                        width: CELL,
                        height: CELL,
                        borderRadius: 3,
                        background: fill,
                        opacity,
                        boxShadow: on
                          ? "none"
                          : `inset 0 0 0 1px ${beatCol ? "#2e2e29" : "#1a1a18"}`,
                      }}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <Scope width={LABEL_W + gridW} />
      </div>
    </AbsoluteFill>
  );
};

// ── flat waveform scope ───────────────────────────────────────────────────────

const Scope: React.FC<{ width: number }> = ({ width }) => {
  const f = useCurrentFrame();
  const H = 132;
  const mid = H / 2;
  const n = beat.waveform.length;
  const playX = (Math.min(f, beat.audioDurationFrames) / beat.audioDurationFrames) * width;

  const line = (sign: number) =>
    beat.waveform
      .map((p, i) => {
        const x = (i / (n - 1)) * width;
        const y = mid + sign * p * (mid - 6);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <svg
      width={width}
      height={H}
      style={{ display: "block", marginTop: 34, overflow: "visible" }}
    >
      <clipPath id="played">
        <rect x="0" y="0" width={playX} height={H} />
      </clipPath>
      {[1, -1].map((s) => (
        <path key={s} d={line(s)} stroke={COLORS.line} strokeWidth={1.5} fill="none" />
      ))}
      <g clipPath="url(#played)">
        {[1, -1].map((s) => (
          <path key={s} d={line(s)} stroke={COLORS.ink} strokeWidth={1.5} fill="none" />
        ))}
      </g>
      <line x1={playX} x2={playX} y1={2} y2={H - 2} stroke={COLORS.accent} strokeWidth={2} />
    </svg>
  );
};

// ── CTA ───────────────────────────────────────────────────────────────────────

const CTA: React.FC = () => {
  const f = useCurrentFrame();
  const o = band(f, 508, 536, 999, 1000);
  const y = interpolate(f, [508, 544], [18, 0], {
    extrapolateRight: "clamp",
    easing: ease,
  });
  const caret = f % 30 < 15 ? 1 : 0; // discrete blink, not a fade
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: o,
        fontFamily: MONO,
      }}
    >
      <div style={{ textAlign: "center", transform: `translateY(${y}px)` }}>
        <div style={{ color: COLORS.ink, fontSize: 60, fontWeight: 600 }}>
          open a terminal. hit play.
        </div>
        <div
          style={{
            marginTop: 40,
            display: "inline-block",
            border: `1px solid ${COLORS.line}`,
            padding: "22px 40px",
            fontSize: 38,
            color: COLORS.ink,
          }}
        >
          <span style={{ color: COLORS.accent }}>$</span> pip install audx
          <span style={{ opacity: caret, color: COLORS.accent }}> ▌</span>
        </div>
        <div
          style={{
            color: COLORS.grey,
            fontSize: 24,
            marginTop: 44,
            letterSpacing: 1,
          }}
        >
          github.com/totalaudiopromo/audx
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── composition ───────────────────────────────────────────────────────────────

export const AudxPromo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <Audio src={staticFile("audx-beat.wav")} />
      <Frame />
      <Hero />
      <Sequencer />
      <CTA />
    </AbsoluteFill>
  );
};
