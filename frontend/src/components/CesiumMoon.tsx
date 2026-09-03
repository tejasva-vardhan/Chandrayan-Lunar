import { useEffect, useRef, useState, type ReactNode } from "react";
import { Cesium3DTileset, Ellipsoid, HeadingPitchRange, Ion, Viewer } from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

type CesiumMoonProps = { children: ReactNode; reducedMotion: boolean };

const moonAssetId = 2684829;

export function CesiumMoon({ children, reducedMotion }: CesiumMoonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const token = import.meta.env.VITE_CESIUM_ION_TOKEN?.trim();
  const [available, setAvailable] = useState(Boolean(token));

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !token) return;
    const mount = container;
    let viewer: Viewer | undefined;
    let disposed = false;
    let removeOrbit: (() => void) | undefined;

    async function loadMoon() {
      try {
        Ion.defaultAccessToken = token;
        Ellipsoid.default = Ellipsoid.MOON;
        viewer = new Viewer(mount, {
          globe: false,
          animation: false,
          baseLayerPicker: false,
          fullscreenButton: false,
          geocoder: false,
          homeButton: false,
          infoBox: false,
          navigationHelpButton: false,
          sceneModePicker: false,
          selectionIndicator: false,
          timeline: false,
          // Without an alpha-enabled WebGL context, scene.backgroundColor's
          // alpha channel below has nothing to composite against and the
          // canvas paints solid black wherever there's no geometry — that's
          // the hard-edged black box behind the Moon. premultipliedAlpha:
          // false keeps the moon's own colors from darkening as they blend
          // with the transparent page background behind them.
          contextOptions: { webgl: { alpha: true, premultipliedAlpha: false } },
        });
        viewer.resolutionScale = Math.min(window.devicePixelRatio * 1.45, 2.35);
        const tileset = await Cesium3DTileset.fromIonAssetId(moonAssetId);
        if (disposed) return;
        tileset.maximumScreenSpaceError = 2;
        viewer.scene.primitives.add(tileset);
        viewer.scene.backgroundColor.alpha = 0;
        // Cesium's own widgets.css opts the viewer container and canvas
        // into an opaque black background regardless of the context/scene
        // settings above — that has to be overridden separately (see
        // App.css's .cesium-moon rules) or the box reappears.
        // enableRotate stays on so drag-to-orbit still works if this ever
        // renders inside a container with pointer-events enabled. In the
        // current layout (App.tsx's .moon-layer sets pointer-events: none,
        // since the moon is a decorative, scroll-driven element sitting
        // behind floating content) drag input never reaches the canvas —
        // only the scroll listener below drives the camera. Flip
        // .moon-layer to pointer-events: auto if manual dragging should
        // come back.
        viewer.scene.screenSpaceCameraController.enableRotate = true;
        viewer.scene.screenSpaceCameraController.enableZoom = false;
        // A Moon-scale stand-off reveals the curved limb instead of a flat close-up tile.
        viewer.camera.flyToBoundingSphere(tileset.boundingSphere, {
          duration: 0,
          offset: new HeadingPitchRange(0.42, -0.34, 6_200_000),
        });
        let lastScrollY = window.scrollY;
        let requestedRotation = 0;
        let appliedRotation = 0;
        const scrollOrbitSensitivity = .00038;
        const maximumOrbitTurn = .9;
        const onScroll = () => {
          const scrollDelta = window.scrollY - lastScrollY;
          lastScrollY = window.scrollY;
          // Downward and upward scroll deltas retain opposite signs by design.
          requestedRotation = Math.max(-maximumOrbitTurn, Math.min(maximumOrbitTurn, requestedRotation + scrollDelta * scrollOrbitSensitivity));
        };
        const orbitMoon = () => {
          if (reducedMotion) return;
          const nextStep = (requestedRotation - appliedRotation) * .16;
          if (Math.abs(nextStep) < .000001) return;
          viewer?.camera.rotateRight(nextStep);
          appliedRotation += nextStep;
        };
        window.addEventListener("scroll", onScroll, { passive: true });
        viewer.scene.postRender.addEventListener(orbitMoon);
        removeOrbit = () => {
          window.removeEventListener("scroll", onScroll);
          viewer?.scene.postRender.removeEventListener(orbitMoon);
        };
      } catch (error) {
        console.warn("Cesium Moon could not load. Confirm that this Cesium ion account has access to asset 2684829 and that the token permits asset access.", error);
        setAvailable(false);
      }
    }

    void loadMoon();
    return () => { disposed = true; removeOrbit?.(); viewer?.destroy(); };
  }, [reducedMotion, token]);

  if (!available) return <>{children}</>;
  return <div className="cesium-moon" ref={containerRef} aria-label="Cesium Moon terrain from NASA LRO data" />;
}
