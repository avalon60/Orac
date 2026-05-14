
import React, { useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { 
  PerspectiveCamera, 
  Environment, 
  Edges, 
  Float, 
  MeshTransmissionMaterial,
  Sparkles,
} from '@react-three/drei';
import { EffectComposer, Bloom, Noise, Glitch } from '@react-three/postprocessing';
import * as THREE from 'three';
import { motion, AnimatePresence } from 'framer-motion';
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
}

const SHOW_TRANSCRIPT_PANELS =
  (import.meta.env.VITE_ORAC_SHOW_TRANSCRIPT_PANELS || '')
    .trim()
    .toLowerCase() === 'true';

const STATE_CONFIGS: Record<OracState, StateConfig> = {
  idle: { color: '#4fc3f7', bloomIntensity: 0.5, rotationSpeed: 0.15, distortion: 0.1, pulseRate: 0.5, scale: 1, transmission: 0.9 },
  wake_detected: { color: '#ffffff', bloomIntensity: 3.0, rotationSpeed: 1.5, distortion: 0.5, pulseRate: 10, scale: 1.25, transmission: 0.5 },
  listening: { color: '#7af7ff', bloomIntensity: 1.5, rotationSpeed: 0.4, distortion: 0.2, pulseRate: 2, scale: 1.1, transmission: 0.8 },
  transcribing: { color: '#b8f2ff', bloomIntensity: 1.2, rotationSpeed: 1.2, distortion: 0.4, pulseRate: 4, scale: 1.05, transmission: 0.8 },
  thinking: { color: '#b69cff', bloomIntensity: 2.0, rotationSpeed: 0.8, distortion: 0.6, pulseRate: 1, scale: 1.15, transmission: 0.7 },
  tool_calling: { color: '#31e6d0', bloomIntensity: 2.5, rotationSpeed: 1.8, distortion: 0.3, pulseRate: 6, scale: 1.2, transmission: 0.6 },
  speaking: { color: '#9be7ff', bloomIntensity: 2.0, rotationSpeed: 0.6, distortion: 0.2, pulseRate: 3, scale: 1.15, transmission: 0.8 },
  interrupted: { color: '#ffb02e', bloomIntensity: 2.5, rotationSpeed: 2.0, distortion: 1.0, pulseRate: 8, scale: 0.95, transmission: 0.4, glitchIntensity: 1 },
  complete: { color: '#4fc3f7', bloomIntensity: 1.0, rotationSpeed: 0.15, distortion: 0.1, pulseRate: 0.2, scale: 1.05, transmission: 0.95 },
  error: { color: '#ff5b4f', bloomIntensity: 1.5, rotationSpeed: 0.05, distortion: 0.5, pulseRate: 12, scale: 1.0, transmission: 0.5 },
};

const CORE_PALETTES: Record<OracState, CorePalette> = {
  idle: { color: '#edf8ff', glowColor: '#d7ecff', highlightColor: '#ffffff' },
  wake_detected: { color: '#fff3d3', glowColor: '#ffe2a8', highlightColor: '#fff9ec' },
  listening: { color: '#eefcff', glowColor: '#dff7ff', highlightColor: '#ffffff' },
  transcribing: { color: '#eefaff', glowColor: '#d7f3ff', highlightColor: '#ffffff' },
  thinking: { color: '#f3f7ff', glowColor: '#d7e4ff', highlightColor: '#ffffff' },
  tool_calling: { color: '#f8f1dd', glowColor: '#f0deaf', highlightColor: '#fff8e8' },
  speaking: { color: '#f1cd82', glowColor: '#ffdea0', highlightColor: '#fff2cf' },
  interrupted: { color: '#ffe0ab', glowColor: '#ffd186', highlightColor: '#fff3d4' },
  complete: { color: '#effaff', glowColor: '#d9efff', highlightColor: '#ffffff' },
  error: { color: '#d3deea', glowColor: '#b9cadf', highlightColor: '#edf4fb' },
};

