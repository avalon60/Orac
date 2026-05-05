"""TCP listener for Orac protocol frames."""

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Handles NDJSON request, response, and streaming event frames.

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
        voice_session_ids: set[str] = set()
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                incoming = data.decode("utf-8", errors="replace").rstrip("\r\n")
                print(f"📥 Received: {incoming}")
                self._remember_voice_session(incoming, voice_session_ids)

                streamer = getattr(self.orchestrator, "handle_request_events", None)
                if callable(streamer):
                    async for out in streamer(incoming):
                        if not isinstance(out, str):
                            out = json.dumps(out, ensure_ascii=False)
                        await self._write_frame(writer, out)
                else:
                    out = await self.orchestrator.handle_request(incoming)
                    if not isinstance(out, str):
                        out = json.dumps(out, ensure_ascii=False)
                    await self._write_frame(writer, out)
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            self._cancel_voice_sessions(voice_session_ids)
            try:
                writer.close()
                await writer.wait_closed()
            finally:
                print(f"🔴 Connection closed: {addr}")

    def _remember_voice_session(
        self,
        incoming: str,
        voice_session_ids: set[str],
    ) -> None:
        """Remember the client voice session id from one request frame."""
        try:
            env = json.loads(incoming)
        except Exception:
            return
        if not isinstance(env, dict):
            return
        meta = env.get("meta")
        if not isinstance(meta, dict):
            return
        session_id = str(meta.get("session_id") or "").strip()
        if session_id:
            voice_session_ids.add(session_id)

    def _cancel_voice_sessions(self, voice_session_ids: set[str]) -> None:
        """Cancel voice output associated with a closed client connection."""
        # TODO: When Orac request execution has an upstream cancellation
        # token, connect this same client/session cancellation path to the
        # active LLM stream as well as downstream TTS/audio.
        canceller = getattr(self.orchestrator, "cancel_voice_session", None)
        if not callable(canceller):
            return
        for session_id in voice_session_ids:
            try:
                discarded = canceller(session_id=session_id)
                print(
                    f"🔇 Cancelled voice session {session_id}; "
                    f"discarded {discarded} queued chunk(s)"
                )
            except Exception as exc:
                print(f"⚠️ Voice cancellation failed for {session_id}: {exc}")

    async def start_server(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        addr = server.sockets[0].getsockname()
        print(f"🚀 OracListener started on {addr}")
        async with server:
            await server.serve_forever()

    async def _write_frame(
        self,
        writer: asyncio.StreamWriter,
        frame: str,
    ) -> None:
        """Write one NDJSON protocol frame to the client."""
        preview = frame if len(frame) <= 300 else frame[:300] + "…"
        print(f"📤 Sending: {preview}")
        writer.write((frame + "\n").encode("utf-8"))
        await writer.drain()



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
