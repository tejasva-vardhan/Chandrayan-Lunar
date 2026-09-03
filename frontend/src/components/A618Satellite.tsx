import { useEffect, useRef } from "react";
import {
  AmbientLight,
  BoxGeometry,
  BufferGeometry,
  Color,
  ConeGeometry,
  CylinderGeometry,
  DirectionalLight,
  DoubleSide,
  Float32BufferAttribute,
  Group,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  RingGeometry,
  Scene,
  Vector3,
  WebGLRenderer,
} from "three";

type A618SatelliteProps = {
  reducedMotion: boolean;
};

/**
 * Photorealistic 3D Model of the A-618 Lunar Orbiter Spacecraft
 * Features: Gold-foil satellite bus, dual solar panel arrays, high-gain dish antenna,
 * OHRC high-resolution optical camera payload, and RCS attitude thrusters.
 */
export function A618Satellite({ reducedMotion }: A618SatelliteProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: "low-power",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new Scene();
    const camera = new PerspectiveCamera(38, 1, 0.1, 50);
    camera.position.set(0, 1.2, 4.2);
    camera.lookAt(0, 0, 0);

    // Realistic directional solar lighting on the spacecraft
    const ambientLight = new AmbientLight(0x2a384c, 2.0);
    scene.add(ambientLight);

    const sunDirLight = new DirectionalLight(0xfffaed, 3.5);
    sunDirLight.position.set(3, 4, 3);
    scene.add(sunDirLight);

    const rimLight = new DirectionalLight(0x38bdf8, 1.2);
    rimLight.position.set(-3, -2, -2);
    scene.add(rimLight);

    // Master Spacecraft Group
    const satelliteGroup = new Group();
    scene.add(satelliteGroup);

    // 1. Central Satellite Bus (Gold Foil / MLI Thermal Insulation)
    const busGeom = new BoxGeometry(0.7, 0.9, 0.7);
    const busMat = new MeshStandardMaterial({
      color: 0xe0b246, // Gold thermal MLI blanket
      metalness: 0.85,
      roughness: 0.3,
    });
    const bus = new Mesh(busGeom, busMat);
    satelliteGroup.add(bus);

    // Structural equipment deck (Titanium upper & lower decks)
    const deckMat = new MeshStandardMaterial({ color: 0x828b98, metalness: 0.9, roughness: 0.2 });
    const topDeck = new Mesh(new BoxGeometry(0.72, 0.08, 0.72), deckMat);
    topDeck.position.y = 0.46;
    satelliteGroup.add(topDeck);

    const bottomDeck = new Mesh(new BoxGeometry(0.72, 0.08, 0.72), deckMat);
    bottomDeck.position.y = -0.46;
    satelliteGroup.add(bottomDeck);

    // 2. Dual Photovoltaic Solar Array Wings (Left & Right)
    const panelMat = new MeshStandardMaterial({
      color: 0x143464, // Deep blue silicon solar cells
      metalness: 0.7,
      roughness: 0.25,
      side: DoubleSide,
    });
    const panelFrameMat = new MeshStandardMaterial({ color: 0x334155, metalness: 0.8, roughness: 0.3 });

    // Left Solar Wing
    const leftWingGroup = new Group();
    leftWingGroup.position.set(-1.15, 0, 0);

    const leftBoom = new Mesh(new CylinderGeometry(0.02, 0.02, 0.7, 8), panelFrameMat);
    leftBoom.rotation.z = Math.PI / 2;
    leftBoom.position.x = 0.45;
    leftWingGroup.add(leftBoom);

    const leftPanel = new Mesh(new BoxGeometry(1.2, 0.65, 0.02), panelMat);
    leftWingGroup.add(leftPanel);
    satelliteGroup.add(leftWingGroup);

    // Right Solar Wing
    const rightWingGroup = new Group();
    rightWingGroup.position.set(1.15, 0, 0);

    const rightBoom = new Mesh(new CylinderGeometry(0.02, 0.02, 0.7, 8), panelFrameMat);
    rightBoom.rotation.z = Math.PI / 2;
    rightBoom.position.x = -0.45;
    rightWingGroup.add(rightBoom);

    const rightPanel = new Mesh(new BoxGeometry(1.2, 0.65, 0.02), panelMat);
    rightWingGroup.add(rightPanel);
    satelliteGroup.add(rightWingGroup);

    // 3. High-Gain Parabolic Dish Antenna
    const dishGroup = new Group();
    dishGroup.position.set(0, 0.58, 0.2);
    dishGroup.rotation.x = -Math.PI / 5;

    const dishGeom = new ConeGeometry(0.38, 0.12, 24, 1, true);
    const dishMat = new MeshStandardMaterial({
      color: 0xf1f5f9,
      metalness: 0.3,
      roughness: 0.4,
      side: DoubleSide,
    });
    const dish = new Mesh(dishGeom, dishMat);
    dish.rotation.x = Math.PI;
    dishGroup.add(dish);

    // Antenna feed horn
    const feed = new Mesh(new CylinderGeometry(0.015, 0.015, 0.22, 8), panelFrameMat);
    feed.position.y = -0.12;
    dishGroup.add(feed);
    satelliteGroup.add(dishGroup);

    // 4. OHRC Optical Camera Payload Sensor (Nadir-pointing)
    const ohrcGroup = new Group();
    ohrcGroup.position.set(0, -0.54, 0);

    const lensHousing = new Mesh(new CylinderGeometry(0.12, 0.14, 0.22, 16), panelFrameMat);
    ohrcGroup.add(lensHousing);

    const lensGlass = new Mesh(
      new CylinderGeometry(0.09, 0.09, 0.02, 16),
      new MeshBasicMaterial({ color: 0x38bdf8 })
    );
    lensGlass.position.y = -0.11;
    ohrcGroup.add(lensGlass);
    satelliteGroup.add(ohrcGroup);

    // 5. Attitude Control RCS Thruster Quads
    const thrusterMat = new MeshStandardMaterial({ color: 0x475569, metalness: 0.9, roughness: 0.2 });
    const thrusterGeom = new ConeGeometry(0.03, 0.06, 8);

    const corners = [
      { x: 0.36, y: 0.38, z: 0.36, rx: 0, rz: -Math.PI / 4 },
      { x: -0.36, y: 0.38, z: 0.36, rx: 0, rz: Math.PI / 4 },
      { x: 0.36, y: -0.38, z: 0.36, rx: 0, rz: -Math.PI * 0.75 },
      { x: -0.36, y: -0.38, z: 0.36, rx: 0, rz: Math.PI * 0.75 },
    ];
    corners.forEach((c) => {
      const t = new Mesh(thrusterGeom, thrusterMat);
      t.position.set(c.x, c.y, c.z);
      t.rotation.set(c.rx, 0, c.rz);
      satelliteGroup.add(t);
    });

    // Ambient status beacon pulse
    const beaconLight = new Mesh(
      new RingGeometry(0.04, 0.08, 16),
      new MeshBasicMaterial({ color: 0x38bdf8, side: DoubleSide })
    );
    beaconLight.position.set(0, 0.48, 0.36);
    satelliteGroup.add(beaconLight);

    let frame = 0;
    const render = (time: number) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (!w || !h) {
        frame = requestAnimationFrame(render);
        return;
      }
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();

      if (!reducedMotion) {
        // Slow realistic 3D spacecraft attitude pitch and yaw
        const sec = time * 0.001;
        satelliteGroup.rotation.y = Math.sin(sec * 0.4) * 0.25 + 0.35;
        satelliteGroup.rotation.x = Math.cos(sec * 0.3) * 0.15 - 0.2;
        satelliteGroup.rotation.z = Math.sin(sec * 0.2) * 0.08;

        // Subtle solar panel sun-tracking gimbal micro-adjustment
        leftWingGroup.rotation.x = Math.sin(sec * 0.5) * 0.12;
        rightWingGroup.rotation.x = Math.sin(sec * 0.5) * 0.12;
      }

      renderer.render(scene, camera);
      frame = requestAnimationFrame(render);
    };

    frame = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frame);
      busGeom.dispose();
      busMat.dispose();
      panelMat.dispose();
      renderer.dispose();
    };
  }, [reducedMotion]);

  return (
    <canvas
      ref={canvasRef}
      className="a618-canvas"
      aria-label="A-618 Chandrayaan-2 Lunar Orbiter Spacecraft 3D Model"
    />
  );
}