const createCoreGlowTexture = () => {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;

  const context = canvas.getContext('2d');
  if (!context) {
    return null;
  }

  const gradient = context.createRadialGradient(46, 42, 6, 64, 64, 58);
  gradient.addColorStop(0, 'rgba(255,255,255,0.96)');
  gradient.addColorStop(0.16, 'rgba(255,255,255,0.7)');
  gradient.addColorStop(0.38, 'rgba(255,255,255,0.26)');
  gradient.addColorStop(0.62, 'rgba(255,255,255,0.08)');
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

  const bodyGradient = context.createRadialGradient(44, 40, 8, 64, 64, 58);
  bodyGradient.addColorStop(0, 'rgba(255,255,255,0.98)');
  bodyGradient.addColorStop(0.14, 'rgba(255,248,225,0.96)');
  bodyGradient.addColorStop(0.34, 'rgba(247,212,130,0.74)');
  bodyGradient.addColorStop(0.62, 'rgba(198,139,55,0.42)');
  bodyGradient.addColorStop(1, 'rgba(78,48,18,0.02)');

  context.fillStyle = bodyGradient;
  context.fillRect(0, 0, canvas.width, canvas.height);

  const shadow = context.createRadialGradient(78, 82, 2, 64, 64, 58);
  shadow.addColorStop(0, 'rgba(57,34,10,0.24)');
  shadow.addColorStop(1, 'rgba(57,34,10,0)');
  context.fillStyle = shadow;
  context.fillRect(0, 0, canvas.width, canvas.height);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
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

const WaveHalo = ({ state }: { state: OracState }) => {
  const ref = useRef<THREE.Group>(null);
  const config = STATE_CONFIGS[state];

  useFrame((sceneState) => {
    if (ref.current && state === 'speaking') {
      const t = sceneState.clock.elapsedTime * 2;
      ref.current.children.forEach((child, i) => {
        const s = 1 + Math.sin(t - i * 0.5) * 0.2;
        child.scale.set(s, s, s);
        const material = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
        material.opacity = (1 - (s - 0.8) / 0.4) * 0.3;
      });
    }
  });

  if (state !== 'speaking') return null;

  return (
    <group ref={ref}>
      {[0, 1, 2].map((i) => (
        <mesh key={i}>
          <ringGeometry args={[2.2 + i * 0.2, 2.25 + i * 0.2, 64]} />
          <meshBasicMaterial color={config.color} transparent opacity={0} side={THREE.DoubleSide} toneMapped={false} />
        </mesh>
      ))}
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
  const groupRef = useRef<THREE.Group>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const outerRef = useRef<THREE.Mesh>(null);
  const coreHaloRef = useRef<THREE.Mesh>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const coreGlowRef = useRef<THREE.Mesh>(null);
  const coreHighlightRef = useRef<THREE.Mesh>(null);
  const connectorRef = useRef<THREE.LineSegments>(null);
  const stateEnteredAtRef = useRef<number>(performance.now() * 0.001);
  
  const config = STATE_CONFIGS[state];
  const corePalette = CORE_PALETTES[state];
  const coreGlowTexture = useMemo(() => createCoreGlowTexture(), []);
  const coreBodyTexture = useMemo(() => createCoreBodyTexture(), []);

  // Base sizes
  const outerBaseSize = 2;
  const innerBaseSize = 1.12;
  const coreBaseRadius = 0.16;

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
    let connectorOpacity = 0.45;
    let coreScale = coreBaseRadius;
    let coreOpacity = 0.12;
    let coreGlow = 0.45;
    let coreHaloOpacity = 0.14;
    let coreHighlightOpacity = 0.35;
    let coreColor: THREE.ColorRepresentation = corePalette.color;
    let coreGlowColor: THREE.ColorRepresentation = corePalette.glowColor;
    let coreHighlightColor: THREE.ColorRepresentation = corePalette.highlightColor;

    switch (state) {
      case 'idle':
        // 3% breathing for inner cube
        innerScale *= (1 + Math.sin(t * 1.5) * 0.03);
        {
          const idlePulse = (Math.sin(t * 0.8) + 1) * 0.5;
          coreScale *= 1 + idlePulse * 0.02;
          coreOpacity = 0.12 + idlePulse * 0.03;
          coreGlow = 1.5 + idlePulse * 0.12;
          coreHaloOpacity = 0.14 + idlePulse * 0.05;
          coreHighlightOpacity = 0.18 + idlePulse * 0.05;
          coreColor = new THREE.Color(corePalette.color).lerp(new THREE.Color('#f7fcff'), 0.3 + idlePulse * 0.25);
          coreGlowColor = new THREE.Color(corePalette.glowColor).lerp(new THREE.Color('#f9fdff'), 0.35 + idlePulse * 0.2);
          coreHighlightColor = new THREE.Color(corePalette.highlightColor).lerp(new THREE.Color('#ffffff'), 0.22 + idlePulse * 0.2);
        }
        break;
      case 'listening':
        // Expanded + gentle pulse
        innerScale *= (1.1 + Math.sin(t * 4) * 0.05);
        connectorOpacity = 0.55;
        coreScale *= (1.02 + Math.sin(t * 2.5) * 0.04);
        coreOpacity = 0.16;
        coreGlow = 0.65;
        coreHaloOpacity = 0.18;
        coreHighlightOpacity = 0.24;
        break;
      case 'thinking':
        // Out of phase breathing
        const thinkT = t * 3;
        innerScale *= (1.1 + Math.sin(thinkT) * 0.1);
        // Shimmering connectors
        connectorOpacity = 0.5 + Math.sin(t * 10) * 0.15;
        coreScale *= (1.03 + Math.sin(t * 2.2) * 0.05);
        coreOpacity = 0.18;
        coreGlow = 0.78;
        coreHaloOpacity = 0.2;
        coreHighlightOpacity = 0.26;
        break;
      case 'speaking':
        // Rhythmic pulse
        innerScale *= (1.1 + Math.sin(t * 10) * 0.15);
        connectorOpacity = 0.6;
        {
          const pulsar = Math.pow((Math.sin(t * 10) + 1) * 0.5, 1.8);
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
          coreScale *= 1.04 + pulsar * 0.07;
          coreOpacity = 0.18 + pulsar * 0.2;
          coreGlow = 0.95 + pulsar * 3.0;
          coreHaloOpacity = 0.12 + pulsar * 0.36;
          coreHighlightOpacity = 0.24 + pulsar * 0.28;
          coreColor = peakColor;
          coreGlowColor = peakGlowColor;
          coreHighlightColor = peakHighlightColor;
        }
        break;
      case 'wake_detected':
        // Sharp expansion
        innerScale *= 1.4;
        connectorOpacity = 0.85;
        const wakePulse = Math.max(0, 1 - stateAge * 1.6);
        coreScale *= 1.12 + wakePulse * 0.08;
        coreOpacity = 0.18 + wakePulse * 0.12;
        coreGlow = 0.95 + wakePulse * 0.35;
        coreHaloOpacity = 0.18 + wakePulse * 0.12;
        coreHighlightOpacity = 0.3 + wakePulse * 0.14;
        break;
      case 'error':
        // Reduced scale and dimmed connectors
        innerScale *= 0.8;
        connectorOpacity = 0.25;
        coreScale *= 0.92;
        coreOpacity = 0.04;
        coreGlow = 0.2;
        coreHaloOpacity = 0.04;
        coreHighlightOpacity = 0.1;
        break;
      case 'transcribing':
        innerScale *= (1.05 + Math.sin(t * 6) * 0.05);
        coreScale *= (1.01 + Math.sin(t * 3) * 0.03);
        coreOpacity = 0.14;
        coreGlow = 0.58;
        coreHaloOpacity = 0.16;
        coreHighlightOpacity = 0.22;
        break;
      case 'tool_calling':
        innerScale *= (1.2 + Math.sin(t * 8) * 0.1);
        connectorOpacity = 0.7;
        coreScale *= (1.08 + Math.sin(t * 8) * 0.06);
        coreOpacity = 0.2;
        coreGlow = 0.9;
        coreHaloOpacity = 0.2;
        coreHighlightOpacity = 0.24;
        break;
    }

    innerRef.current.scale.setScalar(innerScale / innerBaseSize);
    outerRef.current.scale.setScalar(outerScale / outerBaseSize);
    coreRef.current.scale.setScalar(coreScale / coreBaseRadius);
    const coreMaterial = coreRef.current.material as THREE.MeshPhysicalMaterial;
    coreMaterial.color.set(coreColor);
    coreMaterial.emissive.set(coreColor);
    coreMaterial.opacity = coreOpacity;
    coreMaterial.emissiveIntensity = coreGlow;

    if (coreHaloRef.current) {
      coreHaloRef.current.scale.setScalar((coreScale / coreBaseRadius) * 2.3);
      const haloMaterial = coreHaloRef.current.material as THREE.MeshBasicMaterial;
      haloMaterial.color.set(coreGlowColor);
      haloMaterial.opacity = coreHaloOpacity * 0.9;
    }

    if (coreGlowRef.current) {
      coreGlowRef.current.scale.setScalar((coreScale / coreBaseRadius) * 1.45);
      const glowMaterial = coreGlowRef.current.material as THREE.MeshBasicMaterial;
      glowMaterial.color.set(coreGlowColor);
      glowMaterial.opacity = coreHaloOpacity;
    }

    if (coreHighlightRef.current) {
      coreHighlightRef.current.scale.setScalar((coreScale / coreBaseRadius) * 0.55);
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
          thickness={2.5}
          chromaticAberration={0.15}
          anisotropy={0.2}
          distortion={config.distortion}
          distortionScale={0.4}
          temporalDistortion={0.1}
          clearcoat={1}
          attenuationDistance={1}
          attenuationColor={config.color}
          color={config.color}
          transparent
          opacity={config.transmission}
          roughness={0.05}
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
          backsideThickness={1.5}
          thickness={0.8}
          chromaticAberration={0.15}
          anisotropy={0.2}
          distortion={config.distortion}
          distortionScale={0.4}
          temporalDistortion={0.1}
          clearcoat={1}
          attenuationDistance={1}
          attenuationColor={config.color}
          color={config.color}
          transparent
          opacity={config.transmission}
          roughness={0.05}
          ior={1.45}
        />
        <Edges threshold={15} color={edgeColor}>
          <meshBasicMaterial color={edgeColor} toneMapped={false} />
        </Edges>
      </mesh>

      {/* Central Core Sphere */}
      <group renderOrder={4}>
        <mesh ref={coreHaloRef}>
          <sphereGeometry args={[coreBaseRadius, 32, 32]} />
          <meshBasicMaterial
            map={coreGlowTexture || undefined}
            color={corePalette.glowColor}
            transparent
            opacity={0.08}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>

        <mesh ref={coreGlowRef}>
          <sphereGeometry args={[coreBaseRadius, 32, 32]} />
          <meshBasicMaterial
            map={coreGlowTexture || undefined}
            color={corePalette.glowColor}
            transparent
            opacity={0.14}
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

        <mesh ref={coreHighlightRef} position={[-0.035, 0.035, 0.055]}>
          <sphereGeometry args={[coreBaseRadius, 24, 24]} />
          <meshBasicMaterial
            color={corePalette.highlightColor}
            transparent
            opacity={0.3}
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
  const sparkleCount = isThinking ? 52 : 28;
  const sparkleSize = isThinking ? 1.8 : 1.55;
  const sparkleSpeed = config.pulseRate * (isIdle ? 0.14 : isThinking ? 0.24 : 0.18);
  const sparkleOpacity = isError ? 0.14 : isIdle ? 0.28 : isSpeaking ? 0.5 : isThinking ? 0.58 : 0.42;

  const glitchDelay = useMemo(() => new THREE.Vector2(0.1, 0.3), []);
  const glitchDuration = useMemo(() => new THREE.Vector2(0.1, 0.2), []);
  const glitchStrength = useMemo(() => new THREE.Vector2(0.2, 0.4), []);

  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0, 9]} fov={35} />
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 10, 10]} intensity={1.5} color={config.color} />
      <spotLight position={[-10, 10, 10]} angle={0.2} penumbra={1} intensity={2.5} color={config.color} />
      
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

      <Environment preset="night" />

      <EffectComposer>
        <Bloom 
          luminanceThreshold={0.8} 
          mipmapBlur 
          intensity={config.bloomIntensity} 
          radius={0.4} 
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
}) => {
  const config = STATE_CONFIGS[state];
  const isIdle = state === 'idle';
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
        animate={{
          background: [
            `radial-gradient(circle at center, ${config.color}22 0%, transparent 80%)`,
            `radial-gradient(circle at center, ${config.color}33 5%, transparent 85%)`,
            `radial-gradient(circle at center, ${config.color}22 0%, transparent 80%)`,
          ]
        }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
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
          <Canvas gl={{ antialias: false }} dpr={[1, 1.5]}>
            <Scene state={state} />
          </Canvas>
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
