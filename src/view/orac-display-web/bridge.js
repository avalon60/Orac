
import net from 'net';
import { WebSocketServer, WebSocket } from 'ws';

// Temporary compatibility bridge. Python now owns the browser transport.
const TCP_PORT = 8766;
const WS_PORT = 8767;

// WebSocket Server
const wss = new WebSocketServer({ port: WS_PORT });
console.log(`🚀 WebSocket Bridge: Listening for browser connections on ws://localhost:${WS_PORT}`);

wss.on('connection', (ws) => {
  console.log('💻 Browser connected to bridge');
  ws.on('close', () => console.log('❌ Browser disconnected'));
});

function broadcast(data) {
  const message = data.toString();
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  });
}

// TCP Server (Emulates orac_atom_display.py listener)
const tcpServer = net.createServer((socket) => {
  console.log('📡 Orac Backend connected to bridge');
  
  socket.on('data', (data) => {
    console.log(`📩 Received from Orac: ${data.toString().trim()}`);
    broadcast(data);
  });

  socket.on('end', () => console.log('🔌 Orac Backend disconnected'));
  socket.on('error', (err) => console.error('⚠️ TCP Socket Error:', err));
});

tcpServer.listen(TCP_PORT, '127.0.0.1', () => {
  console.log(`🔗 TCP Bridge: Listening for Orac backend on 127.0.0.1:${TCP_PORT}`);
});
