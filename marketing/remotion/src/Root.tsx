import { Composition } from "remotion";
import { AudxPromo } from "./AudxPromo";

// 20s promo at 30fps = 600 frames, locked to the 124 BPM beat in public/.
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="AudxPromo"
      component={AudxPromo}
      durationInFrames={600}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
