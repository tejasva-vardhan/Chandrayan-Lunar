import { useEffect, useRef } from "react";
import {
  AdditiveBlending,
  BufferGeometry,
  Float32BufferAttribute,
  LineBasicMaterial,
  LineLoop,
  Mesh,
  PerspectiveCamera,
  Points,
  PointsMaterial,
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
  // Smoothstep easing for cinematic camera glide
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
  float relief = fbm(direction * 7.5) * .055 + noise(direction * 38.) * .015;
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

  vec3 basalt = vec3(.14, .17, .19);
  vec3 highland = vec3(.55, .58, .56);
  vec3 albedo = mix(basalt, highland, terrain * .88 + smallDetail * .18 + microDetail * .06);
  albedo *= 1. - (craterField * .36 + microCraters * .18);

  // Subtle atmospheric / solar rim illumination
  float rim = pow(1. - max(0., n.z), 3.0);
  gl_FragColor = vec4(albedo * (diffuse + .12) + vec3(.12, .22, .24) * rim, 1.);
}`;

const cpVertexShader = `
varying float vAlpha;
void main() {
  vAlpha = 1.0;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  // Crisp point sizing based on camera distance
  gl_PointSize = clamp(24.0 * (280.0 / -mv.z), 10.0, 48.0);
  gl_Position  = projectionMatrix * mv;
}`;

const cpFragmentShader = `
varying float vAlpha;
void main() {
  vec2 d = gl_PointCoord - 0.5;
  float r = length(d) * 2.0;
  if (r > 1.0) discard;
  // Radar target reticle: bright center dot with concentric pulse ring
  float dotCenter = smoothstep(0.32, 0.08, r);
  float ring = smoothstep(0.72, 0.86, r) * smoothstep(1.0, 0.86, r);
  float intensity = (dotCenter * 1.2 + ring * 1.6) * vAlpha;
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

    // Moon mesh
    const moonMaterial = new ShaderMaterial({ vertexShader, fragmentShader });
    const moon = new Mesh(new SphereGeometry(1.15, 192, 192), moonMaterial);
    scene.add(moon);

    // Sensor scan footprint boundary line
    const footprintGeom = new BufferGeometry();
    const footprintPos = new Float32Array(FOOTPRINT_POINTS.length * 3);
    FOOTPRINT_POINTS.forEach((pt, i) => {
      const v = lonLatToVec3(pt.lon, pt.lat, 1.156);
      footprintPos[i * 3] = v.x;
      footprintPos[i * 3 + 1] = v.y;
      footprintPos[i * 3 + 2] = v.z;
    });
    footprintGeom.setAttribute("position", new Float32BufferAttribute(footprintPos, 3));
    const footprintMat = new LineBasicMaterial({
      color: 0x34f5c5,
      transparent: true,
      opacity: 0.75,
      blending: AdditiveBlending,
    });
    const footprintLine = new LineLoop(footprintGeom, footprintMat);
    scene.add(footprintLine);

    // Control point markers (verified inliers)
    const cpGeom = new BufferGeometry();
    const cpPos = new Float32Array(CP_POINTS.length * 3);
    CP_POINTS.forEach((cp, i) => {
      const v = lonLatToVec3(cp.lon, cp.lat, 1.162);
      cpPos[i * 3] = v.x;
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
    scene.add(cpPoints);

    // Ambient deep-space starfield
    const starsGeom = new BufferGeometry();
    const stars = new Float32Array(800 * 3);
    for (let i = 0; i < stars.length; i += 3) {
      stars[i] = (Math.random() - 0.5) * 18;
      stars[i + 1] = (Math.random() - 0.5) * 12;
      stars[i + 2] = -4 - Math.random() * 6;
    }
    starsGeom.setAttribute("position", new Float32BufferAttribute(stars, 3));
    const starField = new Points(
      starsGeom,
      new PointsMaterial({
        color: 0x8be5e0,
        size: 0.015,
        transparent: true,
        opacity: 0.5,
        blending: AdditiveBlending,
      }),
    );
    scene.add(starField);

    // Smooth camera state
    let camDist = 3.75;
    let camLon = 23.43;
    let camLat = 0.65;
    let camFov = 33;

    const springK = 0.045;

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

      // If a specific target coordinate is hovered / focused
      if (targetRef.current) {
        targetLon = targetRef.current.lon;
        targetLat = targetRef.current.lat;
        targetDist = 1.48 * (targetRef.current.zoomMultiplier ?? 1.0);
        targetFov = 6.2;
      }

      // Spring smoothly toward target coordinates
      camLon += (targetLon - camLon) * springK;
      camLat += (targetLat - camLat) * springK;
      camDist += (targetDist - camDist) * springK;
      camFov += (targetFov - camFov) * springK;

      camera.fov = camFov;
      camera.updateProjectionMatrix();

      // Look directly at the target lon/lat on the sphere surface
      const lookAt = lonLatToVec3(camLon, camLat, 1.15);
      const normal = lookAt.clone().normalize();

      // Camera stands directly above this portion of the Moon
      camera.position.copy(lookAt).addScaledVector(normal, camDist);

      // Prevent gimbal flip near polar extremes
      if (Math.abs(normal.y) > 0.92) {
        camera.up.set(0, 0, normal.y < 0 ? 1 : -1);
      } else {
        camera.up.set(0, 1, 0);
      }
      camera.lookAt(lookAt);

      // Subtle slow planetary rotation only in deep space / hero view
      if (!reducedMotion && progressRef.current < 0.12 && !targetRef.current) {
        moon.rotation.y = time * 0.000015;
      }

      // Control points & footprint visibility & pulse
      const isResultsField = progressRef.current > 0.32 && progressRef.current < 0.72;
      const pulse = 0.55 + 0.45 * Math.sin(time * 0.0035);

      if (isResultsField || targetRef.current) {
        cpPoints.visible = true;
        footprintLine.visible = true;
        (cpMat as ShaderMaterial).opacity = pulse;
        footprintMat.opacity = 0.35 + 0.4 * pulse;
      } else {
        cpPoints.visible = false;
        footprintLine.visible = false;
      }

      starField.rotation.y = reducedMotion ? 0 : time * 0.000004;
      renderer.render(scene, camera);
      frame = requestAnimationFrame(render);
    };

    frame = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frame);
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