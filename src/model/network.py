import asyncio
import json

class OracListener:
    def __init__(self, orchestrator, host="127.0.0.1", port=8765):
        self.orchestrator = orchestrator
        self.host = host
        self.port = port

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"🟢 Connection from {addr}")

        try:
            while True:  # 🔄 Loop to handle multiple messages
                data = await reader.readline()
                if not data:
                    # Client disconnected
                    break

                message = data.decode().strip()
                print(f"📥 Received: {message}")

                # Pass message to Orac’s orchestrator
                response = await self.orchestrator.handle_request(message)

                response_json = json.dumps({"response": response})
                writer.write((response_json + "\n").encode())
                await writer.drain()
                print(f"📤 Sent: {response_json}")

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"🔴 Connection closed: {addr}")

    async def start_server(self):
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        addr = server.sockets[0].getsockname()
        print(f"🚀 OracListener started on {addr}")
        async with server:
            await server.serve_forever()

# Entrypoint for testing
if __name__ == "__main__":
    listener = OracListener()
    asyncio.run(listener.start_server())

