import { useEffect, useRef, useState } from "react";
import {
  ACESFilmicToneMapping,
  AdditiveBlending,
  AmbientLight,
  BufferGeometry,
  CanvasTexture,
  CatmullRomCurve3,
  Color,
  CylinderGeometry,
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
  PointLight,
  Points,
  PointsMaterial,
  Raycaster,
  RingGeometry,
  Scene,
  SphereGeometry,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";

type SolarSystemEntranceProps = {
  onEnterLunarMission: () => void;
  reducedMotion: boolean;
};

// ============================================================================
// NASA KEPLERIAN ORBITAL MECHANICS (True Solar System Elements)
// ============================================================================

type KeplerianPlanet = {
  name: string;
  label: string;
  size: number;
  // Real Keplerian orbital elements (scaled for viewport visualization)
  a: number;         // Semi-major axis (AU scale)
  e: number;         // Orbital Eccentricity (0 = circle, >0 = ellipse)
  inclination: number; // Inclination angle in radians relative to ecliptic
  omega: number;     // Longitude of ascending node (rad)
  perihelion: number;// Argument of periapsis (rad)
  period: number;    // Orbital period (years / speed factor)
  meanAnomaly0: number; // Mean anomaly for real alignment (Sep 2026)
  orbitColor: number;
  textureFactory?: () => CanvasTexture;
  color?: number;
  hasRing?: boolean;
};

// Pronounced visual Keplerian orbital parameters matching NASA Eyes visualization
const KEPLERIAN_PLANETS: KeplerianPlanet[] = [
  {
    name: "Mercury",
    label: "MERCURY",
    size: 0.55,
    a: 8.5,
    e: 0.38, // Distinct, clearly visible elliptical elongation
    inclination: 0.12,
    omega: 0.84,
    perihelion: 1.35,
    period: 0.24,
    meanAnomaly0: 2.1,
    orbitColor: 0x8fa0b0,
    color: 0x9b948a,
  },
  {
    name: "Venus",
    label: "VENUS",
    size: 0.92,
    a: 13.5,
    e: 0.22,
    inclination: 0.06,
    omega: 1.33,
    perihelion: 2.29,
    period: 0.615,
    meanAnomaly0: 4.8,
    orbitColor: 0xd6a858,
    color: 0xe5be7e,
  },
  {
    name: "Earth",
    label: "EARTH",
    size: 1.25,
    a: 20.0,
    e: 0.28, // Clear, prominent ellipse with off-center Sun focus
    inclination: 0.0,
    omega: 0.0,
    perihelion: 1.79,
    period: 1.0,
    meanAnomaly0: 4.15,
    orbitColor: 0x22d3ee,
    textureFactory: createEarthTexture,
  },
  {
    name: "Mars",
    label: "MARS",
    size: 0.75,
    a: 28.5,
    e: 0.34, // Prominent Mars ellipse
    inclination: 0.04,
    omega: 0.86,
    perihelion: 5.0,
    period: 1.88,
    meanAnomaly0: 0.95,
    orbitColor: 0xdd6538,
    textureFactory: createMarsTexture,
  },
  {
    name: "Jupiter",
    label: "JUPITER",
    size: 2.5,
    a: 42.0,
    e: 0.30, // Wide elliptical path
    inclination: 0.025,
    omega: 1.75,
    perihelion: 0.25,
    period: 11.86,
    meanAnomaly0: 5.4,
    orbitColor: 0xe0a068,
    textureFactory: createJupiterTexture,
  },
  {
    name: "Saturn",
    label: "SATURN",
    size: 2.1,
    a: 56.0,
    e: 0.32,
    inclination: 0.045,
    omega: 1.98,
    perihelion: 5.86,
    period: 29.45,
    meanAnomaly0: 1.2,
    orbitColor: 0xebd39a,
    textureFactory: createSaturnTexture,
    hasRing: true,
  },
];

/** Computes true 3D coordinates on a Keplerian elliptical orbit with off-center focus */
function computeKeplerianOrbitPoint(planet: KeplerianPlanet, anomaly: number): Vector3 {
  // Polar Keplerian orbit equation: r = a * (1 - e^2) / (1 + e * cos(theta))
  const r = (planet.a * (1 - planet.e * planet.e)) / (1 + planet.e * Math.cos(anomaly));
  
  // Position in orbital plane with perihelion rotation
  const xOrb = r * Math.cos(anomaly + planet.perihelion);
  const zOrb = r * Math.sin(anomaly + planet.perihelion);
  
  // 3D rotation by inclination and ascending node
  const x = xOrb * Math.cos(planet.omega) - zOrb * Math.cos(planet.inclination) * Math.sin(planet.omega);
  const y = zOrb * Math.sin(planet.inclination);
  const z = xOrb * Math.sin(planet.omega) + zOrb * Math.cos(planet.inclination) * Math.cos(planet.omega);
  
  return new Vector3(x, y, z);
}

function createSunTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 1024; canvas.height = 512;
  const ctx = canvas.getContext("2d")!;
  
  // Pitch black base for maximum contrast
  ctx.fillStyle = "#030000"; 
  ctx.fillRect(0, 0, 1024, 512);

  // Heavy black/dark crimson magma patches
  ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
  for (let i = 0; i < 300; i++) {
    ctx.beginPath();
    ctx.ellipse(Math.random() * 1024, Math.random() * 512, 20 + Math.random() * 80, 10 + Math.random() * 40, Math.random() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }
  
  // Layer 1: Deep red ambient glow (sparser so black shows through)
  for (let i = 0; i < 200; i++) {
    const x = Math.random() * 1024;
    const y = Math.random() * 512;
    const r = 20 + Math.random() * 50;
    const grad = ctx.createRadialGradient(x, y, 0, x, y, r);
    grad.addColorStop(0, "rgba(100, 5, 0, 0.45)"); // Deeper dark red
    grad.addColorStop(1, "rgba(100, 5, 0, 0)");
    ctx.fillStyle = grad;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }

  // Layer 2: Fiery red/orange turbulent veins (thinner, less dense)
  ctx.lineWidth = 1.5;
  for (let i = 0; i < 400; i++) {
    ctx.strokeStyle = `rgba(${120 + Math.random() * 80}, ${10 + Math.random() * 30}, 0, 0.3)`;
    ctx.beginPath();
    const startX = Math.random() * 1024;
    const startY = Math.random() * 512;
    ctx.moveTo(startX, startY);
    ctx.bezierCurveTo(
      startX + (Math.random() - 0.5) * 80, startY + (Math.random() - 0.5) * 80,
      startX + (Math.random() - 0.5) * 80, startY + (Math.random() - 0.5) * 80,
      startX + (Math.random() - 0.5) * 120, startY + (Math.random() - 0.5) * 120
    );
    ctx.stroke();
  }

  // Layer 3: Sparse yellow/orange plasma hotspots
  for (let i = 0; i < 150; i++) {
    const x = Math.random() * 1024;
    const y = Math.random() * 512;
    const w = 3 + Math.random() * 20;
    const h = 2 + Math.random() * 8;
    const angle = Math.random() * Math.PI;
    
    const grad = ctx.createRadialGradient(x, y, 0, x, y, w);
    grad.addColorStop(0, "rgba(230, 100, 0, 0.7)"); // Darker orange-yellow
    grad.addColorStop(0.5, "rgba(200, 40, 0, 0.5)"); // Deep orange-red
    grad.addColorStop(1, "rgba(255, 0, 0, 0)");
    
    ctx.fillStyle = grad;
    ctx.beginPath(); 
    ctx.ellipse(x, y, w, h, angle, 0, Math.PI * 2); 
    ctx.fill();
  }
  
  const texture = new CanvasTexture(canvas);
  texture.anisotropy = 4;
  return texture;
}

function createBlackHoleDiskTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 512; canvas.height = 512;
  const ctx = canvas.getContext("2d")!;
  
  const cx = 256;
  const cy = 256;
  
  // Radial gradient mimicking the intense accretion disk from the image
  // Colors from the image: Deep crimson/purple edge -> Fiery red -> Bright orange -> White hot inner edge
  const grad = ctx.createRadialGradient(cx, cy, 100, cx, cy, 256);
  grad.addColorStop(0.0, "rgba(255, 255, 255, 1.0)");   // White hot inner
  grad.addColorStop(0.1, "rgba(255, 230, 150, 0.95)"); // Intense yellow-white
  grad.addColorStop(0.3, "rgba(255, 100, 20, 0.9)");   // Bright fiery orange
  grad.addColorStop(0.6, "rgba(200, 20, 0, 0.8)");     // Deep crimson red
  grad.addColorStop(0.85, "rgba(80, 0, 20, 0.5)");     // Dark purple-red
  grad.addColorStop(1.0, "rgba(0, 0, 0, 0.0)");        // Fade out
  
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 512, 512);

  // Add some angular streak noise for the plasma swirling effect
  for(let i=0; i<300; i++) {
    const r = 120 + Math.random() * 120;
    const angle = Math.random() * Math.PI * 2;
    const length = 0.1 + Math.random() * 0.4;
    const thick = 1 + Math.random() * 3;
    
    ctx.beginPath();
    ctx.arc(cx, cy, r, angle, angle + length);
    ctx.lineWidth = thick;
    ctx.strokeStyle = Math.random() > 0.5 ? "rgba(255,255,255,0.4)" : "rgba(255,150,0,0.3)";
    ctx.stroke();
  }

  const texture = new CanvasTexture(canvas);
  return texture;
}

function createEarthTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 1024; canvas.height = 512;
  const ctx = canvas.getContext("2d")!;
  const oceanGrad = ctx.createLinearGradient(0, 0, 0, 512);
  oceanGrad.addColorStop(0, "#082347"); oceanGrad.addColorStop(0.5, "#0d437a"); oceanGrad.addColorStop(1, "#061833");
  ctx.fillStyle = oceanGrad; ctx.fillRect(0, 0, 1024, 512);

  ctx.fillStyle = "#2d5a32";
  for (let i = 0; i < 260; i++) {
    const x = Math.random() * 1024; const y = 90 + Math.random() * 332;
    ctx.beginPath(); ctx.arc(x, y, 20 + Math.random() * 70, 0, Math.PI * 2); ctx.fill();
  }
  ctx.fillStyle = "#8a7342";
  for (let i = 0; i < 120; i++) {
    const x = Math.random() * 1024; const y = 140 + Math.random() * 232;
    ctx.beginPath(); ctx.arc(x, y, 12 + Math.random() * 45, 0, Math.PI * 2); ctx.fill();
  }
  ctx.fillStyle = "#e6f2ff"; ctx.fillRect(0, 0, 1024, 38); ctx.fillRect(0, 474, 1024, 38);
  ctx.fillStyle = "rgba(255, 255, 255, 0.48)";
  for (let i = 0; i < 160; i++) {
    ctx.beginPath(); ctx.ellipse(Math.random() * 1024, 40 + Math.random() * 432, 30 + Math.random() * 90, 8 + Math.random() * 22, (Math.random() - 0.5) * 0.7, 0, Math.PI * 2); ctx.fill();
  }
  return new CanvasTexture(canvas);
}

function createMoonTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 512; canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#9ba0a6"; ctx.fillRect(0, 0, 512, 256);
  ctx.fillStyle = "#52575d";
  [{ x: 180, y: 90, r: 55 }, { x: 260, y: 110, r: 42 }, { x: 340, y: 95, r: 38 }, { x: 220, y: 160, r: 48 }].forEach((m) => {
    ctx.beginPath(); ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2); ctx.fill();
  });
  for (let i = 0; i < 180; i++) {
    ctx.fillStyle = "rgba(235, 240, 245, 0.7)"; ctx.beginPath(); ctx.arc(Math.random() * 512, Math.random() * 256, 1.5 + Math.random() * 7, 0, Math.PI * 2); ctx.fill();
  }
  return new CanvasTexture(canvas);
}

function createJupiterTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 512; canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  const colors = ["#4a321f", "#c29b74", "#825838", "#e3cca8", "#593b22", "#d4b087", "#8c5f3b", "#ebd7b7"];
  colors.forEach((col, i) => { ctx.fillStyle = col; ctx.fillRect(0, i * 32, 512, 33); });
  ctx.fillStyle = "#ad3d21"; ctx.beginPath(); ctx.ellipse(320, 160, 32, 18, -0.1, 0, Math.PI * 2); ctx.fill();
  return new CanvasTexture(canvas);
}

function createSaturnTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 512; canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  const colors = ["#a8926d", "#dfcb9f", "#c4ad82", "#ebd7ae", "#ba9f72", "#dfcb9f"];
  colors.forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(0, i * 42, 512, 43); });
  return new CanvasTexture(canvas);
}

function createSaturnRingTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 256; canvas.height = 1;
  const ctx = canvas.getContext("2d")!;
  const grad = ctx.createLinearGradient(0, 0, 256, 0);
  grad.addColorStop(0.0, "rgba(180, 160, 125, 0.0)");
  grad.addColorStop(0.15, "rgba(220, 200, 160, 0.85)");
  grad.addColorStop(0.60, "rgba(225, 205, 165, 0.95)");
  grad.addColorStop(0.65, "rgba(10, 8, 5, 0.02)");
  grad.addColorStop(0.72, "rgba(195, 175, 140, 0.8)");
  grad.addColorStop(1.0, "rgba(160, 140, 110, 0.0)");
  ctx.fillStyle = grad; ctx.fillRect(0, 0, 256, 1);
  return new CanvasTexture(canvas);
}

function createMarsTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 512; canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#c7532b"; ctx.fillRect(0, 0, 512, 256);
  ctx.fillStyle = "#692913";
  for (let i = 0; i < 50; i++) {
    ctx.beginPath(); ctx.ellipse(Math.random() * 512, 50 + Math.random() * 156, 20 + Math.random() * 50, 8 + Math.random() * 20, (Math.random() - 0.5) * 0.5, 0, Math.PI * 2); ctx.fill();
  }
  ctx.fillStyle = "#f5f9fc"; ctx.fillRect(0, 0, 512, 18); ctx.fillRect(0, 238, 512, 18);
  return new CanvasTexture(canvas);
}

