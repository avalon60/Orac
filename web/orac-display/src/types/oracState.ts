
export type OracState =
  | 'idle'
  | 'wake_detected'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'tool_calling'
  | 'speaking'
  | 'interrupted'
  | 'complete'
  | 'error';

export interface OracDisplayProps {
  state: OracState;
  statusMessage?: string;
}
