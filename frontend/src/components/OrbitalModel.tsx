import { useEffect, useRef } from "react";
import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  Float32BufferAttribute,
  Mesh,
  MeshBasicMaterial,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  Scene,
  SphereGeometry,
  TorusGeometry,
  WebGLRenderer,
} from "three";

type OrbitalModelProps = { reducedMotion: boolean };

export function OrbitalModel({ reducedMotion }: OrbitalModelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene  = new Scene();
    const camera = new PerspectiveCamera(40, 1, 0.1, 50);
    camera.position.set(0, 0, 5);

    // Nucleus
    const nucleus = new Mesh(
      new SphereGeometry(0.22, 32, 32),
      new MeshBasicMaterial({ color: new Color(0x40e0ff) }),
    );
    scene.add(nucleus);

    // Nucleus glow particles
    const glowGeom = new BufferGeometry();
    const glowPos  = new Float32Array(60 * 3);
    for (let i = 0; i < glowPos.length; i += 3) {
      const r = 0.22 + Math.random() * 0.18;
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      glowPos[i]     = r * Math.sin(phi) * Math.cos(theta);
      glowPos[i + 1] = r * Math.sin(phi) * Math.sin(theta);
      glowPos[i + 2] = r * Math.cos(phi);
    }
    glowGeom.setAttribute("position", new Float32BufferAttribute(glowPos, 3));
    scene.add(new Points(glowGeom, new PointsMaterial({ color: 0x60efff, size: 0.06, transparent: true, opacity: 0.7, blending: AdditiveBlending })));

    // Three orbital rings at different tilts
    const ORBITS = [
      { rx: 1.0, ry: 0.25, tiltX: 0,         tiltZ: 0,            speed: 0.0009, electronColor: 0x40e0ff },
      { rx: 1.0, ry: 0.25, tiltX: Math.PI/3,  tiltZ: Math.PI/6,   speed: 0.0013, electronColor: 0x7dd4fc },
      { rx: 1.0, ry: 0.25, tiltX: -Math.PI/4, tiltZ: -Math.PI/5,  speed: 0.0007, electronColor: 0xa78bfa },
    ];

    const rings: Mesh[] = [];
    const electrons: Mesh[] = [];
    const electronAngles = ORBITS.map(() => Math.random() * Math.PI * 2);

    ORBITS.forEach((orb, i) => {
      // Ring
      const ring = new Mesh(
        new TorusGeometry(orb.rx, 0.012, 8, 80),
        new MeshBasicMaterial({ color: new Color(orb.electronColor), transparent: true, opacity: 0.25 }),
      );
      ring.rotation.x = orb.tiltX;
      ring.rotation.z = orb.tiltZ;
      scene.add(ring);
      rings.push(ring);

      // Electron dot
      const electron = new Mesh(
        new SphereGeometry(0.065, 12, 12),
        new MeshBasicMaterial({ color: new Color(orb.electronColor) }),
      );
      scene.add(electron);
      electrons.push(electron);
      void i; // suppress unused warning
    });

    let frame = 0;
    const render = (time: number) => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) { frame = requestAnimationFrame(render); return; }
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();

      if (!reducedMotion) {
        // Gentle nucleus pulse
        const scale = 1 + 0.06 * Math.sin(time * 0.002);
        nucleus.scale.setScalar(scale);

        // Orbit electrons along each ring's local ellipse
        ORBITS.forEach((orb, i) => {
          electronAngles[i] += orb.speed;
          const a = electronAngles[i];
          // Local position on ellipse
          const lx = orb.rx * Math.cos(a);
          const ly = orb.ry * Math.sin(a) * 0.25; // flatten
          const lz = orb.rx * Math.sin(a);
          // Apply ring tilt
          const cx = orb.tiltX, cz = orb.tiltZ;
          electrons[i].position.set(
            lx * Math.cos(cz) - lz * Math.sin(cz),
            lx * Math.sin(cx) * Math.sin(cz) + ly * Math.cos(cx) - lz * Math.sin(cx) * Math.cos(cz),
            lx * Math.cos(cx) * Math.sin(cz) + ly * Math.sin(cx) + lz * Math.cos(cx) * Math.cos(cz),
          );
        });

        // Very slow scene rotation
        scene.rotation.y = time * 0.00015;
        scene.rotation.x = Math.sin(time * 0.0002) * 0.18;
      }

      renderer.render(scene, camera);
      frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frame);
      renderer.dispose();
    };
  }, [reducedMotion]);

  return (
    <canvas
      className="orbital-model-canvas"
      ref={canvasRef}
      aria-label="Animated electron orbital model"
    />
  );
}
