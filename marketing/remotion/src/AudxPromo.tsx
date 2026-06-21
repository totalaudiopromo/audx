import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS, MONO } from "./theme";

// ── small building blocks ─────────────────────────────────────────────────────

const Background: React.FC = () => (
  <AbsoluteFill
    style={{
      backgroundColor: COLORS.bg,
      backgroundImage: `radial-gradient(1200px 600px at 82% -10%, rgba(212,165,116,0.12), transparent),
                        radial-gradient(900px 600px at 0% 12%, rgba(168,192,135,0.08), transparent)`,
    }}
  />
);

const FadeUp: React.FC<{ delay?: number; children: React.ReactNode }> = ({
  delay = 0,
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 200 } });
  return (
    <div style={{ opacity: s, transform: `translateY(${(1 - s) * 28}px)` }}>
      {children}
    </div>
  );
};

// A faithful terminal window that types `lines` out over time.
const Terminal: React.FC<{
  title: string;
  lines: { text: string; color: string; bold?: boolean }[];
  startFrame?: number;
  cps?: number; // characters per second
}> = ({ title, lines, startFrame = 0, cps = 38 }) => {
  const frame = useCurrentFrame() - startFrame;
  const { fps } = useVideoConfig();
  const charsShown = Math.max(0, Math.floor((frame / fps) * cps));

  let budget = charsShown;
  return (
    <div
      style={{
        width: 1180,
        borderRadius: 18,
        backgroundColor: COLORS.surface,
        boxShadow: "0 40px 120px rgba(0,0,0,0.55)",
        border: `1px solid ${COLORS.border}`,
        overflow: "hidden",
        fontFamily: MONO,
      }}
    >
      <div
        style={{
          height: 56,
          backgroundColor: COLORS.bar,
          display: "flex",
          alignItems: "center",
          paddingLeft: 22,
          gap: 12,
          borderBottom: `1px solid ${COLORS.border}`,
        }}
      >
        {[COLORS.red, COLORS.amber, COLORS.sage].map((c) => (
          <div
            key={c}
            style={{ width: 16, height: 16, borderRadius: 8, backgroundColor: c }}
          />
        ))}
        <span style={{ color: COLORS.muted, marginLeft: 16, fontSize: 22 }}>
          {title}
        </span>
      </div>
      <div style={{ padding: "30px 34px", fontSize: 30, lineHeight: 1.5 }}>
        {lines.map((line, i) => {
          const take = Math.max(0, Math.min(line.text.length, budget));
          budget -= line.text.length;
          if (take <= 0 && budget < 0) return <div key={i}>&nbsp;</div>;
          return (
            <div
              key={i}
              style={{ color: line.color, fontWeight: line.bold ? 700 : 400 }}
            >
              {line.text.slice(0, take) || " "}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ── scenes ────────────────────────────────────────────────────────────────────

const SceneHook: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <div style={{ textAlign: "center", fontFamily: MONO }}>
      <FadeUp>
        <div style={{ color: COLORS.amber, fontSize: 40, letterSpacing: 6 }}>
          ▸ audx
        </div>
      </FadeUp>
      <FadeUp delay={12}>
        <div
          style={{
            color: COLORS.text,
            fontSize: 96,
            fontWeight: 800,
            marginTop: 18,
            lineHeight: 1.1,
          }}
        >
          Code your music.
          <br />
          <span style={{ color: COLORS.pink }}>Own your sound.</span>
        </div>
      </FadeUp>
      <FadeUp delay={26}>
        <div style={{ color: COLORS.muted, fontSize: 34, marginTop: 28 }}>
          A terminal-native DAW. No cloud. No mouse. No lock-in.
        </div>
      </FadeUp>
    </div>
  </AbsoluteFill>
);

const SceneInstall: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <FadeUp>
      <Terminal
        title="make a beat in 10 seconds"
        cps={32}
        lines={[
          { text: "$ pip install audx", color: COLORS.text, bold: true },
          { text: "Successfully installed audx-0.3.0", color: COLORS.muted },
          { text: "", color: COLORS.muted },
          { text: "$ audx demo loop.wav", color: COLORS.text, bold: true },
          { text: "  audx · demo", color: COLORS.amber, bold: true },
          { text: "    ♪ kick     kick 4/4", color: COLORS.muted },
          { text: "    ♪ sub      sub e(3,8) | tune -5st", color: COLORS.muted },
          { text: "    ♪ clap     clap 2/8", color: COLORS.muted },
          { text: "    ♪ hats     hh 16x8 | swing 12%", color: COLORS.muted },
          { text: "    ♪ bass     bass e(3,8) | tune -7st", color: COLORS.muted },
          {
            text: "  ✓ rendered 4 bars @ 124 BPM → loop.wav",
            color: COLORS.sage,
            bold: true,
          },
        ]}
      />
    </FadeUp>
    <FadeUp delay={20}>
      <div style={{ color: COLORS.muted, fontSize: 30, marginTop: 34, fontFamily: MONO }}>
        No samples. No audio hardware. No config.
      </div>
    </FadeUp>
  </AbsoluteFill>
);

const Feature: React.FC<{ title: string; body: string; delay: number }> = ({
  title,
  body,
  delay,
}) => (
  <FadeUp delay={delay}>
    <div
      style={{
        width: 760,
        backgroundColor: COLORS.surface,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 16,
        padding: "26px 30px",
        fontFamily: MONO,
      }}
    >
      <div style={{ color: COLORS.amber, fontSize: 34, fontWeight: 700 }}>
        {title}
      </div>
      <div style={{ color: COLORS.muted, fontSize: 26, marginTop: 10 }}>{body}</div>
    </div>
  </FadeUp>
);

const SceneFeatures: React.FC = () => (
  <AbsoluteFill
    style={{
      justifyContent: "center",
      alignItems: "center",
      gap: 22,
    }}
  >
    <Feature
      title="Pattern DSL"
      body="kick 4/4 · hh 16x8 · perc e(5,16,2) · clap [1.0.1.1]"
      delay={0}
    />
    <Feature
      title="Built-in synth kit"
      body="20 procedural voices — drums, sub bass, plucks, stabs. Zero samples."
      delay={10}
    />
    <Feature
      title="Render · MIDI · live-code"
      body="Stems to WAV, export MIDI, hot-reload projects, A/B/C/D slots."
      delay={20}
    />
  </AbsoluteFill>
);

const SceneCTA: React.FC = () => {
  const frame = useCurrentFrame();
  const pulse = interpolate(frame % 60, [0, 30, 60], [1, 0.55, 1]);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center", fontFamily: MONO }}>
        <FadeUp>
          <div style={{ color: COLORS.text, fontSize: 64, fontWeight: 800 }}>
            Open a terminal. Hit play.
          </div>
        </FadeUp>
        <FadeUp delay={12}>
          <div
            style={{
              marginTop: 36,
              display: "inline-block",
              backgroundColor: COLORS.surface,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 14,
              padding: "22px 38px",
              fontSize: 38,
              color: COLORS.text,
            }}
          >
            <span style={{ color: COLORS.pink }}>$ </span>
            pip install audx
            <span style={{ opacity: pulse, color: COLORS.amber }}> ▌</span>
          </div>
        </FadeUp>
        <FadeUp delay={24}>
          <div style={{ color: COLORS.sage, fontSize: 28, marginTop: 40, fontStyle: "italic" }}>
            Code is the controller. Sound is the canvas. Terminal is the dimension.
          </div>
        </FadeUp>
        <FadeUp delay={32}>
          <div style={{ color: COLORS.muted, fontSize: 26, marginTop: 18 }}>
            github.com/totalaudiopromo/audx
          </div>
        </FadeUp>
      </div>
    </AbsoluteFill>
  );
};

// ── timeline ──────────────────────────────────────────────────────────────────

export const AudxPromo: React.FC = () => {
  return (
    <AbsoluteFill>
      <Background />
      <Sequence durationInFrames={120}>
        <SceneHook />
      </Sequence>
      <Sequence from={120} durationInFrames={240}>
        <SceneInstall />
      </Sequence>
      <Sequence from={360} durationInFrames={180}>
        <SceneFeatures />
      </Sequence>
      <Sequence from={540} durationInFrames={180}>
        <SceneCTA />
      </Sequence>
    </AbsoluteFill>
  );
};
