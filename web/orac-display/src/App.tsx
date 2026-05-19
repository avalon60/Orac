import { useEffect, useRef, useState } from 'react';

import { OracDisplay } from './components/OracDisplay';
import { OracStateControls } from './components/OracStateControls';
import {
  installGlobalDisplayDiagnostics,
  logDisplayDiagnostic,
  type DisplayRecoveryReason,
} from './displayDiagnostics';
import type { OracState } from './types/oracState';


const DEFAULT_DISPLAY_WS_URL = 'ws://127.0.0.1:8767';
const DISPLAY_WS_URL =
  import.meta.env.VITE_ORAC_DISPLAY_WS_URL?.trim() || DEFAULT_DISPLAY_WS_URL;
const SHOW_TRANSCRIPT_PANELS =
  (import.meta.env.VITE_ORAC_SHOW_TRANSCRIPT_PANELS || '')
    .trim()
    .toLowerCase() === 'true';
const RECONNECT_INITIAL_DELAY_MS = 500;
const RECONNECT_MAX_DELAY_MS = 10_000;

type ConnectionState = 'connecting' | 'connected' | 'disconnected';
type BrowserUiConfig = {
  buttons_visible?: boolean;
  show_transcript_panels?: boolean;
};
type RuntimeIdentity = {
  model: string;
  persona: string;
};
type BrowserDiagnosticEvent = CustomEvent<{
  timestamp: string;
  message: string;
  detail?: string;
}>;

function getTranscriptText(
  data: Record<string, unknown>,
  options: { preserveWhitespace?: boolean } = {},
): string {
  const candidate =
    data.text ?? data.message ?? data.delta ?? data.chunk ?? data.content;

  if (typeof candidate !== 'string') {
    return '';
  }

  return options.preserveWhitespace ? candidate : candidate.trim();
}

function getRuntimeIdentity(data: Record<string, unknown>): RuntimeIdentity | null {
  const model = typeof data.model === 'string' ? data.model.trim() : '';
  const persona = typeof data.persona === 'string' ? data.persona.trim() : '';
  const personalityName =
    typeof data.personality_name === 'string' ? data.personality_name.trim() : '';
  const personalityCode =
    typeof data.personality_code === 'string' ? data.personality_code.trim() : '';
  const resolvedPersona = persona || personalityName || personalityCode || (
    model ? 'DEFAULT' : ''
  );

  if (!model && !resolvedPersona) {
    return null;
  }

  return {
    model,
    persona: resolvedPersona,
  };
}

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState<boolean>(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia(query);
    const updateMatches = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    setMatches(mediaQuery.matches);
    mediaQuery.addEventListener('change', updateMatches);
    return () => mediaQuery.removeEventListener('change', updateMatches);
  }, [query]);

  return matches;
}

const STATE_MESSAGES: Record<OracState, string> = {
  idle: 'Awaiting directive.',
  wake_detected: 'I am listening.',
  listening: 'Processing ambient audio...',
  transcribing: 'Converting speech to intent...',
  thinking: 'Synthesizing response...',
  tool_calling: 'Executing specialised sub-routine...',
  speaking: 'Relaying synthesised output.',
  interrupted: 'Operation suspended.',
  complete: 'Task finalised.',
  error: 'Critical system anomaly detected.',
};

