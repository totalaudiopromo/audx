import { Composition } from "remotion";
import { AudxPromo } from "./AudxPromo";

// 24s promo at 30fps = 720 frames.
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="AudxPromo"
      component={AudxPromo}
      durationInFrames={720}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
