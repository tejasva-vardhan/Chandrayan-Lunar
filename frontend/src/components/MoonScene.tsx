import { useEffect, useRef } from "react";
import {
  AdditiveBlending,
  BoxGeometry,
  BufferGeometry,
  ConeGeometry,
  CylinderGeometry,
  DoubleSide,
  Float32BufferAttribute,
  Group,
  LineBasicMaterial,
  LineLoop,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  RingGeometry,
  Scene,
  ShaderMaterial,
  SphereGeometry,
  Vector3,
  WebGLRenderer,
} from "three";

type MoonSceneProps = {
  progress: number;
  reducedMotion: boolean;
  focusedTarget?: { lon: number; lat: number; zoomMultiplier?: number } | null;
};

type RegionMilestone = {
  progress: number;
  label: string;
  lon: number;
  lat: number;
  fov: number;
  dist: number;
};

// Region milestones tied to key scroll sections
const REGION_MILESTONES: RegionMilestone[] = [
  // 0.00: Hero - Majestic deep space lunar disc
  { progress: 0.00, label: "Global View", lon: 23.43, lat: 0.65, fov: 33, dist: 3.75 },
  // 0.18: Transitioning out of hero towards workflow
  { progress: 0.18, label: "Orbital Transition", lon: 23.43, lat: 8.0, fov: 27, dist: 3.2 },
  // 0.32: Workflow ("From Orbit to Evidence")
  { progress: 0.32, label: "Equatorial Approach", lon: 23.43, lat: 0.65, fov: 18, dist: 2.5 },
  // 0.52: Scientific Results / EXP-000 Field - EXPAND CLOSE UP on OHRC Footprint & Control Points
  { progress: 0.52, label: "OHRC Strip Scan", lon: 23.43, lat: 0.65, fov: 7.0, dist: 1.58 },
  // 0.75: Quality Certificate - EXPAND on South Pole basin and cold traps
  { progress: 0.75, label: "South Pole Basin", lon: 25.24, lat: -84.9, fov: 11.5, dist: 2.05 },
  // 1.00: Audit Trail / Report - Pull back to global overview
  { progress: 1.00, label: "Global Audit Pull", lon: 23.43, lat: 0.65, fov: 32, dist: 3.7 },
];

// Verified control points from EXP-000 on equatorial region
const CP_POINTS = [
  { lon: 23.42, lat: 0.83 },
  { lon: 23.39, lat: 0.55 },
  { lon: 23.46, lat: 0.62 },
  { lon: 23.44, lat: 0.38 },
];

// Selenographic footprint boundary of Chandrayaan-2 OHRC strip
const FOOTPRINT_POINTS = [
  { lon: 23.37, lat: 0.22 },
  { lon: 23.50, lat: 0.22 },
  { lon: 23.50, lat: 1.07 },
  { lon: 23.37, lat: 1.07 },
];

function lonLatToVec3(lon: number, lat: number, r = 1.15): Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta),
  );
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function regionAt(progress: number) {
  const clamped = Math.max(0, Math.min(1, progress));
  let idx = 0;
  for (let i = 0; i < REGION_MILESTONES.length - 1; i++) {
    if (clamped >= REGION_MILESTONES[i].progress && clamped <= REGION_MILESTONES[i + 1].progress) {
      idx = i;
      break;
    }
  }
  const a = REGION_MILESTONES[idx];
  const b = REGION_MILESTONES[idx + 1] ?? a;
  const range = b.progress - a.progress;
  const rawT = range > 0 ? (clamped - a.progress) / range : 0;
  const t = rawT * rawT * (3 - 2 * rawT);

  return {
    lon: lerp(a.lon, b.lon, t),
    lat: lerp(a.lat, b.lat, t),
    fov: lerp(a.fov, b.fov, t),
    dist: lerp(a.dist, b.dist, t),
    label: clamped > 0.42 && clamped < 0.66 ? "OHRC Inlier Field" : b.label,
  };
}

