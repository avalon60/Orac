const DIAGNOSTIC_PREFIX = '[orac-display]';
const SUSPEND_GAP_THRESHOLD_MS = 30_000;
const HEARTBEAT_INTERVAL_MS = 5_000;
const VISIBILITY_RESUME_THRESHOLD_MS = 5_000;
const MAX_DETAIL_LENGTH = 2_000;

export type DisplayRecoveryReason =
  | 'bfcache-pageshow'
  | 'timer-gap'
  | 'visibility-resume'
  | 'webgl-context-lost'
  | 'webgl-context-restored';

type RecoveryHandler = (reason: DisplayRecoveryReason) => void;

type DiagnosticEvent = {
  timestamp: string;
  message: string;
  detail?: string;
};

function summariseDiagnosticDetail(detail: unknown): string {
  if (detail instanceof Error) {
    return `${detail.name}: ${detail.message}\n${detail.stack || ''}`.slice(
      0,
      MAX_DETAIL_LENGTH,
    );
  }

  if (detail instanceof Event) {
    return `${detail.type} event`.slice(0, MAX_DETAIL_LENGTH);
  }

  try {
    return JSON.stringify(detail).slice(0, MAX_DETAIL_LENGTH);
  } catch {
    return String(detail).slice(0, MAX_DETAIL_LENGTH);
  }
}

function dispatchDiagnosticEvent(event: DiagnosticEvent): void {
  window.dispatchEvent(
    new CustomEvent<DiagnosticEvent>('orac-display-diagnostic', {
      detail: event,
    }),
  );
}

export function logDisplayDiagnostic(
  message: string,
  detail?: unknown,
): void {
  const timestamp = new Date().toISOString();
  const diagnosticEvent: DiagnosticEvent = {
    timestamp,
    message,
    detail:
      detail === undefined ? undefined : summariseDiagnosticDetail(detail),
  };

  if (detail === undefined) {
    console.info(`${DIAGNOSTIC_PREFIX} ${timestamp} ${message}`);
    dispatchDiagnosticEvent(diagnosticEvent);
    return;
  }

  console.info(`${DIAGNOSTIC_PREFIX} ${timestamp} ${message}`, detail);
  dispatchDiagnosticEvent(diagnosticEvent);
}

export function installGlobalDisplayDiagnostics(
  onRecoveryRequested: RecoveryHandler,
): () => void {
  let hiddenAt = 0;
  let lastHeartbeat = Date.now();

  const handleError = (event: ErrorEvent) => {
    console.error(`${DIAGNOSTIC_PREFIX} window.error`, {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      error: event.error,
    });
  };

  const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
    console.error(`${DIAGNOSTIC_PREFIX} unhandledrejection`, event.reason);
  };

  const handleVisibilityChange = () => {
    if (document.visibilityState === 'hidden') {
      hiddenAt = Date.now();
      logDisplayDiagnostic('document hidden');
      return;
    }

    logDisplayDiagnostic('document visible');
    if (hiddenAt && Date.now() - hiddenAt >= VISIBILITY_RESUME_THRESHOLD_MS) {
      onRecoveryRequested('visibility-resume');
    }
    hiddenAt = 0;
  };

  const handlePageShow = (event: PageTransitionEvent) => {
    logDisplayDiagnostic('pageshow', { persisted: event.persisted });
    if (event.persisted) {
      onRecoveryRequested('bfcache-pageshow');
    }
  };

  const handleOnline = () => logDisplayDiagnostic('browser online');
  const handleOffline = () => logDisplayDiagnostic('browser offline');

  const heartbeatId = window.setInterval(() => {
    const now = Date.now();
    const gap = now - lastHeartbeat;
    lastHeartbeat = now;

    if (gap >= SUSPEND_GAP_THRESHOLD_MS) {
      logDisplayDiagnostic('large browser timer gap detected', { gap });
      onRecoveryRequested('timer-gap');
    }
  }, HEARTBEAT_INTERVAL_MS);

  window.addEventListener('error', handleError);
  window.addEventListener('unhandledrejection', handleUnhandledRejection);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  window.addEventListener('pageshow', handlePageShow);
  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);

  logDisplayDiagnostic('frontend diagnostics installed');

  return () => {
    window.clearInterval(heartbeatId);
    window.removeEventListener('error', handleError);
    window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    window.removeEventListener('pageshow', handlePageShow);
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
  };
}

export function attachCanvasDiagnostics(
  canvas: HTMLCanvasElement,
  onRecoveryRequested: RecoveryHandler,
): () => void {
  const handleContextLost = (event: Event) => {
    event.preventDefault();
    console.warn(`${DIAGNOSTIC_PREFIX} webglcontextlost`, event);
    onRecoveryRequested('webgl-context-lost');
  };

  const handleContextRestored = (event: Event) => {
    logDisplayDiagnostic('webglcontextrestored', event);
    onRecoveryRequested('webgl-context-restored');
  };

  canvas.addEventListener('webglcontextlost', handleContextLost);
  canvas.addEventListener('webglcontextrestored', handleContextRestored);
  logDisplayDiagnostic('canvas diagnostics attached');

  return () => {
    canvas.removeEventListener('webglcontextlost', handleContextLost);
    canvas.removeEventListener('webglcontextrestored', handleContextRestored);
  };
}
