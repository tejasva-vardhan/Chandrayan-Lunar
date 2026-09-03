import { useEffect, useRef, useState } from "react";
import {
  AmbientLight,
  BoxGeometry,
  BufferGeometry,
  ConeGeometry,
  DirectionalLight,
  DoubleSide,
  Float32BufferAttribute,
  Group,
  LineBasicMaterial,
  LineLoop,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  Scene,
  Vector3,
  WebGLRenderer,
} from "three";

type A618OrbiterLayerProps = {
  reducedMotion: boolean;
};

// Major Lunar Geological Features & Maria
const LUNAR_FEATURES = [
  { name: "MARE TRANQUILLITATIS", lon: 31.4, lat: 8.5, type: "MARE" },
  { name: "MARE SERENITATIS", lon: 17.5, lat: 28.0, type: "MARE" },
  { name: "MARE IMBRIUM", lon: -15.6, lat: 32.8, type: "MARE" },
  { name: "COPERNICUS CRATER", lon: -20.0, lat: 9.6, type: "CRATER" },
  { name: "TYCHO CRATER", lon: -11.2, lat: -43.3, type: "CRATER" },
  { name: "EXP-000 SCAN FIELD", lon: 23.43, lat: 0.65, type: "TARGET" },
];

function lonLatToSphere(lonDeg: number, latDeg: number, radius: number): Vector3 {
  const phi = (90 - latDeg) * (Math.PI / 180);
  const theta = (lonDeg + 180) * (Math.PI / 180);
  return new Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

/**
 * 3D Chandrayaan Lunar Orbiter Spacecraft Layer & Lunar Geographic Landmark Labels
 */
export function A618OrbiterLayer({ reducedMotion }: A618OrbiterLayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [tagPos, setTagPos] = useState<{ x: number; y: number; visible: boolean }>({ x: 0, y: 0, visible: false });
  const [featureLabels, setFeatureLabels] = useState<{ name: string; x: number; y: number; visible: boolean; type: string }[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2.0));

    const scene = new Scene();
    const camera = new PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(0, 0, 5.0);
    camera.lookAt(0, 0, 0);

    const ambientLight = new AmbientLight(0x384c68, 2.6);
    scene.add(ambientLight);

    const sunLight = new DirectionalLight(0xfffaea, 4.2);
    sunLight.position.set(5, 3, 4);
    scene.add(sunLight);

    const rimLight = new DirectionalLight(0x38bdf8, 1.8);
    rimLight.position.set(-4, -2, -2);
    scene.add(rimLight);

    // Master Spacecraft Group (Prominent, authentic Chandrayaan-2 model)
    const orbiterGroup = new Group();
    scene.add(orbiterGroup);

    // 1. Central Satellite Bus (Gold MLI thermal insulation)
    const busMat = new MeshStandardMaterial({
      color: 0xf5b722,
      metalness: 0.88,
      roughness: 0.22,
    });
    const bus = new Mesh(new BoxGeometry(0.11, 0.14, 0.11), busMat);
    orbiterGroup.add(bus);

    // Structural equipment decks (Titanium upper & lower decks)
    const deckMat = new MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9, roughness: 0.2 });
    const topDeck = new Mesh(new BoxGeometry(0.12, 0.016, 0.12), deckMat);
    topDeck.position.y = 0.075;
    orbiterGroup.add(topDeck);

    const bottomDeck = new Mesh(new BoxGeometry(0.12, 0.016, 0.12), deckMat);
    bottomDeck.position.y = -0.075;
    orbiterGroup.add(bottomDeck);

    // 2. Dual Photovoltaic Solar Array Wings (Left & Right)
    const solarMat = new MeshStandardMaterial({
      color: 0x0284c7, // Vibrant photovoltaic blue
      metalness: 0.8,
      roughness: 0.18,
      side: DoubleSide,
    });
    const frameMat = new MeshStandardMaterial({ color: 0x1e293b, metalness: 0.85 });

    // Left Wing
    const leftWingGroup = new Group();
    leftWingGroup.position.set(-0.20, 0, 0);
    const leftBoom = new Mesh(new BoxGeometry(0.08, 0.012, 0.012), frameMat);
    leftBoom.position.x = 0.09;
    leftWingGroup.add(leftBoom);
    const leftPanel = new Mesh(new BoxGeometry(0.22, 0.11, 0.006), solarMat);
    leftWingGroup.add(leftPanel);
    orbiterGroup.add(leftWingGroup);

    // Right Wing
    const rightWingGroup = new Group();
    rightWingGroup.position.set(0.20, 0, 0);
    const rightBoom = new Mesh(new BoxGeometry(0.08, 0.012, 0.012), frameMat);
    rightBoom.position.x = -0.09;
    rightWingGroup.add(rightBoom);
    const rightPanel = new Mesh(new BoxGeometry(0.22, 0.11, 0.006), solarMat);
    rightWingGroup.add(rightPanel);
    orbiterGroup.add(rightWingGroup);

    // 3. High-Gain Parabolic Dish Antenna
    const dishMat = new MeshStandardMaterial({
      color: 0xf8fafc,
      metalness: 0.4,
      roughness: 0.25,
      side: DoubleSide,
    });
    const dish = new Mesh(new ConeGeometry(0.055, 0.018, 16, 1, true), dishMat);
    dish.position.set(0, 0.085, 0.038);
    dish.rotation.x = Math.PI * 0.85;
    orbiterGroup.add(dish);

    // 4. Optical Sensor Scan Cone (OHRC Nadir Beam sweeping lunar terrain)
    const scanConeGeom = new ConeGeometry(0.25, 0.50, 16, 1, true);
    const scanConeMat = new MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.32,
      side: DoubleSide,
    });
    const scanCone = new Mesh(scanConeGeom, scanConeMat);
    scanCone.rotation.x = Math.PI;
    scanCone.position.y = -0.25;
    orbiterGroup.add(scanCone);

    // 5. Cyan Orbit Trajectory Line around Moon (Perfect in-bounds 360° visibility)
    const trackSegs = 140;
    const trackPos = new Float32Array((trackSegs + 1) * 3);
    const orbitRadiusX = 1.22;
    const orbitRadiusY = 1.20;
    const orbitTilt = 0.28;

    for (let i = 0; i <= trackSegs; i++) {
      const theta = (i / trackSegs) * Math.PI * 2;
      const x = Math.cos(theta) * orbitRadiusX;
      const y = Math.sin(theta) * orbitRadiusY;
      trackPos[i * 3]     = x * Math.cos(orbitTilt) - y * Math.sin(orbitTilt) * 0.25;
      trackPos[i * 3 + 1] = y * Math.cos(orbitTilt);
      trackPos[i * 3 + 2] = x * Math.sin(orbitTilt) + y * 0.20;
    }

    const trackGeom = new BufferGeometry();
    trackGeom.setAttribute("position", new Float32BufferAttribute(trackPos, 3));
    const trackMat = new LineBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.55,
    });
    scene.add(new LineLoop(trackGeom, trackMat));

    let orbiterAngle = 0;
    let frameId = 0;

    const render = () => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (!width || !height) {
        frameId = requestAnimationFrame(render);
        return;
      }
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();

      if (!reducedMotion) {
        orbiterAngle += 0.012;
      }

      // Calculate position along inclined 3D orbit (guaranteed 100% inside canvas)
      const x = Math.cos(orbiterAngle) * orbitRadiusX;
      const y = Math.sin(orbiterAngle) * orbitRadiusY;
      const pos = new Vector3(
        x * Math.cos(orbitTilt) - y * Math.sin(orbitTilt) * 0.25,
        y * Math.cos(orbitTilt),
        x * Math.sin(orbitTilt) + y * 0.20
      );

      orbiterGroup.position.copy(pos);
      // Nadir point toward center (the Moon)
      orbiterGroup.lookAt(0, 0, 0);

      // Track screen position for Chandrayaan plain text label
      const screenV = pos.clone().project(camera);
      if (screenV.z < 1) {
        const sx = ((screenV.x + 1) * width) / 2;
        const sy = ((-screenV.y + 1) * height) / 2;
        setTagPos({ x: sx, y: sy, visible: true });
      } else {
        setTagPos((prev) => ({ ...prev, visible: false }));
      }

      // Project Lunar Landmark Feature Labels
      const moonR = 1.15;
      const updatedFeatures: { name: string; x: number; y: number; visible: boolean; type: string }[] = [];
      LUNAR_FEATURES.forEach((feat) => {
        const featPos = lonLatToSphere(feat.lon, feat.lat, moonR);
        // Check facing vector (front-facing towards camera at z > 0)
        if (featPos.z > 0.15) {
          const projected = featPos.clone().project(camera);
          if (projected.z < 1) {
            const fx = ((projected.x + 1) * width) / 2;
            const fy = ((-projected.y + 1) * height) / 2;
            updatedFeatures.push({
              name: feat.name,
              x: fx,
              y: fy,
              visible: true,
              type: feat.type,
            });
          }
        }
      });
      setFeatureLabels(updatedFeatures);

      renderer.render(scene, camera);
      frameId = requestAnimationFrame(render);
    };

    frameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frameId);
      bus.geometry.dispose();
      busMat.dispose();
      renderer.dispose();
    };
  }, [reducedMotion]);

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 5 }}>
      <canvas
        ref={canvasRef}
        className="a618-orbiter-canvas"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        aria-hidden="true"
      />

      {/* Clean White Plain Text Label for Chandrayaan */}
      {tagPos.visible && (
        <div
          style={{
            position: "absolute",
            left: `${tagPos.x}px`,
            top: `${tagPos.y}px`,
            transform: "translate(6px, -50%)",
            font: "600 9px 'Berkeley Mono', 'JetBrains Mono', ui-monospace, monospace",
            letterSpacing: "0.14em",
            color: "#f8fafc",
            whiteSpace: "nowrap",
            pointerEvents: "none",
          }}
        >
          CHANDRAYAAN
        </div>
      )}

      {/* Clean White 3D Pinned Lunar Surface Region & Crater Labels */}
      {featureLabels.map((feat) => (
        <div
          key={feat.name}
          style={{
            position: "absolute",
            left: `${feat.x}px`,
            top: `${feat.y}px`,
            transform: "translate(-50%, -50%)",
            font: feat.type === "TARGET" ? "600 8.5px 'Berkeley Mono', 'JetBrains Mono', ui-monospace, monospace" : "500 8px 'Berkeley Mono', 'JetBrains Mono', ui-monospace, monospace",
            letterSpacing: "0.12em",
            color: "#f8fafc",
            whiteSpace: "nowrap",
            pointerEvents: "none",
            opacity: 0.9,
          }}
        >
          {feat.name}
        </div>
      ))}
    </div>
  );
}
