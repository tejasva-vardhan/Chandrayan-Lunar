import { useEffect, useRef } from "react";
import {
  AdditiveBlending,
  BufferGeometry,
  Float32BufferAttribute,
  Mesh,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  Scene,
  ShaderMaterial,
  SphereGeometry,
  WebGLRenderer,
} from "three";

type MoonSceneProps = { progress: number; reducedMotion: boolean };

const noiseFunctions = `
float hash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float noise(vec3 p) {
  vec3 i = floor(p), f = fract(p); f = f * f * (3. - 2. * f);
  return mix(mix(mix(hash(i), hash(i + vec3(1.,0.,0.)), f.x), mix(hash(i + vec3(0.,1.,0.)), hash(i + vec3(1.,1.,0.)), f.x), f.y), mix(mix(hash(i + vec3(0.,0.,1.)), hash(i + vec3(1.,0.,1.)), f.x), mix(hash(i + vec3(0.,1.,1.)), hash(i + vec3(1.,1.,1.)), f.x), f.y), f.z);
}
float fbm(vec3 p) { float value = 0., amplitude = .5; for (int i = 0; i < 4; i++) { value += noise(p) * amplitude; p = p * 2.02 + 10.; amplitude *= .5; } return value; }
`;

const vertexShader = `
varying vec3 vNormal;
varying vec3 vPosition;
${noiseFunctions}
void main() {
  vec3 direction = normalize(position);
  float relief = fbm(direction * 7.) * .052 + noise(direction * 35.) * .014;
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
  vec3 light = normalize(vec3(-.72, .38, .75));
  float diffuse = max(.035, dot(n, light));
  float terrain = fbm(vPosition * 7.);
  float smallDetail = noise(vPosition * 48.);
  float craterField = smoothstep(.055, .0, abs(noise(vPosition * 18.) - .5));
  vec3 basalt = vec3(.16, .19, .20);
  vec3 highland = vec3(.52, .55, .52);
  vec3 albedo = mix(basalt, highland, terrain * .9 + smallDetail * .18);
  albedo *= 1. - craterField * .38;
  float rim = pow(1. - max(0., n.z), 3.2);
  gl_FragColor = vec4(albedo * (diffuse + .13) + vec3(.10, .17, .19) * rim, 1.);
}`;

export function MoonScene({ progress, reducedMotion }: MoonSceneProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progressRef = useRef(progress);
  progressRef.current = progress;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2.25));
    const scene = new Scene();
    const camera = new PerspectiveCamera(33, 1, .1, 100);
    camera.position.z = 3.45;

    const moonMaterial = new ShaderMaterial({ vertexShader, fragmentShader });
    const moon = new Mesh(new SphereGeometry(1.15, 192, 192), moonMaterial);
    moon.position.set(.7, .04, 0);
    scene.add(moon);

    const starsGeometry = new BufferGeometry();
    const stars = new Float32Array(720 * 3);
    for (let index = 0; index < stars.length; index += 3) {
      stars[index] = (Math.random() - .5) * 14;
      stars[index + 1] = (Math.random() - .5) * 8;
      stars[index + 2] = -3 - Math.random() * 4;
    }
    starsGeometry.setAttribute("position", new Float32BufferAttribute(stars, 3));
    const starField = new Points(starsGeometry, new PointsMaterial({ color: 0x92dce2, size: .018, transparent: true, opacity: .65, blending: AdditiveBlending }));
    scene.add(starField);

    let frame = 0;
    const render = (time: number) => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (!width || !height) { frame = requestAnimationFrame(render); return; }
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      const targetX = .55 - progressRef.current * .82;
      moon.position.x += (targetX - moon.position.x) * .035;
      moon.rotation.y = reducedMotion ? .18 : time * .000025;
      moon.rotation.x = .14;
      starField.rotation.y = reducedMotion ? 0 : time * .000006;
      renderer.render(scene, camera);
      if (!reducedMotion) frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(frame);
      moon.geometry.dispose(); moonMaterial.dispose(); starsGeometry.dispose();
      starField.material.dispose(); renderer.dispose();
    };
  }, [reducedMotion]);

  return <canvas className="moon-canvas" ref={canvasRef} aria-label="Three-dimensional lunar globe in deep space" />;
}
