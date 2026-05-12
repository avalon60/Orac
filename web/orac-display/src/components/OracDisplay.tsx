
import React, { useRef, useMemo } from 'react';
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

const STATE_CONFIGS: Record<OracState, StateConfig> = {
  idle: { color: '#4fc3f7', bloomIntensity: 0.5, rotationSpeed: 0.2, distortion: 0.1, pulseRate: 0.5, scale: 1, transmission: 0.9 },
  wake_detected: { color: '#ffffff', bloomIntensity: 3.0, rotationSpeed: 2.0, distortion: 0.5, pulseRate: 10, scale: 1.25, transmission: 0.5 },
  listening: { color: '#7af7ff', bloomIntensity: 1.5, rotationSpeed: 0.5, distortion: 0.2, pulseRate: 2, scale: 1.1, transmission: 0.8 },
  transcribing: { color: '#b8f2ff', bloomIntensity: 1.2, rotationSpeed: 1.5, distortion: 0.4, pulseRate: 4, scale: 1.05, transmission: 0.8 },
  thinking: { color: '#b69cff', bloomIntensity: 2.0, rotationSpeed: 0.8, distortion: 0.6, pulseRate: 1, scale: 1.15, transmission: 0.7 },
  tool_calling: { color: '#31e6d0', bloomIntensity: 2.5, rotationSpeed: 1.8, distortion: 0.3, pulseRate: 6, scale: 1.2, transmission: 0.6 },
  speaking: { color: '#9be7ff', bloomIntensity: 2.0, rotationSpeed: 0.6, distortion: 0.2, pulseRate: 3, scale: 1.15, transmission: 0.8 },
  interrupted: { color: '#ffb02e', bloomIntensity: 2.5, rotationSpeed: 4.0, distortion: 1.0, pulseRate: 8, scale: 0.95, transmission: 0.4, glitchIntensity: 1 },
  complete: { color: '#4fc3f7', bloomIntensity: 1.0, rotationSpeed: 0.2, distortion: 0.1, pulseRate: 0.2, scale: 1.05, transmission: 0.95 },
  error: { color: '#ff5b4f', bloomIntensity: 3.5, rotationSpeed: 5.0, distortion: 0.5, pulseRate: 12, scale: 1.0, transmission: 0.5 },
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

const Crystal = ({ state, isInner }: { state: OracState; isInner?: boolean }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const config = STATE_CONFIGS[state];
  
  const size = isInner ? 1 : 2;
  const rotationDir = isInner ? -1 : 1;

  useFrame((sceneState, delta) => {
    if (meshRef.current) {
      const rotBase = config.rotationSpeed * (isInner ? 1.5 : 1);
      meshRef.current.rotation.y += delta * rotBase * rotationDir;
      meshRef.current.rotation.x += delta * (rotBase / 2) * rotationDir;
      meshRef.current.rotation.z += delta * (rotBase / 4);
      
      const pulse = Math.sin(sceneState.clock.elapsedTime * config.pulseRate) * 0.05;
      meshRef.current.scale.setScalar(config.scale + (isInner ? pulse : -pulse));
    }
  });

  const edgeColor = useMemo(() => new THREE.Color(config.color), [config.color]);

  return (
    <mesh ref={meshRef}>
      <boxGeometry args={[size, size, size]} />
      <MeshTransmissionMaterial
        backside
        backsideThickness={1.5}
        thickness={isInner ? 0.8 : 2.5}
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
      
      <Edges threshold={15} color={edgeColor}>
        <meshBasicMaterial color={edgeColor} toneMapped={false} transparent opacity={0.4} />
      </Edges>
    </mesh>
  );
};

const Scene = ({ state }: { state: OracState }) => {
  const config = STATE_CONFIGS[state];

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
          <Crystal state={state} />
          <Crystal state={state} isInner />
          
          <Sparkles 
            count={state === 'thinking' ? 40 : 20} 
            scale={2.5} 
            size={2} 
            speed={config.pulseRate * 0.2} 
            color={config.color} 
            opacity={0.6}
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

export const OracDisplay: React.FC<{ state: OracState; message?: string }> = ({ state, message }) => {
  const config = STATE_CONFIGS[state];

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

      <div className="w-full h-full relative">
        <Canvas gl={{ antialias: false }} dpr={[1, 1.5]}>
          <Scene state={state} />
        </Canvas>
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