export function SolarSystemEntrance({ onEnterLunarMission, reducedMotion }: SolarSystemEntranceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [hudLabels, setHudLabels] = useState<{ [key: string]: { x: number; y: number; visible: boolean; label: string; color: string } }>({});
  const [moonScreenPos, setMoonScreenPos] = useState<{ x: number; y: number; visible: boolean }>({ x: 0, y: 0, visible: false });
  const [isZooming, setIsZooming] = useState(false);
  const [zoomFade, setZoomFade] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const [hoveredBodyName, setHoveredBodyName] = useState<string | null>(null);

  const triggerZoomRef = useRef<(() => void) | null>(null);

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
    renderer.toneMapping = ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.35;

    const scene = new Scene();
    // Matching exact NASA Eyes high-inclination view
    const camera = new PerspectiveCamera(40, 1, 0.5, 700);
    camera.position.set(0, 46, 68);
    camera.lookAt(0, 0, 0);

    const ambientLight = new AmbientLight(0x1a2638, 0.4); // Darker ambient for deeper shadows
    scene.add(ambientLight);

    const sunLight = new PointLight(0xfffaed, 8.5, 800, 0.25); // Stronger point light
    scene.add(sunLight);

    const dirLight = new DirectionalLight(0xfffaea, 1.5);
    dirLight.position.set(0, 5, 0);
    scene.add(dirLight);

    // Deep Space Starfield
    const starGeom = new BufferGeometry();
    const starCount = 3200;
    const starPos = new Float32Array(starCount * 3);
    const starColors = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount * 3; i += 3) {
      starPos[i]     = (Math.random() - 0.5) * 550;
      starPos[i + 1] = (Math.random() - 0.5) * 380;
      starPos[i + 2] = (Math.random() - 0.5) * 550;

      const c = Math.random();
      if (c > 0.65) {
        starColors[i] = 0.65; starColors[i + 1] = 0.88; starColors[i + 2] = 1.0;
      } else if (c > 0.35) {
        starColors[i] = 1.0; starColors[i + 1] = 0.98; starColors[i + 2] = 0.92;
      } else {
        starColors[i] = 1.0; starColors[i + 1] = 0.78; starColors[i + 2] = 0.5;
      }
    }
    starGeom.setAttribute("position", new Float32BufferAttribute(starPos, 3));
    starGeom.setAttribute("color", new Float32BufferAttribute(starColors, 3));
    const starField = new Points(
      starGeom,
      new PointsMaterial({ size: 0.75, vertexColors: true, transparent: true, opacity: 0.85, blending: AdditiveBlending })
    );
    scene.add(starField);

    // Radiant Sun in center
    const sunGeom = new SphereGeometry(3.6, 36, 36);
    const sunTex = createSunTexture();
    const sunMat = new MeshStandardMaterial({ 
      map: sunTex,
      emissiveMap: sunTex,
      emissive: 0xff6600, // Brighter orange/red emissive
      emissiveIntensity: 1.8, // Much higher intensity for extreme brightness
      roughness: 0.9,
    });
    const sun = new Mesh(sunGeom, sunMat);
    scene.add(sun);

    const sunGlow = new Mesh(
      new SphereGeometry(4.8, 32, 32),
      new MeshBasicMaterial({ color: 0xff6600, transparent: true, opacity: 0.45, blending: AdditiveBlending })
    );
    scene.add(sunGlow);

    // Supermassive Black Hole in the deep distance
    const bhGroup = new Group();
    bhGroup.position.set(150, 60, -220); // Brought closer for prominence

    // The Event Horizon (Perfectly black sphere)
    const bhGeom = new SphereGeometry(20, 32, 32); // Scaled up
    const bhMat = new MeshBasicMaterial({ color: 0x000000 });
    const blackHole = new Mesh(bhGeom, bhMat);
    bhGroup.add(blackHole);
    
    const bhTex = createBlackHoleDiskTexture();

    // Accretion Disk
    const diskGeom = new RingGeometry(22, 60, 64);
    const diskMat = new MeshBasicMaterial({
      map: bhTex,
      color: 0xffffff, // White base so the texture colors shine through
      side: DoubleSide,
      transparent: true,
      opacity: 0.95,
      blending: AdditiveBlending,
    });
    const disk = new Mesh(diskGeom, diskMat);
    disk.rotation.x = Math.PI / 2.2;
    disk.rotation.y = Math.PI / 8;
    bhGroup.add(disk);

    // Photon Ring / Gravitational Lensing Halo (Spherical wrap mimicking the image)
    const haloGeom = new SphereGeometry(22.5, 32, 32);
    const haloMat = new MeshBasicMaterial({
      map: bhTex,
      color: 0xffffff,
      transparent: true,
      opacity: 0.55,
      blending: AdditiveBlending,
      side: DoubleSide
    });
    const halo = new Mesh(haloGeom, haloMat);
    bhGroup.add(halo);

    scene.add(bhGroup);

    // Real Keplerian Orbital Ellipses & Bodies
    const planetObjects: {
      group: Group;
      mesh: Mesh;
      def: KeplerianPlanet;
      currentAnomaly: number;
    }[] = [];

    let earthGroup: Group | null = null;
    let moonMesh: Mesh | null = null;
    let moonBeaconGroup: Group | null = null;
    const interactiveTargets: Mesh[] = [];

    KEPLERIAN_PLANETS.forEach((def) => {
      // Draw Exact Keplerian Elliptical Orbit Curve
      const orbitSegments = 160;
      const orbitPoints: Vector3[] = [];
      for (let i = 0; i <= orbitSegments; i++) {
        const anomaly = (i / orbitSegments) * Math.PI * 2;
        orbitPoints.push(computeKeplerianOrbitPoint(def, anomaly));
      }
      const orbitGeom = new BufferGeometry().setFromPoints(orbitPoints);
      const orbitMat = new LineBasicMaterial({
        color: def.orbitColor,
        transparent: true,
        opacity: def.name === "Earth" ? 0.75 : 0.45,
      });
      scene.add(new LineLoop(orbitGeom, orbitMat));

      const pGroup = new Group();
      scene.add(pGroup);

      let pMat: MeshStandardMaterial;
      if (def.textureFactory) {
        pMat = new MeshStandardMaterial({
          map: def.textureFactory(),
          roughness: 0.7,
          metalness: 0.15,
        });
      } else {
        pMat = new MeshStandardMaterial({
          color: new Color(def.color),
          roughness: 0.6,
          metalness: 0.2,
        });
      }

      const pMesh = new Mesh(new SphereGeometry(def.size, 32, 32), pMat);
      pMesh.userData = { name: def.name };
      pGroup.add(pMesh);
      interactiveTargets.push(pMesh);

      // Earth-Moon Sub-System
      if (def.name === "Earth") {
        earthGroup = pGroup;

        // Atmosphere halo
        const atmoGeom = new SphereGeometry(def.size * 1.15, 24, 24);
        const atmoMat = new MeshBasicMaterial({
          color: 0x4dd0e1,
          transparent: true,
          opacity: 0.25,
          blending: AdditiveBlending,
        });
        pGroup.add(new Mesh(atmoGeom, atmoMat));

        // The Moon
        const moonMat = new MeshStandardMaterial({
          map: createMoonTexture(),
          roughness: 0.85,
          metalness: 0.05,
        });
        moonMesh = new Mesh(new SphereGeometry(0.48, 24, 24), moonMat);
        moonMesh.userData = { name: "Moon" };
        scene.add(moonMesh);
        interactiveTargets.push(moonMesh);

        // Moon Orbit circle line around Earth
        const moonOrbitSegs = 64;
        const moonOrbitPos = new Float32Array((moonOrbitSegs + 1) * 3);
        const moonRadius = 3.6;
        for (let i = 0; i <= moonOrbitSegs; i++) {
          const theta = (i / moonOrbitSegs) * Math.PI * 2;
          moonOrbitPos[i * 3]     = Math.cos(theta) * moonRadius;
          moonOrbitPos[i * 3 + 1] = 0;
          moonOrbitPos[i * 3 + 2] = Math.sin(theta) * moonRadius;
        }
        const moonOrbitGeom = new BufferGeometry();
        moonOrbitGeom.setAttribute("position", new Float32BufferAttribute(moonOrbitPos, 3));
        const moonOrbitMat = new LineBasicMaterial({
          color: 0x38ef7d,
          transparent: true,
          opacity: 0.6,
        });
        pGroup.add(new LineLoop(moonOrbitGeom, moonOrbitMat));

        // 3D Laser Beacon on Moon
        moonBeaconGroup = new Group();
        const beaconGeom = new CylinderGeometry(0.04, 0.08, 4.5, 12);
        const beaconMat = new MeshBasicMaterial({
          color: 0x38ef7d,
          transparent: true,
          opacity: 0.85,
          blending: AdditiveBlending,
        });
        const beacon = new Mesh(beaconGeom, beaconMat);
        beacon.position.y = 2.25;
        moonBeaconGroup.add(beacon);

        const beaconRingGeom = new RingGeometry(0.6, 0.8, 32);
        const beaconRingMat = new MeshBasicMaterial({
          color: 0xc9ff5e,
          side: DoubleSide,
          transparent: true,
          opacity: 0.9,
          blending: AdditiveBlending,
        });
        const beaconRing = new Mesh(beaconRingGeom, beaconRingMat);
        beaconRing.rotation.x = Math.PI / 2;
        beaconRing.position.y = 0.5;
        moonBeaconGroup.add(beaconRing);

        scene.add(moonBeaconGroup);
      }

      // Saturn Rings
      if (def.hasRing) {
        const ringGeom = new RingGeometry(def.size * 1.35, def.size * 2.5, 64);
        const ringMat = new MeshBasicMaterial({
          map: createSaturnRingTexture(),
          side: DoubleSide,
          transparent: true,
          opacity: 0.9,
        });
        const ring = new Mesh(ringGeom, ringMat);
        ring.rotation.x = Math.PI * 0.45;
        pGroup.add(ring);
      }

      planetObjects.push({
        group: pGroup,
        mesh: pMesh,
        def,
        currentAnomaly: def.meanAnomaly0,
      });
    });

    // Spacecraft Transfer Orbit Line (Like Lucy / Chandrayaan orbital path in NASA Eyes)
    const transferPointsCount = 80;
    const transferPts: Vector3[] = [];
    for (let i = 0; i < transferPointsCount; i++) {
      const t = i / (transferPointsCount - 1);
      const angle = t * Math.PI * 2.6 - 0.6;
      const r = 20.0 - t * 3.8;
      const y = Math.sin(t * Math.PI) * 1.6;
      transferPts.push(new Vector3(Math.cos(angle) * r, y, Math.sin(angle) * r));
    }
    const transferCurve = new CatmullRomCurve3(transferPts);
    const transferGeom = new BufferGeometry().setFromPoints(transferCurve.getPoints(120));
    const transferMat = new LineBasicMaterial({
      color: 0xa8c2c7,
      transparent: true,
      opacity: 0.45,
    });
    scene.add(new LineLoop(transferGeom, transferMat));

    // 3D Drag Orbit Controls
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    let orbitAzimuth = 0;
    let orbitElevation = 0.42;
    let orbitDistance = 64;

    let targetAzimuth = 0;
    let targetElevation = 0.42;
    let targetDistance = 64;

    const onPointerDown = (e: MouseEvent) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const onPointerMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mouseVec = new Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );

      const raycaster = new Raycaster();
      raycaster.setFromCamera(mouseVec, camera);
      const intersects = raycaster.intersectObjects(interactiveTargets);
      if (intersects.length > 0) {
        const hitName = intersects[0].object.userData?.name;
        setHoveredBodyName(hitName ?? null);
        setIsHovered(hitName === "Moon" || hitName === "Earth");
      } else {
        setHoveredBodyName(null);
        setIsHovered(false);
      }

      if (isDragging) {
        const deltaX = e.clientX - prevMouseX;
        const deltaY = e.clientY - prevMouseY;
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;
        targetAzimuth += deltaX * 0.006;
        targetElevation = Math.max(0.08, Math.min(Math.PI / 2 - 0.05, targetElevation - deltaY * 0.005));
      }
    };

    const onPointerUp = () => { isDragging = false; };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      targetDistance = Math.max(20, Math.min(125, targetDistance + e.deltaY * 0.05));
    };

    canvas.addEventListener("mousedown", onPointerDown);
    window.addEventListener("mousemove", onPointerMove);
    window.addEventListener("mouseup", onPointerUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });

    // Smooth Line-Path Dive Transition
    let zooming = false;
    let zoomStartTime = 0;
    const zoomDuration = 2000;
    let startCamPos = camera.position.clone();
    let startLookAt = new Vector3(0, 0, 0);

    triggerZoomRef.current = () => {
      if (zooming) return;
      zooming = true;
      zoomStartTime = performance.now();
      startCamPos = camera.position.clone();
      setIsZooming(true);
    };

    let moonAngle = 0;
    let frameId = 0;

    const render = (time: number) => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (!width || !height) {
        frameId = requestAnimationFrame(render);
        return;
      }
      renderer.setSize(width, height, false);
      camera.aspect = width / height;

      // Animate Planets along real Keplerian Elliptical Orbits
      planetObjects.forEach((item) => {
        if (!zooming) {
          // Kepler's speed: faster when closer (period inversely proportional)
          item.currentAnomaly += (0.003 / item.def.period);
        }
        const pos = computeKeplerianOrbitPoint(item.def, item.currentAnomaly);
        item.group.position.copy(pos);
        item.mesh.rotation.y += 0.012;
      });

      // Position Moon around Earth
      let moonWorldPos = new Vector3();
      if (earthGroup && moonMesh) {
        if (!zooming) {
          moonAngle += 0.024;
        }
        const moonRadius = 3.6;
        moonMesh.position.x = earthGroup.position.x + Math.cos(moonAngle) * moonRadius;
        moonMesh.position.y = earthGroup.position.y + Math.sin(moonAngle * 0.5) * 0.4;
        moonMesh.position.z = earthGroup.position.z + Math.sin(moonAngle) * moonRadius;
        moonMesh.rotation.y += 0.008;
        moonMesh.getWorldPosition(moonWorldPos);

        if (moonBeaconGroup) {
          moonBeaconGroup.position.copy(moonWorldPos);
          moonBeaconGroup.rotation.y = time * 0.003;
        }
      }

      // Project NASA Eyes HUD labels tracking 3D bodies
      const updatedLabels: { [key: string]: { x: number; y: number; visible: boolean; label: string; color: string } } = {};

      const sunV = new Vector3(0, 0, 0).project(camera);
      if (sunV.z < 1) {
        updatedLabels["Sun"] = {
          x: ((sunV.x + 1) * width) / 2,
          y: ((-sunV.y + 1) * height) / 2,
          visible: true,
          label: "SUN",
          color: "#fffa70",
        };
      }

      const bhV = new Vector3(150, 60, -220).project(camera);
      if (bhV.z < 1) {
        updatedLabels["BlackHole"] = {
          x: ((bhV.x + 1) * width) / 2,
          y: ((-bhV.y + 1) * height) / 2,
          visible: true,
          label: "SGR A* [BLACK HOLE]",
          color: "#ff7700",
        };
      }

      planetObjects.forEach((item) => {
        const temp = new Vector3();
        item.group.getWorldPosition(temp);
        temp.project(camera);
        if (temp.z < 1) {
          updatedLabels[item.def.name] = {
            x: ((temp.x + 1) * width) / 2,
            y: ((-temp.y + 1) * height) / 2,
            visible: true,
            label: item.def.label,
            color: item.def.name === "Earth" ? "#22d3ee" : "#d6d9e0",
          };
        }
      });

      // Moon Target Label
      if (moonMesh) {
        const temp = moonWorldPos.clone().project(camera);
        if (temp.z < 1) {
          const sx = ((temp.x + 1) * width) / 2;
          const sy = ((-temp.y + 1) * height) / 2;
          setMoonScreenPos({ x: sx, y: sy, visible: true });
        } else {
          setMoonScreenPos((prev) => ({ ...prev, visible: false }));
        }
      }

      setHudLabels(updatedLabels);

      // Camera Handling
      if (!zooming) {
        orbitAzimuth += (targetAzimuth - orbitAzimuth) * 0.08;
        orbitElevation += (targetElevation - orbitElevation) * 0.08;
        orbitDistance += (targetDistance - orbitDistance) * 0.08;

        if (!isDragging && !reducedMotion) {
          targetAzimuth += 0.0006;
        }

        const camX = orbitDistance * Math.cos(orbitElevation) * Math.sin(orbitAzimuth);
        const camY = orbitDistance * Math.sin(orbitElevation);
        const camZ = orbitDistance * Math.cos(orbitElevation) * Math.cos(orbitAzimuth);

        camera.position.set(camX, camY, camZ);
        camera.lookAt(0, 0, 0);
      } else {
        const elapsed = performance.now() - zoomStartTime;
        const progress = Math.min(1, elapsed / zoomDuration);
        
        const ease = progress < 0.5
          ? 4 * progress * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 3) / 2;

        const targetPos = moonWorldPos.clone().add(new Vector3(0.0, 0.0, 1.0));
        camera.position.lerpVectors(startCamPos, targetPos, ease);

        const currentLookAt = new Vector3().lerpVectors(startLookAt, moonWorldPos, ease);
        camera.lookAt(currentLookAt);

        camera.fov = 40 - ease * 16;
        camera.updateProjectionMatrix();

        if (progress > 0.65) {
          setZoomFade((progress - 0.65) / 0.35);
        }

        if (progress >= 1) {
          onEnterLunarMission();
          return;
        }
      }

      starField.rotation.y = time * 0.000008;
      renderer.render(scene, camera);
      frameId = requestAnimationFrame(render);
    };

    frameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frameId);
      canvas.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("mousemove", onPointerMove);
      window.removeEventListener("mouseup", onPointerUp);
      canvas.removeEventListener("wheel", onWheel);
      renderer.dispose();
      sunGeom.dispose();
      sunMat.dispose();
      starGeom.dispose();
    };
  }, [onEnterLunarMission, reducedMotion]);

  const handleTriggerZoom = () => {
    if (triggerZoomRef.current) {
      triggerZoomRef.current();
    } else {
      onEnterLunarMission();
    }
  };

  return (
    <div className={`solar-entrance-container ${isZooming ? "zooming" : ""}`} ref={containerRef}>
      <canvas className="solar-canvas" ref={canvasRef} />

      {/* Atmospheric Transit Veil for seamless crossfade */}
      <div
        className="hyperspace-overlay"
        style={{
          opacity: isZooming ? zoomFade : 0,
          background: "radial-gradient(circle at center, rgba(56, 239, 125, 0.25) 0%, rgba(3, 7, 18, 0.98) 100%)",
        }}
      />

      {/* NASA Eyes Header Navigation */}
      <header className="solar-nav" style={{ opacity: isZooming ? 1 - zoomFade : 1 }}>
        <div className="solar-brand">
          <span style={{ font: "600 11px 'Berkeley Mono', 'JetBrains Mono', ui-monospace, monospace" }}>EYES ON THE SOLAR SYSTEM // <strong>SELENEON HELIOCENTRIC RADAR</strong></span>
        </div>
        <div className="solar-tag" style={{ font: "500 10px 'Berkeley Mono', 'JetBrains Mono', ui-monospace, monospace" }}>
          {hoveredBodyName ? `TARGET LOCK: ${hoveredBodyName.toUpperCase()}` : "DRAG TO ROTATE / SCROLL TO ZOOM"}
        </div>
        <button
          className="solar-skip-btn"
          onClick={handleTriggerZoom}
          aria-label="Skip to Moon mission console"
        >
          Skip to Moon ↗
        </button>
      </header>

      {/* NASA Eyes Pinned 3D Orbit Node Labels (Clean plain text, no bullets, no glow) */}
      {!isZooming && Object.entries(hudLabels).map(([key, item]) => {
        if (key === "Moon" || !item.visible) return null;
        return (
          <div
            key={key}
            style={{
              position: "absolute",
              left: `${item.x}px`,
              top: `${item.y}px`,
              transform: "translate(-50%, -130%)",
              pointerEvents: "none",
              zIndex: 10,
              font: "500 9px 'Berkeley Mono', 'JetBrains Mono', ui-monospace, monospace",
              letterSpacing: "0.14em",
              color: item.color,
              whiteSpace: "nowrap",
            }}
          >
            {item.label}
          </div>
        );
      })}

      {/* Interactive Moon Hologram Tag tracking 3D Moon coordinate */}
      {moonScreenPos.visible && !isZooming && (
        <div
          className={`moon-hologram-tag ${isHovered ? "hovered" : ""}`}
          style={{
            left: `${moonScreenPos.x}px`,
            top: `${moonScreenPos.y}px`,
          }}
          onClick={handleTriggerZoom}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          role="button"
          tabIndex={0}
          aria-label="Target The Moon - Tap to zoom into lunar mission"
        >
          <div className="reticle-rings">
            <span className="ring-pulse r1" />
            <span className="ring-pulse r2" />
            <span className="reticle-crosshair ch-x" />
            <span className="reticle-crosshair ch-y" />
            <span className="reticle-center" />
          </div>

          <div className="hologram-card">
            <div className="hologram-header">
              <strong>TARGET: THE MOON [LUNA]</strong>
            </div>
            <div className="hologram-sub">EARTH SATELLITE · CHANDRAYAAN-2 OHRC EXP-000</div>
            <div className="hologram-action">
              <span>CLICK TO ENTER LUNAR MISSION</span>
              <span className="action-arrow">➔</span>
            </div>
          </div>
        </div>
      )}

      {/* NASA Eyes Timeline Bar */}
      <footer className="solar-bottom-bar" style={{ opacity: isZooming ? 1 - zoomFade : 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span style={{ color: "#38bdf8", font: "600 11px 'Berkeley Mono', 'JetBrains Mono', ui-monospace, monospace", letterSpacing: "0.1em" }}>
            LIVE
          </span>
          <span style={{ color: "#8ca8af", font: "10px 'Berkeley Mono', 'JetBrains Mono', ui-monospace, monospace", letterSpacing: "0.08em" }}>
            SEP 04, 2026 / REAL RATE / 12:01:18 AM UTC
          </span>
        </div>

        <button
          className="solar-engage-btn"
          onClick={handleTriggerZoom}
          disabled={isZooming}
        >
          {isZooming ? (
            <span>SWOOPING ALONG ORBITAL PATH...</span>
          ) : (
            <>
              <span>ENGAGE APPROACH TO MOON</span>
              <span className="arrow">➔</span>
            </>
          )}
        </button>
      </footer>
    </div>
  );
}
