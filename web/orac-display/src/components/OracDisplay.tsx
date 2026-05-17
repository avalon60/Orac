
import React, { useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { 
  PerspectiveCamera, 
  Environment,
  Edges, 
  Float, 
  Lightformer,
  Line,
  MeshTransmissionMaterial,
  Sparkles,
} from '@react-three/drei';
import { EffectComposer, Bloom, Noise, Glitch } from '@react-three/postprocessing';
import * as THREE from 'three';
import { motion, AnimatePresence } from 'framer-motion';
import {
  attachCanvasDiagnostics,
  logDisplayDiagnostic,
  type DisplayRecoveryReason,
} from '../displayDiagnostics';
import type { OracState } from '../types/oracState';

interface StateConfig {
  color: string;
  bloomIntensity: number;
  rotationSpeed: number;
  distortion: number;
  pulseRate: number;
  scale: number;
  transmission: number;
  glitchIntensity?: number;
}

interface CorePalette {
  color: string;
  glowColor: string;
  highlightColor: string;
}

interface OracDisplayProps {
  state: OracState;
  message?: string;
  showTranscriptPanels?: boolean;
  userTranscript?: string;
  oracTranscript?: string;
  renderResetKey?: number;
  onRenderRecovery?: (reason: DisplayRecoveryReason) => void;
}

interface CanvasErrorBoundaryProps {
  children: React.ReactNode;
  resetKey: number;
}

interface CanvasErrorBoundaryState {
  error: Error | null;
}

class CanvasErrorBoundary extends React.Component<
  CanvasErrorBoundaryProps,
  CanvasErrorBoundaryState
> {
  constructor(props: CanvasErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): CanvasErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error) {
    logDisplayDiagnostic('canvas error boundary caught error', error);
  }

  componentDidUpdate(prevProps: CanvasErrorBoundaryProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full w-full items-center justify-center bg-[#03070d] px-6">
          <div className="max-w-xl rounded-[1.5rem] border border-[#4fc3f7]/20 bg-[#06131d]/92 px-6 py-5 text-center shadow-[0_0_40px_rgba(3,7,13,0.75)]">
            <div className="text-[10px] font-bold uppercase tracking-[0.45em] text-[#8fdcff]">
              Display renderer fault
            </div>
            <div className="mt-3 text-[11px] tracking-[0.18em] text-[#b8d9ee]">
              The WebGL canvas failed and will retry automatically.
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const SHOW_TRANSCRIPT_PANELS =
  (import.meta.env.VITE_ORAC_SHOW_TRANSCRIPT_PANELS || '')
    .trim()
    .toLowerCase() === 'true';

const STATE_CONFIGS: Record<OracState, StateConfig> = {
  idle: { color: '#4fc3f7', bloomIntensity: 0.45, rotationSpeed: 0.15, distortion: 0.1, pulseRate: 0.5, scale: 1, transmission: 0.9 },
  wake_detected: { color: '#8fdcff', bloomIntensity: 0.15, rotationSpeed: 1.5, distortion: 0.1, pulseRate: 10, scale: 1.25, transmission: 0.28 },
  listening: { color: '#7af7ff', bloomIntensity: 0.22, rotationSpeed: 0.4, distortion: 0.2, pulseRate: 2, scale: 1.1, transmission: 0.34 },
  transcribing: { color: '#b8f2ff', bloomIntensity: 1.1, rotationSpeed: 1.2, distortion: 0.4, pulseRate: 4, scale: 1.05, transmission: 0.8 },
  thinking: { color: '#8ed3e8', bloomIntensity: 1.45, rotationSpeed: 0.8, distortion: 0.42, pulseRate: 1, scale: 1.15, transmission: 0.7 },
  tool_calling: { color: '#31e6d0', bloomIntensity: 2.1, rotationSpeed: 1.8, distortion: 0.3, pulseRate: 6, scale: 1.2, transmission: 0.6 },
  speaking: { color: '#9be7ff', bloomIntensity: 1.6, rotationSpeed: 0.54, distortion: 0.2, pulseRate: 3, scale: 1.15, transmission: 0.8 },
  interrupted: { color: '#ffb02e', bloomIntensity: 2.5, rotationSpeed: 2.0, distortion: 1.0, pulseRate: 8, scale: 0.95, transmission: 0.4, glitchIntensity: 1 },
  complete: { color: '#4fc3f7', bloomIntensity: 1.0, rotationSpeed: 0.15, distortion: 0.1, pulseRate: 0.2, scale: 1.05, transmission: 0.95 },
  error: { color: '#ff5b4f', bloomIntensity: 1.5, rotationSpeed: 0.05, distortion: 0.5, pulseRate: 12, scale: 1.0, transmission: 0.5 },
};

const CORE_PALETTES: Record<OracState, CorePalette> = {
  idle: { color: '#edf8ff', glowColor: '#d7ecff', highlightColor: '#ffffff' },
  wake_detected: { color: '#fff3d3', glowColor: '#ffe2a8', highlightColor: '#fff9ec' },
  listening: { color: '#eefcff', glowColor: '#dff7ff', highlightColor: '#ffffff' },
  transcribing: { color: '#eefaff', glowColor: '#d7f3ff', highlightColor: '#ffffff' },
  thinking: { color: '#f4fbff', glowColor: '#d8edf7', highlightColor: '#ffffff' },
  tool_calling: { color: '#f8f1dd', glowColor: '#f0deaf', highlightColor: '#fff8e8' },
  speaking: { color: '#f1cd82', glowColor: '#ffdea0', highlightColor: '#fff2cf' },
  interrupted: { color: '#ffe0ab', glowColor: '#ffd186', highlightColor: '#fff3d4' },
  complete: { color: '#effaff', glowColor: '#d9efff', highlightColor: '#ffffff' },
  error: { color: '#d3deea', glowColor: '#b9cadf', highlightColor: '#edf4fb' },
};

const OUTER_CUBE_SURFACE = {
  color: '#d7f4ff',
  clearcoat: 0.95,
  distortion: 0.02,
  distortionScale: 0.05,
  opacity: 0.24,
  roughness: 0.04,
  thickness: 0.65,
};

const createCoreGlowTexture = () => {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;

  const context = canvas.getContext('2d');
  if (!context) {
    return null;
  }

  const gradient = context.createRadialGradient(48, 40, 5, 64, 64, 46);
  gradient.addColorStop(0, 'rgba(255,255,255,0.74)');
  gradient.addColorStop(0.18, 'rgba(255,255,255,0.36)');
  gradient.addColorStop(0.42, 'rgba(255,255,255,0.14)');
  gradient.addColorStop(0.66, 'rgba(255,255,255,0.04)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');

  context.fillStyle = gradient;
  context.fillRect(0, 0, canvas.width, canvas.height);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
};

const createCoreBodyTexture = () => {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;

  const context = canvas.getContext('2d');
  if (!context) {
    return null;
  }

  const bodyGradient = context.createRadialGradient(42, 38, 7, 64, 64, 52);
  bodyGradient.addColorStop(0, 'rgba(255,255,255,0.98)');
  bodyGradient.addColorStop(0.12, 'rgba(255,250,236,0.95)');
  bodyGradient.addColorStop(0.3, 'rgba(244,216,146,0.72)');
  bodyGradient.addColorStop(0.58, 'rgba(194,136,56,0.38)');
  bodyGradient.addColorStop(1, 'rgba(78,48,18,0.02)');

  context.fillStyle = bodyGradient;
  context.fillRect(0, 0, canvas.width, canvas.height);

  const shadow = context.createRadialGradient(82, 82, 2, 64, 64, 48);
  shadow.addColorStop(0, 'rgba(57,34,10,0.12)');
  shadow.addColorStop(1, 'rgba(57,34,10,0)');
  context.fillStyle = shadow;
  context.fillRect(0, 0, canvas.width, canvas.height);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
};

const WAVE_SEGMENTS = 72;

const createWavePoints = (radius: number, seed: number, timeOffset: number) => {
  const points: THREE.Vector2[] = [];
  const lobePhase = seed * 0.77 + timeOffset * 0.4;

  for (let i = 0; i <= WAVE_SEGMENTS; i += 1) {
    const theta = (i / WAVE_SEGMENTS) * Math.PI * 2;
    const ripple =
      Math.sin(theta * 3.0 + lobePhase) * 0.008 +
      Math.sin(theta * 7.0 - lobePhase * 0.6) * 0.003 +
      Math.sin(theta * 11.0 + lobePhase * 0.25) * 0.0015;

    points.push(
      new THREE.Vector2(
        Math.cos(theta) * radius * (1 + ripple),
        Math.sin(theta) * radius * (1 + ripple),
      ),
    );
  }

  return points;
};

const createWaveGeometry = (radius: number, seed: number) => {
  const points = createWavePoints(radius, seed, 0);
  const geometry = new THREE.BufferGeometry();
  const vertices = new Float32Array(points.length * 3);

  points.forEach((point, index) => {
    const offset = index * 3;
    vertices[offset] = point.x;
    vertices[offset + 1] = point.y;
    vertices[offset + 2] = 0;
  });

  geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
  geometry.computeBoundingSphere();
  return geometry;
};

const ORBITAL_RING_SEGMENTS = 96;
const ORBITAL_RING_MAJOR_RATIO = 1;
const ORBITAL_RING_MINOR_RATIO = 0.88;
const ORBITAL_RING_BASE_MULTIPLIER = 1.78;

const createOrbitalArcPoints = (
  startAngle: number,
  endAngle: number,
  radiusX = ORBITAL_RING_MAJOR_RATIO,
  radiusY = ORBITAL_RING_MINOR_RATIO,
) => {
  const points = Array.from({ length: ORBITAL_RING_SEGMENTS + 1 }, (_, index) => {
    const t = index / ORBITAL_RING_SEGMENTS;
    const theta = startAngle + (endAngle - startAngle) * t;
    const wobble = Math.sin(theta * 4.0) * 0.008 + Math.sin(theta * 9.0) * 0.003;
    return new THREE.Vector3(
      Math.cos(theta) * radiusX * (1 + wobble),
      Math.sin(theta) * radiusY * (1 + wobble * 0.85),
      0,
    );
  });
  return points;
};

const ScanLine = ({ state }: { state: OracState }) => {
  const ref = useRef<THREE.Mesh>(null);
  const config = STATE_CONFIGS[state];
  
  useFrame((sceneState) => {
    if (ref.current && state === 'transcribing') {
      ref.current.position.y = Math.sin(sceneState.clock.elapsedTime * 2) * 2.5;
    }
  });

  if (state !== 'transcribing') return null;

  return (
    <mesh ref={ref} rotation={[Math.PI / 2, 0, 0]}>
      <planeGeometry args={[6, 0.05]} />
      <meshBasicMaterial color={config.color} transparent opacity={0.6} toneMapped={false} />
    </mesh>
  );
};

const CanvasDiagnostics = ({
  onRecovery,
}: {
  onRecovery?: (reason: DisplayRecoveryReason) => void;
}) => {
  const { gl } = useThree();
  const recoveryRef = useRef(onRecovery);

  useEffect(() => {
    recoveryRef.current = onRecovery;
  }, [onRecovery]);

  useEffect(
    () =>
      attachCanvasDiagnostics(gl.domElement, (reason) => {
        recoveryRef.current?.(reason);
      }),
    [gl],
  );

  return null;
};

const GlassEnvironment = () => (
  <Environment background={false} resolution={48} blur={0.9}>
    <group rotation={[0, Math.PI / 4, 0]}>
      <Lightformer
        form="rect"
        intensity={0.46}
        color="#8fdcff"
        scale={[12, 1.1, 1]}
        position={[0, 4, -7]}
      />
      <Lightformer
        form="rect"
        intensity={0.18}
        color="#0f2233"
        scale={[12, 1.1, 1]}
        position={[0, -4, 7]}
      />
      <Lightformer
        form="rect"
        intensity={0.24}
        color="#4ca9ff"
        scale={[1.2, 12, 1]}
        position={[-7, 0, 1]}
      />
      <Lightformer
        form="rect"
        intensity={0.18}
        color="#2f5f99"
        scale={[1.2, 12, 1]}
        position={[7, 0, -1]}
      />
      <Lightformer
        form="rect"
        intensity={0.2}
        color="#ffffff"
        scale={[2.5, 2.5, 1]}
        position={[0, 0, 8]}
      />
      <Lightformer
        form="rect"
        intensity={0.14}
        color="#14324d"
        scale={[2.5, 2.5, 1]}
        position={[0, 0, -8]}
      />
    </group>
  </Environment>
);

const WaveHalo = ({ state }: { state: OracState }) => {
  const ref = useRef<THREE.Group>(null);
  const config = STATE_CONFIGS[state];
  const isListening = state === 'listening' || state === 'wake_detected';
  const isSpeaking = state === 'speaking';
  const waveCount = isSpeaking ? 3 : 2;
  const waveGeometries = useMemo(
    () =>
      Array.from({ length: waveCount }, (_, index) =>
        createWaveGeometry(1 + index * 0.12, index + (isSpeaking ? 2.4 : 1.2)),
      ),
    [isSpeaking, waveCount],
  );

  useEffect(() => {
    return () => {
      waveGeometries.forEach((geometry) => geometry.dispose());
    };
  }, [waveGeometries]);

  useFrame((sceneState) => {
    if (!ref.current) {
      return;
    }

    const t = sceneState.clock.elapsedTime;
    const rings = ref.current.children as THREE.Group[];

    rings.forEach((child, index) => {
      if (isSpeaking) {
        const progress = ((t * 0.18) + index * 0.24) % 1;
        const eased = progress * progress * (3 - 2 * progress);
        const scale = 0.92 + index * 0.08 + eased * (0.62 + index * 0.05);
        child.scale.setScalar(scale);
        child.rotation.z = Math.sin(t * 0.12 + index * 0.7) * 0.006;
        const line = child.children[0] as THREE.LineLoop;
        const material = line.material as THREE.LineBasicMaterial;
        material.opacity = (1 - eased) * (0.055 - index * 0.008);
      } else if (isListening) {
        const progress = ((t * 0.12) + index * 0.26) % 1;
        const eased = progress * progress * (3 - 2 * progress);
        const scale = 1.975 - eased * (0.78 + index * 0.04);
        child.scale.setScalar(scale);
        child.rotation.z = Math.sin(t * 0.1 + index * 0.55) * 0.005;
        const line = child.children[0] as THREE.LineLoop;
        const material = line.material as THREE.LineBasicMaterial;
        material.opacity = (1 - eased) * (0.022 - index * 0.0035);
      }
    });
  });

  if (!isListening && !isSpeaking) return null;

  return (
    <group ref={ref} renderOrder={1}>
      {waveGeometries.map((geometry, i) => (
        <group key={i}>
          <lineLoop geometry={geometry}>
            <lineBasicMaterial
              color={config.color}
              transparent
              opacity={0}
              depthWrite={false}
              depthTest={false}
              blending={THREE.AdditiveBlending}
              toneMapped={false}
            />
          </lineLoop>
        </group>
      ))}
    </group>
  );
};

const OrbitalRings = ({
  state,
  coreRadiusRef,
}: {
  state: OracState;
  coreRadiusRef: React.MutableRefObject<number>;
}) => {
  const rootRef = useRef<THREE.Group>(null);
  const ringGroupsRef = useRef<Array<THREE.Group | null>>([]);

  const ringFrontPoints = useMemo(
    () => createOrbitalArcPoints(-Math.PI * 0.48, Math.PI * 0.52),
    [],
  );
  const ringBackPoints = useMemo(
    () => createOrbitalArcPoints(Math.PI * 0.52, Math.PI * 1.52),
    [],
  );

  useFrame((sceneState, delta) => {
    if (!rootRef.current) {
      return;
    }

    const t = sceneState.clock.elapsedTime;
    const isIdle = state === 'idle';
    const isListening = state === 'listening' || state === 'wake_detected';
    const isSpeaking = state === 'speaking';
    const coreRadius = coreRadiusRef.current;
    const ringRadius = coreRadius * ORBITAL_RING_BASE_MULTIPLIER;
    const driftSpeed = isIdle ? 0.01 : isListening ? 0.024 : isSpeaking ? 0.032 : 0.018;

    rootRef.current.scale.setScalar(ringRadius);
    rootRef.current.rotation.z += delta * driftSpeed;
    rootRef.current.rotation.x = Math.sin(t * 0.06) * (isSpeaking ? 0.08 : 0.05);
    rootRef.current.rotation.y = Math.cos(t * 0.05) * (isListening ? 0.08 : 0.05);

    ringGroupsRef.current.forEach((ringGroup, index) => {
      if (!ringGroup) {
        return;
      }

      const phase = index * Math.PI * 0.5;
      ringGroup.rotation.z = Math.sin(t * 0.12 + phase) * (isIdle ? 0.018 : isListening ? 0.03 : 0.04);
      ringGroup.rotation.x = Math.sin(t * 0.09 + phase * 0.5) * 0.02;

      const ringChildren = ringGroup.children as THREE.Line[];
      const frontLine = ringChildren[0];
      const backLine = ringChildren[1];
      const frontMaterial = frontLine.material as THREE.LineBasicMaterial;
      const backMaterial = backLine.material as THREE.LineBasicMaterial;
      const shimmer = (Math.sin(t * (isSpeaking ? 0.9 : 0.45) + phase) + 1) * 0.5;
      const frontBaseOpacity = isIdle ? 0.07 : isListening ? 0.095 : isSpeaking ? 0.105 : 0.085;
      const backBaseOpacity = isIdle ? 0.028 : isListening ? 0.04 : isSpeaking ? 0.045 : 0.036;

      frontMaterial.color.set(STATE_CONFIGS[state].color);
      backMaterial.color.set(STATE_CONFIGS[state].color);
      frontMaterial.opacity = frontBaseOpacity + shimmer * (isSpeaking ? 0.012 : 0.008);
      backMaterial.opacity = backBaseOpacity + shimmer * (isSpeaking ? 0.01 : 0.006);
    });
  });

  if (state === 'error') {
    return null;
  }

  return (
    <group ref={rootRef} renderOrder={3}>
      <group
        ref={(node) => {
          ringGroupsRef.current[0] = node;
        }}
        rotation={[0.74, 0.18, 0.14]}
        scale={[1, 0.92, 1]}
        renderOrder={3}
      >
        <Line
          points={ringBackPoints}
          color={STATE_CONFIGS[state].color}
          transparent
          opacity={0}
          depthWrite={false}
          depthTest={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
        <Line
          points={ringFrontPoints}
          color={STATE_CONFIGS[state].color}
          transparent
          opacity={0}
          depthWrite={false}
          depthTest={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </group>

      <group
        ref={(node) => {
          ringGroupsRef.current[1] = node;
        }}
        rotation={[0.74, Math.PI / 2 + 0.18, -0.14]}
        scale={[0.92, 1, 1]}
        renderOrder={3}
      >
        <Line
          points={ringBackPoints}
          color={STATE_CONFIGS[state].color}
          transparent
          opacity={0}
          depthWrite={false}
          depthTest={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
        <Line
          points={ringFrontPoints}
          color={STATE_CONFIGS[state].color}
          transparent
          opacity={0}
          depthWrite={false}
          depthTest={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </group>
    </group>
  );
};

const TranscriptPanel = ({
  title,
  text,
  placeholder,
  accentColor,
  emphasis = 1,
  muted = false,
  bodyClassName = '',
  fadeStop = 82,
}: {
  title: string;
  text: string;
  placeholder: string;
  accentColor: string;
  emphasis?: number;
  muted?: boolean;
  bodyClassName?: string;
  fadeStop?: number;
}) => {
  const body = text.trim() || placeholder;
  const panelOpacity = muted ? 0.5 : 0.82;
  const borderOpacity = muted ? 0.12 : 0.2;
  const glowOpacity = muted ? 0.08 : 0.14;
  const bodyOpacity = muted ? 0.82 : 0.94;

  return (
    <div
      className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-[1.5rem] border bg-[#04131d]/68 px-5 py-4 backdrop-blur-xl"
      style={{
        borderColor: `rgba(27, 95, 145, ${borderOpacity})`,
        boxShadow: `0 0 26px ${accentColor}${muted ? '14' : '22'}`,
        opacity: panelOpacity,
        transform: `scale(${emphasis})`,
        transformOrigin: 'center',
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 rounded-[1.5rem]"
        style={{
          background:
            'linear-gradient(180deg, rgba(255,255,255,0.02), transparent 28%, rgba(0,0,0,0.06))',
          boxShadow: `inset 0 0 0 1px rgba(79, 195, 247, ${glowOpacity})`,
        }}
      />
      <div className="flex items-center justify-between gap-3 border-b border-[#1b5f91]/14 pb-3">
        <div
          className="text-[10px] font-bold uppercase tracking-[0.45em]"
          style={{
            color: accentColor,
            textShadow: `0 0 16px ${accentColor}55`,
          }}
        >
          {title}
        </div>
        <div className="h-px flex-1 bg-gradient-to-r from-[#1b5f91]/20 to-transparent" />
      </div>
      <div className={`mt-4 flex-1 overflow-hidden ${bodyClassName}`}>
        <div
          className="max-h-full overflow-y-auto whitespace-pre-wrap break-words pr-1 text-[#d5e7f1]"
          style={{
            opacity: bodyOpacity,
            fontSize: emphasis > 1 ? '12px' : '13px',
            lineHeight: emphasis > 1 ? 1.75 : 1.8,
            letterSpacing: '0.085em',
            maskImage:
              `linear-gradient(180deg, black 0%, black ${fadeStop}%, transparent 100%)`,
            WebkitMaskImage:
              `linear-gradient(180deg, black 0%, black ${fadeStop}%, transparent 100%)`,
          }}
        >
          {body}
        </div>
      </div>
    </div>
  );
};

const Tesseract = ({ state }: { state: OracState }) => {
  // Base sizes
  const outerBaseSize = 2;
  const innerBaseSize = 1.3;
  const coreBaseRadius = 0.16;

  const groupRef = useRef<THREE.Group>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const outerRef = useRef<THREE.Mesh>(null);
  const coreHaloRef = useRef<THREE.Mesh>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const coreGlowRef = useRef<THREE.Mesh>(null);
  const coreHighlightRef = useRef<THREE.Mesh>(null);
  const connectorRef = useRef<THREE.LineSegments>(null);
  const orbitalCoreRadiusRef = useRef<number>(coreBaseRadius);
  const stateEnteredAtRef = useRef<number>(performance.now() * 0.001);
  
  const config = STATE_CONFIGS[state];
  const corePalette = CORE_PALETTES[state];
  const coreGlowTexture = useMemo(() => createCoreGlowTexture(), []);
  const coreBodyTexture = useMemo(() => createCoreBodyTexture(), []);

  useEffect(() => {
    stateEnteredAtRef.current = performance.now() * 0.001;
  }, [state]);

  useFrame((sceneState, delta) => {
    if (
      !groupRef.current ||
      !innerRef.current ||
      !outerRef.current ||
      !coreRef.current ||
      !connectorRef.current
    ) {
      return;
    }

    const t = sceneState.clock.elapsedTime;
    const stateAge = t - stateEnteredAtRef.current;
    
    // 1. Shared rotation for the whole tesseract
    const rotSpeed = config.rotationSpeed;
    groupRef.current.rotation.y += delta * rotSpeed;
    groupRef.current.rotation.x += delta * (rotSpeed * 0.5);
    groupRef.current.rotation.z += delta * (rotSpeed * 0.25);

    // 2. State-driven animations for the inner core, central sphere, and connectors
    let innerScale = innerBaseSize * config.scale;
    const outerScale = outerBaseSize;
    let outerOpacity = OUTER_CUBE_SURFACE.opacity;
    let innerOpacity = 0.16;
    let connectorOpacity = 0.45;
    let coreScale = coreBaseRadius * (state === 'idle' ? 1 : 2);
    let coreOpacity = 0.12;
    let coreGlow = 0.45;
    let coreHighlightOpacity = 0.2;
    let coreColor: THREE.ColorRepresentation = corePalette.color;
    let coreGlowColor: THREE.ColorRepresentation = corePalette.glowColor;
    let coreHighlightColor: THREE.ColorRepresentation = corePalette.highlightColor;

    switch (state) {
      case 'idle':
        // 3% breathing for inner cube
        innerScale *= (1 + Math.sin(t * 1.5) * 0.03);
        outerOpacity = 0.16;
        innerOpacity = 0.14;
        {
          const idlePulse = (Math.sin(t * 0.8) + 1) * 0.5;
          coreScale *= 1 + idlePulse * 0.02;
          coreOpacity = 0.12 + idlePulse * 0.03;
          coreGlow = 1.5 + idlePulse * 0.12;
          coreHighlightOpacity = 0.12 + idlePulse * 0.025;
          coreColor = new THREE.Color(corePalette.color).lerp(new THREE.Color('#f7fcff'), 0.3 + idlePulse * 0.25);
          coreGlowColor = new THREE.Color(corePalette.glowColor).lerp(new THREE.Color('#f9fdff'), 0.35 + idlePulse * 0.2);
          coreHighlightColor = new THREE.Color(corePalette.highlightColor).lerp(new THREE.Color('#ffffff'), 0.22 + idlePulse * 0.2);
        }
        break;
      case 'listening':
        // Expanded + gentle pulse
        innerScale *= (1.1 + Math.sin(t * 4) * 0.05);
        outerOpacity = 0.21;
        innerOpacity = 0.16;
        connectorOpacity = 0.55;
        coreScale *= (1 + Math.sin(t * 2.5) * 0.04);
        coreOpacity = 0.16;
        coreGlow = 0.65;
        coreHighlightOpacity = 0.14;
        break;
      case 'thinking':
        // Out of phase breathing
        const thinkT = t * 3;
        innerScale *= (1.1 + Math.sin(thinkT) * 0.1);
        outerOpacity = 0.22;
        innerOpacity = 0.17;
        // Shimmering connectors
        connectorOpacity = 0.5 + Math.sin(t * 10) * 0.15;
        coreScale *= (1.03 + Math.sin(t * 2.2) * 0.04);
        coreOpacity = 0.18;
        coreGlow = 0.78;
        coreHighlightOpacity = 0.15;
        break;
      case 'speaking':
        // Rhythmic pulse
        innerScale *= (1.03 + Math.sin(t * 3.92) * 0.08);
        outerOpacity = 0.23;
        innerOpacity = 0.18;
        {
          const pulsar = Math.pow((Math.sin(t * 3.12375) + 1) * 0.5, 1.8);
          connectorOpacity = 0.56 + pulsar * 0.08;
          const peakColor = new THREE.Color(corePalette.color).lerp(
            new THREE.Color('#fffdf6'),
            0.25 + pulsar * 0.7,
          );
          const peakGlowColor = new THREE.Color(corePalette.glowColor).lerp(
            new THREE.Color('#ffffff'),
            0.45 + pulsar * 0.45,
          );
          const peakHighlightColor = new THREE.Color(corePalette.highlightColor).lerp(
            new THREE.Color('#ffffff'),
            0.3 + pulsar * 0.6,
          );
          coreScale *= (1 + pulsar * 0.06);
          coreOpacity = 0.18 + pulsar * 0.2;
          coreGlow = 0.95 + pulsar * 3.0;
          coreHighlightOpacity = 0.16 + pulsar * 0.12;
          coreColor = peakColor;
          coreGlowColor = peakGlowColor;
          coreHighlightColor = peakHighlightColor;
        }
        break;
      case 'wake_detected':
        // Sharp expansion
        innerScale *= 1.4;
        outerOpacity = 0.2;
        innerOpacity = 0.16;
        connectorOpacity = 0.85;
        const wakePulse = Math.max(0, 1 - stateAge * 1.6);
        coreScale *= 1 + wakePulse * 0.06;
        coreOpacity = 0.18 + wakePulse * 0.12;
        coreGlow = 0.95 + wakePulse * 0.35;
        coreHighlightOpacity = 0.16 + wakePulse * 0.06;
        break;
      case 'error':
        // Reduced scale and dimmed connectors
        innerScale *= 0.8;
        outerOpacity = 0.1;
        innerOpacity = 0.1;
        connectorOpacity = 0.25;
        coreScale *= 1;
        coreOpacity = 0.04;
        coreGlow = 0.2;
        coreHighlightOpacity = 0.05;
        break;
      case 'transcribing':
        innerScale *= (1.05 + Math.sin(t * 6) * 0.05);
        outerOpacity = 0.2;
        innerOpacity = 0.17;
        coreScale *= (1 + Math.sin(t * 3) * 0.03);
        coreOpacity = 0.14;
        coreGlow = 0.58;
        coreHighlightOpacity = 0.12;
        break;
      case 'tool_calling':
        innerScale *= (1.2 + Math.sin(t * 8) * 0.1);
        outerOpacity = 0.24;
        innerOpacity = 0.17;
        connectorOpacity = 0.7;
        coreScale *= (1.04 + Math.sin(t * 8) * 0.05);
        coreOpacity = 0.2;
        coreGlow = 0.9;
        coreHighlightOpacity = 0.13;
        break;
    }

    innerRef.current.scale.setScalar(innerScale / innerBaseSize);
    outerRef.current.scale.setScalar(outerScale / outerBaseSize);
    coreRef.current.scale.setScalar(coreScale / coreBaseRadius);
    orbitalCoreRadiusRef.current = coreScale;
    const outerMaterial = outerRef.current.material as THREE.MeshPhysicalMaterial;
    outerMaterial.opacity = outerOpacity;
    const innerMaterial = innerRef.current.material as THREE.MeshPhysicalMaterial;
    innerMaterial.opacity = innerOpacity;
    const coreMaterial = coreRef.current.material as THREE.MeshPhysicalMaterial;
    coreMaterial.color.set(coreColor);
    coreMaterial.emissive.set(coreColor);
    coreMaterial.opacity = coreOpacity;
    coreMaterial.emissiveIntensity = coreGlow;

    if (coreHaloRef.current) {
      coreHaloRef.current.scale.setScalar((coreScale / coreBaseRadius) * 2.6);
      const haloMaterial = coreHaloRef.current.material as THREE.MeshBasicMaterial;
      haloMaterial.color.set(coreGlowColor);
      haloMaterial.opacity = 0;
    }

    if (coreGlowRef.current) {
      coreGlowRef.current.scale.setScalar((coreScale / coreBaseRadius) * 1.65);
      const glowMaterial = coreGlowRef.current.material as THREE.MeshBasicMaterial;
      glowMaterial.color.set(coreGlowColor);
      glowMaterial.opacity = 0;
    }

    if (coreHighlightRef.current) {
      coreHighlightRef.current.scale.setScalar((coreScale / coreBaseRadius) * 0.42);
      const highlightMaterial = coreHighlightRef.current.material as THREE.MeshBasicMaterial;
      highlightMaterial.color.set(coreHighlightColor);
      highlightMaterial.opacity = coreHighlightOpacity;
    }

    // 3. Update connector line vertices
    const positions = connectorRef.current.geometry.attributes.position.array as Float32Array;
    
    // Calculate current half-sizes in local space
    const halfOuter = (outerBaseSize * outerRef.current.scale.x) / 2;
    const halfInner = (innerBaseSize * innerRef.current.scale.x) / 2;
    
    const corners = [
      [-1, -1, -1], [ 1, -1, -1], [ 1,  1, -1], [-1,  1, -1],
      [-1, -1,  1], [ 1, -1,  1], [ 1,  1,  1], [-1,  1,  1]
    ];

    for (let i = 0; i < 8; i++) {
      const [cx, cy, cz] = corners[i];
      // Outer vertex
      positions[i * 6 + 0] = cx * halfOuter;
      positions[i * 6 + 1] = cy * halfOuter;
      positions[i * 6 + 2] = cz * halfOuter;
      // Inner vertex
      positions[i * 6 + 3] = cx * halfInner;
      positions[i * 6 + 4] = cy * halfInner;
      positions[i * 6 + 5] = cz * halfInner;
    }
    connectorRef.current.geometry.attributes.position.needsUpdate = true;
    (connectorRef.current.material as THREE.LineBasicMaterial).opacity = connectorOpacity;
  });

  const edgeColor = useMemo(() => new THREE.Color(config.color), [config.color]);

  return (
    <group ref={groupRef}>
      {/* Outer Cube */}
      <mesh ref={outerRef}>
        <boxGeometry args={[outerBaseSize, outerBaseSize, outerBaseSize]} />
        <MeshTransmissionMaterial
          backside
          backsideThickness={1.5}
          thickness={OUTER_CUBE_SURFACE.thickness}
          chromaticAberration={0.15}
          anisotropy={0.2}
          distortion={OUTER_CUBE_SURFACE.distortion}
          distortionScale={OUTER_CUBE_SURFACE.distortionScale}
          temporalDistortion={0}
          clearcoat={OUTER_CUBE_SURFACE.clearcoat}
          attenuationDistance={1.2}
          attenuationColor={OUTER_CUBE_SURFACE.color}
          color={OUTER_CUBE_SURFACE.color}
          transparent
          opacity={OUTER_CUBE_SURFACE.opacity}
          roughness={OUTER_CUBE_SURFACE.roughness}
          ior={1.45}
        />
        <Edges threshold={15} color={edgeColor}>
          <meshBasicMaterial color={edgeColor} toneMapped={false} />
        </Edges>
      </mesh>

      {/* Inner Cube */}
      <mesh ref={innerRef}>
        <boxGeometry args={[innerBaseSize, innerBaseSize, innerBaseSize]} />
        <MeshTransmissionMaterial
          backside
          backsideThickness={0.75}
          thickness={0.28}
          chromaticAberration={0.04}
          anisotropy={0.05}
          distortion={config.distortion * 0.35}
          distortionScale={0.08}
          temporalDistortion={0.04}
          clearcoat={1}
          attenuationDistance={4}
          attenuationColor={config.color}
          color={config.color}
          transparent
          opacity={0.16}
          roughness={0.03}
          ior={1.45}
        />
        <Edges threshold={15} color={edgeColor}>
          <meshBasicMaterial color={edgeColor} toneMapped={false} />
        </Edges>
      </mesh>

      {/* Central Core Sphere */}
      <group renderOrder={4}>
        <OrbitalRings state={state} coreRadiusRef={orbitalCoreRadiusRef} />

        <mesh ref={coreHaloRef} position={[0.018, 0.028, -0.016]} visible={false}>
          <sphereGeometry args={[coreBaseRadius, 32, 32]} />
          <meshBasicMaterial
            map={coreGlowTexture || undefined}
            color={corePalette.glowColor}
            transparent
            opacity={0}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>

        <mesh ref={coreGlowRef} position={[0.03, 0.04, -0.006]} visible={false}>
          <sphereGeometry args={[coreBaseRadius, 32, 32]} />
          <meshBasicMaterial
            map={coreGlowTexture || undefined}
            color={corePalette.glowColor}
            transparent
            opacity={0}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>

        <mesh ref={coreRef}>
          <sphereGeometry args={[coreBaseRadius, 32, 32]} />
          <meshPhysicalMaterial
            map={coreBodyTexture || undefined}
            color={corePalette.color}
            emissive={corePalette.color}
            emissiveIntensity={0.55}
            transparent
            opacity={0.22}
            roughness={0.22}
            metalness={0.03}
            transmission={0.22}
            thickness={0.3}
            clearcoat={1}
            clearcoatRoughness={0.1}
            ior={1.35}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>

        <mesh ref={coreHighlightRef} position={[-0.04, 0.05, 0.08]}>
          <sphereGeometry args={[coreBaseRadius, 24, 24]} />
          <meshBasicMaterial
            color={corePalette.highlightColor}
            transparent
            opacity={0.14}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
      </group>

      {/* Connectors between outer and inner vertices */}
      <lineSegments ref={connectorRef} renderOrder={10}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[new Float32Array(16 * 3), 3]}
          />
        </bufferGeometry>
        <lineBasicMaterial
          color={edgeColor}
          transparent
          opacity={0.45}
          depthTest={false}
          depthWrite={false}
          toneMapped={false}
        />
      </lineSegments>
    </group>
  );
};

const Scene = ({ state }: { state: OracState }) => {
  const config = STATE_CONFIGS[state];
  const isIdle = state === 'idle';
  const isThinking = state === 'thinking';
  const isSpeaking = state === 'speaking';
  const isError = state === 'error' || state === 'interrupted';
  const isListening = state === 'listening' || state === 'wake_detected';
  const sparkleCount = isThinking ? 52 : 28;
  const sparkleSize = isThinking ? 1.8 : 1.55;
  const sparkleSpeed = config.pulseRate * (isIdle ? 0.28 : isThinking ? 0.24 : 0.18);
  const sparkleOpacity = isError ? 0.14 : isIdle ? 0.28 : isSpeaking ? 0.5 : isThinking ? 0.58 : 0.42;
  const pointLightIntensity = isListening ? 0.04 : isSpeaking ? 0.22 : isThinking ? 0.18 : 0.1;
  const spotLightIntensity = isListening ? 0.08 : isSpeaking ? 0.42 : isThinking ? 0.34 : 0.18;

  const glitchDelay = useMemo(() => new THREE.Vector2(0.1, 0.3), []);
  const glitchDuration = useMemo(() => new THREE.Vector2(0.1, 0.2), []);
  const glitchStrength = useMemo(() => new THREE.Vector2(0.2, 0.4), []);

  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0, 9]} fov={35} />
      <ambientLight intensity={0.28} />
      <pointLight position={[10, 10, 10]} intensity={pointLightIntensity} color={config.color} />
      <spotLight position={[-10, 10, 10]} angle={0.2} penumbra={1} intensity={spotLightIntensity} color={config.color} />
      
      <Float
        speed={1.5 * config.pulseRate} 
        rotationIntensity={0.3} 
        floatIntensity={0.5}
      >
        <group>
          <Tesseract state={state} />
          
          <Sparkles 
            count={sparkleCount} 
            scale={2.6} 
            size={sparkleSize} 
            speed={sparkleSpeed} 
            color={config.color} 
            opacity={sparkleOpacity}
          />
        </group>
      </Float>

      <ScanLine state={state} />
      <WaveHalo state={state} />

      <GlassEnvironment />

      <EffectComposer>
        <Bloom 
          luminanceThreshold={0.8} 
          mipmapBlur 
          intensity={config.bloomIntensity} 
          radius={isListening ? 0.24 : 0.4} 
        />
        <Noise opacity={0.05} />
        {state === 'interrupted' ? (
          <Glitch 
            delay={glitchDelay} 
            duration={glitchDuration} 
            strength={glitchStrength} 
          />
        ) : <></>}
      </EffectComposer>
    </>
  );
};

export const OracDisplay: React.FC<OracDisplayProps> = ({
  state,
  message,
  showTranscriptPanels = SHOW_TRANSCRIPT_PANELS,
  userTranscript = '',
  oracTranscript = '',
  renderResetKey = 0,
  onRenderRecovery,
}) => {
  const config = STATE_CONFIGS[state];
  const isIdle = state === 'idle';
  const isListening = state === 'listening' || state === 'wake_detected';
  const isTurnActive =
    state === 'wake_detected' ||
    state === 'listening' ||
    state === 'transcribing' ||
    state === 'thinking' ||
    state === 'tool_calling' ||
    state === 'speaking';
  const leftTranscript =
    userTranscript.trim() || 'No recent utterance';
  const rightTranscript =
    oracTranscript.trim() || 'Waiting for response';
  const leftPanelEmphasis = isIdle ? 0.98 : isTurnActive ? 1.01 : 1;
  const rightPanelEmphasis = isIdle ? 0.98 : state === 'speaking' ? 1.03 : 1.01;

  return (
    <div className="relative flex flex-col items-center justify-center w-full h-full bg-[#03070d] overflow-hidden rounded-2xl border border-[#1b5f91]/10">
      <motion.div 
        className="absolute inset-0 transition-colors duration-1000 pointer-events-none"
        style={{
          background: `radial-gradient(circle at center, ${config.color}${isListening ? '28' : '18'} 0%, transparent ${isListening ? '66%' : '72%'})`,
        }}
        animate={{
          opacity: isListening ? [0.42, 0.62, 0.42] : [0.18, 0.26, 0.18],
        }}
        transition={{ duration: isListening ? 8.5 : 5, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="absolute top-8 z-10 flex flex-col items-center opacity-85">
        <div className="rounded-full border border-[#4fc3f7]/20 bg-[#04111a]/55 px-4 py-2 text-[11px] font-black uppercase tracking-[0.55em] text-[#8fdcff] shadow-[0_0_24px_rgba(79,195,247,0.18)] backdrop-blur-md sm:px-6 sm:py-2.5 sm:text-[14px]">
          Orac Neural Interface
        </div>
        <div className="mt-3 h-px w-40 bg-gradient-to-r from-transparent via-[#4fc3f7] to-transparent sm:w-56" />
      </div>

      <div
        className={`relative z-10 grid h-full w-full min-h-0 gap-4 ${
          showTranscriptPanels
            ? 'px-3 sm:px-4 xl:grid-cols-[minmax(15.5rem,17rem)_minmax(0,1fr)_minmax(18rem,22rem)]'
            : 'grid-cols-1'
        }`}
      >
        {showTranscriptPanels && (
          <div className="hidden min-h-0 xl:flex">
            <TranscriptPanel
              title="You"
              text={leftTranscript}
              placeholder="Listening for wake word"
              accentColor="#8fdcff"
              emphasis={leftPanelEmphasis}
              muted={isIdle}
            />
          </div>
        )}

        <div className="w-full h-full min-h-0 relative">
          <CanvasErrorBoundary resetKey={renderResetKey}>
            <Canvas key={renderResetKey} gl={{ antialias: false }} dpr={[1, 1.5]}>
              <CanvasDiagnostics onRecovery={onRenderRecovery} />
              <Scene state={state} />
            </Canvas>
          </CanvasErrorBoundary>
        </div>

        {showTranscriptPanels && (
          <div className="hidden min-h-0 xl:flex">
            <TranscriptPanel
              title="Orac"
              text={rightTranscript}
              placeholder="Waiting for response"
              accentColor={config.color}
              emphasis={rightPanelEmphasis}
              muted={isIdle}
              bodyClassName="pb-8"
              fadeStop={98}
            />
          </div>
        )}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={state}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 1.05 }}
          className="absolute bottom-14 z-10 flex flex-col items-center pointer-events-none"
        >
          <div 
            className="font-bold tracking-[1em] text-[11px] uppercase mb-5 text-center transition-colors duration-700"
            style={{ 
              color: config.color,
              textShadow: `0 0 25px ${config.color}88`
            }}
          >
            {state.replace('_', ' ')}
          </div>
          {message && (
            <div className="text-[#72899a] text-[11px] font-medium tracking-[0.15em] text-center max-w-sm opacity-40 leading-relaxed border-t border-[#1b5f91]/20 pt-5 px-10">
              {message}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      <div className="absolute inset-4 pointer-events-none border border-[#1b5f91]/5 rounded-3xl">
        <div className="absolute top-6 left-6 w-8 h-8 border-t border-l border-[#1b5f91]/30" />
        <div className="absolute top-6 right-6 w-8 h-8 border-t border-r border-[#1b5f91]/30" />
        <div className="absolute bottom-6 left-6 w-8 h-8 border-b border-l border-[#1b5f91]/30" />
        <div className="absolute bottom-6 right-6 w-8 h-8 border-b border-r border-[#1b5f91]/30" />
      </div>
    </div>
  );
};
