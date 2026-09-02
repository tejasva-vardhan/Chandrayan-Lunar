import { useEffect, useRef } from "react";

type MoonSceneProps = { progress: number; reducedMotion: boolean };

const vertexSource = `
attribute vec2 a_position;
varying vec2 v_uv;
void main() { v_uv = a_position * .5 + .5; gl_Position = vec4(a_position, 0., 1.); }
`;

const fragmentSource = `
precision mediump float;
uniform float u_time;
uniform float u_progress;
uniform vec2 u_resolution;
varying vec2 v_uv;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.,0.)), f.x), mix(hash(i+vec2(0.,1.)), hash(i+vec2(1.,1.)), f.x), f.y);
}
mat2 rotate(float angle) {
  float s = sin(angle), c = cos(angle);
  return mat2(c, -s, s, c);
}
void main() {
  vec2 uv = v_uv;
  vec2 p = (uv - .5) * vec2(u_resolution.x/u_resolution.y, 1.);
  float zoom = mix(.76, 1.55, smoothstep(.05, .82, u_progress));
  vec2 center = vec2(mix(.18, -.05, u_progress), mix(-.03, .03, u_progress));
  p = (p - center) * zoom;
  float r = length(p);
  vec3 space = vec3(.012, .035, .063);
  float stars = step(.996, hash(floor(uv * 380.)));
  space += stars * vec3(.4, .72, .86) * (1. - r * .35);
  if (r < .52) {
    vec2 q = p / .52;
    float z = sqrt(max(0., 1. - dot(q,q)));
    vec3 normal = normalize(vec3(q.x, q.y, z));
    vec3 light = normalize(vec3(-.65, .35, .7));
    float lit = max(0.08, dot(normal, light));
    // Rotate the terrain texture while keeping the moon's lighting stable.
    vec2 terrain = rotate(u_time * .055) * q;
    float detail = noise(terrain * 38.) * .18 + noise(terrain * 105.) * .07;
    float crater = smoothstep(.24, .0, abs(noise(terrain * 12.) - .48)) * .1;
    vec3 moon = vec3(.38, .43, .44) * (lit + detail - crater);
    float rim = smoothstep(.52, .43, r);
    moon += rim * vec3(.05, .11, .12);
    gl_FragColor = vec4(moon, 1.);
  } else { gl_FragColor = vec4(space, 1.); }
}
`;

function shader(gl: WebGLRenderingContext, type: number, source: string) {
  const result = gl.createShader(type);
  if (!result) throw new Error("WebGL shader creation failed");
  gl.shaderSource(result, source);
  gl.compileShader(result);
  return result;
}

export function MoonScene({ progress, reducedMotion }: MoonSceneProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progressRef = useRef(progress);
  progressRef.current = progress;

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext("webgl");
    if (!canvas || !gl) return;
    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, shader(gl, gl.VERTEX_SHADER, vertexSource));
    gl.attachShader(program, shader(gl, gl.FRAGMENT_SHADER, fragmentSource));
    gl.linkProgram(program);
    const position = gl.getAttribLocation(program, "a_position");
    const time = gl.getUniformLocation(program, "u_time");
    const sceneProgress = gl.getUniformLocation(program, "u_progress");
    const resolution = gl.getUniformLocation(program, "u_resolution");
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
    let frame = 0;
    const render = (now: number) => {
      const ratio = Math.min(window.devicePixelRatio, 1.75);
      const width = Math.floor(canvas.clientWidth * ratio);
      const height = Math.floor(canvas.clientHeight * ratio);
      if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
      gl.viewport(0, 0, width, height);
      gl.useProgram(program);
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      gl.uniform1f(time, reducedMotion ? 0 : now * .001);
      gl.uniform1f(sceneProgress, progressRef.current);
      gl.uniform2f(resolution, width, height);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      if (!reducedMotion) frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => { cancelAnimationFrame(frame); gl.deleteProgram(program); gl.deleteBuffer(buffer); };
  }, [reducedMotion]);

  return <canvas className="moon-canvas" ref={canvasRef} aria-label="Animated lunar surface in deep space" />;
}
