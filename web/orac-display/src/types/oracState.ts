
export type OracState =
  | 'idle'
  | 'wake_detected'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'checking_online'
  | 'reading_sources'
  | 'tool_calling'
  | 'speaking'
  | 'interrupted'
  | 'complete'
  | 'error';

export interface OracDisplayProps {
  state: OracState;
  statusMessage?: string;
}