function App() {
  const [state, setState] = useState<OracState>('idle');
  const [message, setMessage] = useState<string>(STATE_MESSAGES.idle);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('connecting');
  const [showButtons, setShowButtons] = useState(false);
  const [showTranscriptPanels, setShowTranscriptPanels] = useState(
    SHOW_TRANSCRIPT_PANELS,
  );
  const [runtimeIdentity, setRuntimeIdentity] =
    useState<RuntimeIdentity | null>(null);
  const [userTranscript, setUserTranscript] = useState('');
  const [oracTranscript, setOracTranscript] = useState('');
  const [railExpanded, setRailExpanded] = useState(false);
  const [reconnectNonce, setReconnectNonce] = useState(0);
  const [renderResetNonce, setRenderResetNonce] = useState(0);
  const socketRef = useRef<WebSocket | null>(null);
  const diagnosticQueueRef = useRef<string[]>([]);
  const isWideScreen = useMediaQuery('(min-width: 1280px)');

  const requestDisplayRecovery = (reason: DisplayRecoveryReason) => {
    logDisplayDiagnostic('display recovery requested', { reason });
    setConnectionState('connecting');
    setReconnectNonce((value) => value + 1);
    setRenderResetNonce((value) => value + 1);
  };

  useEffect(() => {
    if (!showButtons || isWideScreen) {
      setRailExpanded(false);
    }
  }, [showButtons, isWideScreen]);

  useEffect(() => {
    const sendDiagnostic = (payload: string) => {
      const socket = socketRef.current;
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(payload);
        return;
      }

      diagnosticQueueRef.current = [
        ...diagnosticQueueRef.current.slice(-49),
        payload,
      ];
    };

    const handleDiagnostic = (event: Event) => {
      const diagnostic = event as BrowserDiagnosticEvent;
      sendDiagnostic(
        JSON.stringify({
          v: 1,
          event: 'browser.diagnostic',
          ...diagnostic.detail,
        }),
      );
    };

    window.addEventListener('orac-display-diagnostic', handleDiagnostic);
    return () =>
      window.removeEventListener('orac-display-diagnostic', handleDiagnostic);
  }, []);

  useEffect(
    () => installGlobalDisplayDiagnostics(requestDisplayRecovery),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimerId: number | null = null;
    let retryDelay = RECONNECT_INITIAL_DELAY_MS;

    const clearReconnectTimer = () => {
      if (reconnectTimerId !== null) {
        window.clearTimeout(reconnectTimerId);
        reconnectTimerId = null;
      }
    };

    const scheduleReconnect = () => {
      if (cancelled) {
        return;
      }

      clearReconnectTimer();
      setConnectionState('disconnected');
      reconnectTimerId = window.setTimeout(() => {
        reconnectTimerId = null;
        connect();
      }, retryDelay);
      retryDelay = Math.min(retryDelay * 2, RECONNECT_MAX_DELAY_MS);
    };

    const connect = () => {
      if (cancelled) {
        return;
      }

      clearReconnectTimer();
      setConnectionState((current) =>
        current === 'connected' ? 'connected' : 'connecting',
      );

      try {
        logDisplayDiagnostic('opening display WebSocket', {
          url: DISPLAY_WS_URL,
          reconnectNonce,
        });
        socket = new WebSocket(DISPLAY_WS_URL);
        socketRef.current = socket;
      } catch (error) {
        console.error('⚠️ Failed to open Orac display WebSocket:', error);
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        if (cancelled) {
          return;
        }
        retryDelay = RECONNECT_INITIAL_DELAY_MS;
        logDisplayDiagnostic('display WebSocket connected');
        setConnectionState('connected');

        diagnosticQueueRef.current.forEach((payload) => socket?.send(payload));
        diagnosticQueueRef.current = [];
      };

      socket.onmessage = (event) => {
        if (cancelled) {
          return;
        }

        try {
          const data = JSON.parse(String(event.data)) as {
            event?: string;
            message?: string;
            state?: string;
            buttons_visible?: boolean;
            show_transcript_panels?: boolean;
            text?: string;
            delta?: string;
            chunk?: string;
            content?: string;
            model?: string;
            persona?: string;
            personality_code?: string;
            personality_name?: string;
          };
          const transcriptText = getTranscriptText(
            data as Record<string, unknown>,
          );

          if (data.event === 'state_changed' && data.state) {
            const newState = data.state.toLowerCase() as OracState;
            setState(newState);
            if (data.message) {
              setMessage(data.message);
            } else {
              setMessage(STATE_MESSAGES[newState] || '');
            }
            setConnectionState('connected');
          } else if (data.event === 'status_message' && data.message) {
            setMessage(data.message);
            setConnectionState('connected');
          } else if (data.event === 'ui_config') {
            const uiConfig = data as BrowserUiConfig;
            if (typeof uiConfig.buttons_visible === 'boolean') {
              setShowButtons(uiConfig.buttons_visible);
            }
            if (typeof uiConfig.show_transcript_panels === 'boolean') {
              setShowTranscriptPanels(uiConfig.show_transcript_panels);
            }
            setConnectionState('connected');
          } else if (data.event === 'runtime.identity') {
            const identity = getRuntimeIdentity(data as Record<string, unknown>);
            if (identity) {
              setRuntimeIdentity(identity);
            }
            setConnectionState('connected');
          } else if (
            data.event === 'transcript.turn.clear'
          ) {
            setUserTranscript('');
            setOracTranscript('');
            setConnectionState('connected');
          } else if (
            data.event === 'transcript.user.final' ||
            data.event === 'voice_stt_final' ||
            data.event === 'stt_final'
          ) {
            setUserTranscript(transcriptText);
            setOracTranscript('');
            setConnectionState('connected');
          } else if (
            data.event === 'transcript.orac.start' ||
            data.event === 'stream_start'
          ) {
            setOracTranscript(transcriptText);
            setConnectionState('connected');
          } else if (
            data.event === 'transcript.orac.delta' ||
            data.event === 'text_delta'
          ) {
            const deltaText = getTranscriptText(
              data as Record<string, unknown>,
              { preserveWhitespace: true },
            );
            if (deltaText) {
              setOracTranscript((current) => `${current}${deltaText}`);
            }
            setConnectionState('connected');
          } else if (
            data.event === 'transcript.orac.final' ||
            data.event === 'stream_end' ||
            data.event === 'response'
          ) {
            if (transcriptText) {
              setOracTranscript(transcriptText);
            }
            setConnectionState('connected');
          }
        } catch (error) {
          console.warn('⚠️ Failed to parse display payload:', error);
        }
      };

      socket.onclose = () => {
        logDisplayDiagnostic('display WebSocket closed');
        if (socketRef.current === socket) {
          socketRef.current = null;
        }
        socket = null;
        if (!cancelled) {
          scheduleReconnect();
        }
      };

      socket.onerror = (event) => {
        console.warn('⚠️ Orac display WebSocket error:', event);
        // The close handler owns reconnect scheduling.
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearReconnectTimer();
      socket?.close();
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
      socket = null;
    };
  }, [reconnectNonce]);

  const handleManualStateChange = (newState: OracState) => {
    setState(newState);
    setMessage(STATE_MESSAGES[newState]);
  };

  const connectionLabel =
    connectionState === 'connected'
      ? 'Live'
      : connectionState === 'connecting'
        ? 'Connecting'
        : 'Offline';
  const runtimeIdentityLabel = runtimeIdentity
    ? [runtimeIdentity.model, runtimeIdentity.persona]
        .filter(Boolean)
        .join('/')
    : '';

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-[#03070d] text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(79,195,247,0.16),_transparent_42%),linear-gradient(180deg,_rgba(3,7,13,0.45),_rgba(3,7,13,0.9))]" />

      <div className="pointer-events-none absolute inset-x-4 top-4 z-20 sm:inset-x-6">
        <div className="flex items-start justify-between gap-4">
          <div className="rounded-full border border-[#4fc3f7]/20 bg-[#06131d]/80 px-4 py-2 text-[10px] font-bold uppercase tracking-[0.45em] text-[#8fdcff] shadow-[0_0_20px_rgba(79,195,247,0.14)] backdrop-blur-md">
            Orac Display
          </div>
          <div
            className={`rounded-full border px-4 py-2 text-[10px] font-bold uppercase tracking-[0.35em] backdrop-blur-md ${
              connectionState === 'connected'
                ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
                : connectionState === 'connecting'
                  ? 'border-amber-300/30 bg-amber-300/10 text-amber-100'
                  : 'border-red-400/30 bg-red-400/10 text-red-100'
            }`}
          >
            {connectionLabel}
          </div>
        </div>
        {runtimeIdentityLabel && (
          <div className="absolute left-1/2 top-12 max-w-[calc(100vw-2rem)] -translate-x-1/2 truncate rounded-full border border-[#4fc3f7]/20 bg-[#06131d]/72 px-4 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.28em] text-[#8fdcff]/80 shadow-[0_0_20px_rgba(79,195,247,0.12)] backdrop-blur-md sm:top-0 sm:max-w-[min(34rem,calc(100vw-21rem))] sm:px-5">
            {runtimeIdentityLabel}
          </div>
        )}
      </div>

      {connectionState !== 'connected' && (
        <div className="pointer-events-none absolute inset-x-4 top-20 z-20 flex justify-center sm:inset-x-6">
          <div className="max-w-2xl rounded-3xl border border-[#4fc3f7]/15 bg-[#06131d]/80 px-6 py-4 text-center shadow-[0_0_40px_rgba(3,7,13,0.65)] backdrop-blur-xl">
            <div className="text-[10px] font-bold uppercase tracking-[0.45em] text-[#8fdcff]">
              {connectionState === 'connecting'
                ? 'Connecting to display stream'
                : 'Display offline'}
            </div>
            <div className="mt-2 text-[12px] tracking-[0.18em] text-[#b8d9ee]">
              Waiting for {DISPLAY_WS_URL}. The UI will reconnect automatically.
            </div>
          </div>
        </div>
      )}

      <div className="relative z-10 flex h-full w-full flex-col p-3 pt-16 sm:p-4 sm:pt-20">
        <div
          className={`mx-auto grid h-full w-full items-stretch gap-4 ${
            showButtons && isWideScreen
              ? 'xl:grid-cols-[minmax(0,1fr)_19rem]'
              : 'grid-cols-1'
          }`}
        >
          <div className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-[2rem] border border-[#1b5f91]/20 bg-[#03070d]/90 shadow-[0_30px_120px_rgba(0,0,0,0.75)] backdrop-blur-xl">
            <div className="relative min-h-0 flex-1">
              <OracDisplay
                state={state}
                message={message}
                showTranscriptPanels={showTranscriptPanels}
                userTranscript={userTranscript}
                oracTranscript={oracTranscript}
                renderResetKey={renderResetNonce}
                onRenderRecovery={requestDisplayRecovery}
              />
              {connectionState !== 'connected' && (
                <div className="pointer-events-none absolute inset-0 bg-[#03070d]/35" />
              )}
            </div>
          </div>
          {showButtons && isWideScreen && (
            <aside className="flex h-full min-h-0 flex-col overflow-hidden rounded-[2rem] border border-[#1b5f91]/25 bg-[#04101a]/92 shadow-[0_30px_100px_rgba(0,0,0,0.55)] backdrop-blur-xl">
              <div className="border-b border-[#1b5f91]/20 px-5 py-4">
                <div className="text-[10px] font-bold uppercase tracking-[0.45em] text-[#8fdcff]">
                  DEBUG STATE CONTROLS
                </div>
                <div className="mt-2 text-[11px] tracking-[0.2em] text-[#9bbad0]">
                  Optional control rail
                </div>
              </div>
              <OracStateControls
                currentState={state}
                onStateChange={handleManualStateChange}
                className="flex-1 px-4 py-4"
              />
            </aside>
          )}
        </div>

        {showButtons && !isWideScreen && (
          <div className="absolute inset-x-3 bottom-3 z-30 sm:inset-x-4">
            <div className="rounded-[1.75rem] border border-[#1b5f91]/25 bg-[#04101a]/96 shadow-[0_24px_80px_rgba(0,0,0,0.7)] backdrop-blur-xl">
              <button
                type="button"
                onClick={() => setRailExpanded((value) => !value)}
                className="flex w-full items-center justify-between gap-4 rounded-[1.75rem] px-5 py-4 text-left"
              >
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.45em] text-[#8fdcff]">
                    DEBUG STATE CONTROLS
                  </div>
                  <div className="mt-1 text-[11px] tracking-[0.2em] text-[#9bbad0]">
                    {railExpanded ? 'Tap to collapse' : 'Tap to expand'}
                  </div>
                </div>
                <div className="rounded-full border border-[#4fc3f7]/20 bg-[#03070d] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.35em] text-[#8fdcff]">
                  {railExpanded ? 'Hide' : 'Show'}
                </div>
              </button>
              {railExpanded && (
                <div className="max-h-[42vh] border-t border-[#1b5f91]/20">
                  <OracStateControls
                    currentState={state}
                    onStateChange={handleManualStateChange}
                    className="max-h-[42vh] px-4 py-4"
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