const noiseFunctions = `
float hash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float noise(vec3 p) {
  vec3 i = floor(p), f = fract(p); f = f * f * (3. - 2. * f);
  return mix(mix(mix(hash(i), hash(i + vec3(1.,0.,0.)), f.x), mix(hash(i + vec3(0.,1.,0.)), hash(i + vec3(1.,1.,0.)), f.x), f.y), mix(mix(hash(i + vec3(0.,0.,1.)), hash(i + vec3(1.,0.,1.)), f.x), mix(hash(i + vec3(0.,1.,1.)), hash(i + vec3(1.,1.,1.)), f.x), f.y), f.z);
}
float fbm(vec3 p) {
  float value = 0., amplitude = .5;
  for (int i = 0; i < 5; i++) {
    value += noise(p) * amplitude;
    p = p * 2.04 + 10.;
    amplitude *= .5;
  }
  return value;
}
`;

const vertexShader = `
varying vec3 vNormal;
varying vec3 vPosition;
${noiseFunctions}
void main() {
  vec3 direction = normalize(position);
  float relief = fbm(direction * 7.5) * .058 + noise(direction * 38.) * .016;
  vec3 displaced = position + normal * relief;
  vNormal = normalize(normalMatrix * normal);
  vPosition = direction;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.);
}`;

const fragmentShader = `
precision highp float;
varying vec3 vNormal;
varying vec3 vPosition;
${noiseFunctions}
void main() {
  vec3 n = normalize(vNormal);
  vec3 light = normalize(vec3(-.75, .35, .82));
  float diffuse = max(.04, dot(n, light));
  float terrain = fbm(vPosition * 7.5);
  float smallDetail = noise(vPosition * 52.);
  float microDetail = noise(vPosition * 120.);
  float craterField = smoothstep(.058, .0, abs(noise(vPosition * 20.) - .5));
  float microCraters = smoothstep(.03, .0, abs(noise(vPosition * 85.) - .5));

  vec3 basalt = vec3(.13, .16, .18);
  vec3 highland = vec3(.56, .59, .57);
  vec3 albedo = mix(basalt, highland, terrain * .88 + smallDetail * .18 + microDetail * .06);
  albedo *= 1. - (craterField * .38 + microCraters * .18);

  // Rim glow
  float rim = pow(1. - max(0., n.z), 3.0);
  gl_FragColor = vec4(albedo * (diffuse + .12) + vec3(.14, .24, .26) * rim, 1.);
}`;

const cpVertexShader = `
varying float vAlpha;
void main() {
  vAlpha = 1.0;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = clamp(26.0 * (280.0 / -mv.z), 10.0, 52.0);
  gl_Position  = projectionMatrix * mv;
}`;

const cpFragmentShader = `
varying float vAlpha;
void main() {
  vec2 d = gl_PointCoord - 0.5;
  float r = length(d) * 2.0;
  if (r > 1.0) discard;
  float dotCenter = smoothstep(0.32, 0.08, r);
  float ring = smoothstep(0.72, 0.86, r) * smoothstep(1.0, 0.86, r);
  float intensity = (dotCenter * 1.3 + ring * 1.8) * vAlpha;
  gl_FragColor = vec4(0.2, 0.98, 0.82, clamp(intensity, 0.0, 1.0));
}`;

