
import React from 'react';
import type { OracState } from '../types/oracState';

interface OracStateControlsProps {
  currentState: OracState;
  onStateChange: (state: OracState) => void;
  className?: string;
}

const STATES: OracState[] = [
  'idle',
  'wake_detected',
  'listening',
  'transcribing',
  'thinking',
  'checking_online',
  'reading_sources',
  'tool_calling',
  'speaking',
  'interrupted',
  'complete',
  'error',
];

export const OracStateControls: React.FC<OracStateControlsProps> = ({
  currentState,
  onStateChange,
  className = '',
}) => {
  return (
    <div className={`flex h-full min-h-0 flex-col gap-2 overflow-y-auto p-4 ${className}`}>
      {STATES.map((state) => (
        <button
          key={state}
          onClick={() => onStateChange(state)}
          className={`w-full rounded-xl border px-3 py-3 text-left text-xs font-bold tracking-wider uppercase transition-all ${
            currentState === state
              ? 'border-[#4fc3f7]/40 bg-[#4fc3f7] text-[#03070d] shadow-[0_0_15px_rgba(79,195,247,0.4)]'
              : 'border-[#4fc3f7]/20 bg-[#03070d] text-[#4fc3f7] hover:border-[#4fc3f7]/60 hover:bg-[#071724]'
          }`}
        >
          {state.replace('_', ' ')}
        </button>
      ))}
    </div>
  );
};
