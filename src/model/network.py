# model/network.py
import asyncio
import json
from typing import Any


class OracListener:
    def __init__(self, orchestrator: Any, host: str = "127.0.0.1", port: int = 8765):
        self.orchestrator = orchestrator
        self.host = host
        self.port = port

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        print(f"🟢 Connection from {addr}")
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                incoming = data.decode("utf-8", errors="replace").rstrip("\r\n")
                print(f"📥 Received: {incoming}")

                out = await self.orchestrator.handle_request(incoming)
                if not isinstance(out, str):                # future-proof
                    out = json.dumps(out, ensure_ascii=False)

                preview = out if len(out) <= 300 else out[:300] + "…"
                print(f"📤 Sending: {preview}")              # DEBUG: what actually goes on the wire

                writer.write((out + "\n").encode("utf-8"))  # exactly one NDJSON line
                await writer.drain()
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            finally:
                print(f"🔴 Connection closed: {addr}")

    async def start_server(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        addr = server.sockets[0].getsockname()
        print(f"🚀 OracListener started on {addr}")
        async with server:
            await server.serve_forever()



# Optional standalone test (remove in production)
if __name__ == "__main__":
    class _EchoOrchestrator:
        async def handle_request(self, msg: str) -> str:
            # Return a minimal protocol envelope so the client expects JSON
            return json.dumps({
                "v": 1, "type": "response", "id": "res_test", "reply_to": "req_test",
                "ts": "2025-08-17T00:00:00Z", "route": "orac.prompt",
                "meta": {"status": "ok", "model": "echo", "latency_ms": 0},
                "payload": {"content": f"echo: {msg}", "stop_reason": "stop",
                            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}},
                "error": None
            }, ensure_ascii=False)

    listener = OracListener(_EchoOrchestrator())
    asyncio.run(listener.start_server())