export function MoonScene({ progress, reducedMotion, focusedTarget }: MoonSceneProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progressRef = useRef(progress);
  progressRef.current = progress;

  const targetRef = useRef(focusedTarget);
  targetRef.current = focusedTarget;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2.0));

    const scene = new Scene();
    const camera = new PerspectiveCamera(33, 1, 0.1, 100);
    camera.position.set(0, 0, 3.8);

    // 3D Moon mesh container
    const moonGroup = new Group();
    scene.add(moonGroup);

    // Moon mesh with relief displacement shader
    const moonMaterial = new ShaderMaterial({ vertexShader, fragmentShader });
    const moon = new Mesh(new SphereGeometry(1.15, 192, 192), moonMaterial);
    moonGroup.add(moon);

    // 3D Selenographic Grid Arcs
    const gridMat = new LineBasicMaterial({
      color: 0x22d3ee,
      transparent: true,
      opacity: 0.15,
    });
    // Latitude parallel lines
    [-45, -20, 0, 20, 45].forEach((latDeg) => {
      const latRad = latDeg * (Math.PI / 180);
      const rRing = 1.154 * Math.cos(latRad);
      const yRing = 1.154 * Math.sin(latRad);
      const ringGeom = new BufferGeometry();
      const segs = 64;
      const pts = new Float32Array((segs + 1) * 3);
      for (let i = 0; i <= segs; i++) {
        const a = (i / segs) * Math.PI * 2;
        pts[i * 3]     = Math.cos(a) * rRing;
        pts[i * 3 + 1] = yRing;
        pts[i * 3 + 2] = Math.sin(a) * rRing;
      }
      ringGeom.setAttribute("position", new Float32BufferAttribute(pts, 3));
      moonGroup.add(new LineLoop(ringGeom, gridMat));
    });

    // 3D Sensor scan footprint boundary line
    const footprintGeom = new BufferGeometry();
    const footprintPos = new Float32Array(FOOTPRINT_POINTS.length * 3);
    FOOTPRINT_POINTS.forEach((pt, i) => {
      const v = lonLatToVec3(pt.lon, pt.lat, 1.158);
      footprintPos[i * 3]     = v.x;
      footprintPos[i * 3 + 1] = v.y;
      footprintPos[i * 3 + 2] = v.z;
    });
    footprintGeom.setAttribute("position", new Float32BufferAttribute(footprintPos, 3));
    const footprintMat = new LineBasicMaterial({
      color: 0x34f5c5,
      transparent: true,
      opacity: 0.85,
      blending: AdditiveBlending,
    });
    const footprintLine = new LineLoop(footprintGeom, footprintMat);
    moonGroup.add(footprintLine);

    // 3D Vertical Laser Beacons & Targeting Pins for Verified Control Points
    const cpBeaconsGroup = new Group();
    const beaconCylinderGeom = new CylinderGeometry(0.006, 0.014, 0.45, 12);
    const beaconCylinderMat = new MeshBasicMaterial({
      color: 0x38ef7d,
      transparent: true,
      opacity: 0.85,
      blending: AdditiveBlending,
    });

    CP_POINTS.forEach((cp) => {
      const surfPos = lonLatToVec3(cp.lon, cp.lat, 1.156);
      const normal = surfPos.clone().normalize();

      const bMesh = new Mesh(beaconCylinderGeom, beaconCylinderMat);
      // Position halfway up the normal
      bMesh.position.copy(surfPos).addScaledVector(normal, 0.225);
      bMesh.quaternion.setFromUnitVectors(new Vector3(0, 1, 0), normal);
      cpBeaconsGroup.add(bMesh);
    });
    moonGroup.add(cpBeaconsGroup);

    // Control point surface markers (verified inliers)
    const cpGeom = new BufferGeometry();
    const cpPos = new Float32Array(CP_POINTS.length * 3);
    CP_POINTS.forEach((cp, i) => {
      const v = lonLatToVec3(cp.lon, cp.lat, 1.164);
      cpPos[i * 3]     = v.x;
      cpPos[i * 3 + 1] = v.y;
      cpPos[i * 3 + 2] = v.z;
    });
    cpGeom.setAttribute("position", new Float32BufferAttribute(cpPos, 3));
    const cpMat = new ShaderMaterial({
      vertexShader: cpVertexShader,
      fragmentShader: cpFragmentShader,
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
    });
    const cpPoints = new Points(cpGeom, cpMat);
    moonGroup.add(cpPoints);

    // Ambient Starfield
    const starsGeom = new BufferGeometry();
    const stars = new Float32Array(800 * 3);
    for (let i = 0; i < stars.length; i += 3) {
      stars[i]     = (Math.random() - 0.5) * 20;
      stars[i + 1] = (Math.random() - 0.5) * 14;
      stars[i + 2] = -4 - Math.random() * 6;
    }
    starsGeom.setAttribute("position", new Float32BufferAttribute(stars, 3));
    const starField = new Points(
      starsGeom,
      new PointsMaterial({
        color: 0x8be5e0,
        size: 0.016,
        transparent: true,
        opacity: 0.55,
        blending: AdditiveBlending,
      })
    );
    scene.add(starField);

    // Mouse Parallax for 3D Depth
    let mouseParallaxX = 0;
    let mouseParallaxY = 0;
    const onMouseMove = (e: MouseEvent) => {
      mouseParallaxX = (e.clientX / window.innerWidth - 0.5) * 0.18;
      mouseParallaxY = (e.clientY / window.innerHeight - 0.5) * 0.14;
    };
    window.addEventListener("mousemove", onMouseMove);

    // Smooth camera state
    let camDist = 3.75;
    let camLon = 23.43;
    let camLat = 0.65;
    let camFov = 33;
    const springK = 0.045;

    let orbiterAngle = 0;
    let frame = 0;

    const render = (time: number) => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (!width || !height) {
        frame = requestAnimationFrame(render);
        return;
      }
      renderer.setSize(width, height, false);
      camera.aspect = width / height;

      // Base target from scroll progress
      const regionTarget = regionAt(progressRef.current);
      let targetLon = regionTarget.lon;
      let targetLat = regionTarget.lat;
      let targetDist = regionTarget.dist;
      let targetFov = regionTarget.fov;

      if (targetRef.current) {
        targetLon = targetRef.current.lon;
        targetLat = targetRef.current.lat;
        targetDist = 1.46 * (targetRef.current.zoomMultiplier ?? 1.0);
        targetFov = 6.2;
      }

      // Spring smoothly toward target coordinates
      camLon += (targetLon - camLon) * springK;
      camLat += (targetLat - camLat) * springK;
      camDist += (targetDist - camDist) * springK;
      camFov += (targetFov - camFov) * springK;

      camera.fov = camFov;
      camera.updateProjectionMatrix();

      // Look directly at the target on sphere
      const lookAt = lonLatToVec3(camLon, camLat, 1.15);
      const normal = lookAt.clone().normalize();

      camera.position.copy(lookAt).addScaledVector(normal, camDist);

      // Subtle 3D mouse parallax tilt
      if (!reducedMotion) {
        camera.position.x += mouseParallaxX;
        camera.position.y += mouseParallaxY;
      }

      if (Math.abs(normal.y) > 0.92) {
        camera.up.set(0, 0, normal.y < 0 ? 1 : -1);
      } else {
        camera.up.set(0, 1, 0);
      }
      camera.lookAt(lookAt);

      // Slow planetary rotation only in deep space
      if (!reducedMotion && progressRef.current < 0.12 && !targetRef.current) {
        moon.rotation.y = time * 0.000015;
      }

      // Control points & footprint visibility
      const isResultsField = progressRef.current > 0.32 && progressRef.current < 0.72;
      const pulse = 0.55 + 0.45 * Math.sin(time * 0.004);

      if (isResultsField || targetRef.current) {
        cpPoints.visible = true;
        footprintLine.visible = true;
        cpBeaconsGroup.visible = true;
        (cpMat as ShaderMaterial).opacity = pulse;
        footprintMat.opacity = 0.4 + 0.45 * pulse;
        beaconCylinderMat.opacity = 0.5 + 0.35 * pulse;
      } else {
        cpPoints.visible = false;
        footprintLine.visible = false;
        cpBeaconsGroup.visible = false;
      }

      starField.rotation.y = reducedMotion ? 0 : time * 0.000004;
      renderer.render(scene, camera);
      frame = requestAnimationFrame(render);
    };

    frame = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("mousemove", onMouseMove);
      moon.geometry.dispose();
      moonMaterial.dispose();
      starsGeom.dispose();
      starField.material.dispose();
      cpGeom.dispose();
      cpMat.dispose();
      footprintGeom.dispose();
      footprintMat.dispose();
      renderer.dispose();
    };
  }, [reducedMotion]);

  return (
    <canvas
      className="moon-canvas"
      ref={canvasRef}
      aria-label="Three-dimensional interactive lunar globe with scroll-driven expansion"
    />
  );
}