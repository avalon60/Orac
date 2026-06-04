
import net from 'net';
import { WebSocketServer, WebSocket } from 'ws';

// Bridge display pipe events to browser WebSocket clients.
const TCP_PORT = 8766;
const WS_PORT = 8767;
const BROWSER_RECONNECT_GRACE_MS = 1_000;
let latestMessage = null;
let latestRuntimeIdentity = null;
let activeBrowserClients = 0;
let browserDisconnectTimer = null;

function timestamp() {
  return new Date().toLocaleTimeString('en-GB', { hour12: false });
}

function log(message, ...args) {
  console.log(`[${timestamp()}] ${message}`, ...args);
}

function logError(message, ...args) {
  console.error(`[${timestamp()}] ${message}`, ...args);
}

function envBoolean(name, defaultValue = false) {
  const value = (process.env[name] || '').trim().toLowerCase();
  if (!value) {
    return defaultValue;
  }
  return ['1', 'true', 'yes', 'on'].includes(value);
}

function uiConfigMessage() {
  return JSON.stringify({
    v: 1,
    event: 'ui_config',
    buttons_visible: envBoolean('ORAC_DISPLAY_BUTTONS_VISIBLE', false),
    show_transcript_panels: envBoolean(
      'ORAC_DISPLAY_SHOW_TRANSCRIPT_PANELS',
      true,
    ),
  });
}

// WebSocket Server
const wss = new WebSocketServer({ port: WS_PORT });
log(`🚀 WebSocket Bridge: Listening for browser connections on ws://localhost:${WS_PORT}`);

wss.on('connection', (ws) => {
  activeBrowserClients += 1;
  if (browserDisconnectTimer) {
    clearTimeout(browserDisconnectTimer);
    browserDisconnectTimer = null;
    log('💻 Browser reconnected to bridge');
  } else {
    log('💻 Browser connected to bridge');
  }
  ws.send(uiConfigMessage());
  if (latestRuntimeIdentity) {
    ws.send(latestRuntimeIdentity);
  }
  if (latestMessage) {
    ws.send(latestMessage);
  }
  ws.on('close', () => {
    activeBrowserClients = Math.max(0, activeBrowserClients - 1);
    if (activeBrowserClients > 0) {
      return;
    }

    browserDisconnectTimer = setTimeout(() => {
      browserDisconnectTimer = null;
      if (activeBrowserClients === 0) {
        log('Browser disconnected from bridge');
      }
    }, BROWSER_RECONNECT_GRACE_MS);
  });
});

function broadcast(data) {
  const message = data.toString();
  try {
    const payload = JSON.parse(message);
    if (payload?.event === 'runtime.identity') {
      latestRuntimeIdentity = message;
    }
  } catch {
    // Keep forwarding malformed payloads for diagnostic parity.
  }
  latestMessage = message;
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  });
}

// TCP Server (Emulates orac_atom_display.py listener)
const tcpServer = net.createServer((socket) => {
  log('📡 Orac Backend connected to bridge');
  
  socket.on('data', (data) => {
    log(`📩 Received from Orac: ${data.toString().trim()}`);
    broadcast(data);
  });

  socket.on('end', () => log('🔌 Orac Backend disconnected'));
  socket.on('error', (err) => logError('⚠️ TCP Socket Error:', err));
});

tcpServer.listen(TCP_PORT, '127.0.0.1', () => {
  log(`🔗 TCP Bridge: Listening for Orac backend on 127.0.0.1:${TCP_PORT}`);
});
