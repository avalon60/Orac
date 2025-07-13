"""
Thin TCP client for Orac orchestrator (with JSON decoding)
"""

import asyncio
import textwrap
import json
import re
from lib.icons import Icons  # 🆕 Use icon library

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
WRAP_WIDTH = 100

# Toggle to show or strip <think>...</think> tags
SHOW_REASONING = False


def strip_reasoning_tags(text: str) -> str:
    """
    Strips <think>...</think> blocks from the text unless SHOW_REASONING is True.
    """
    if SHOW_REASONING:
        return text
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


async def tcp_client(host=DEFAULT_HOST, port=DEFAULT_PORT):
    print(f"{Icons.rocket} Connecting to Orac at {host}:{port} ...")

    try:
        reader, writer = await asyncio.open_connection(host, port)
        print(f"{Icons.robot} Connected. Type 'exit' to quit.\n")

        while True:
            user_input = input(f"{Icons.right_arrow} You: ").strip()
            if user_input.lower() == "exit":
                print(f"{Icons.wave} Exiting.")
                break

            # Send message to Orac
            writer.write((user_input + "\n").encode())
            await writer.drain()

            # Read response from Orac
            response = await reader.readline()
            response_text = response.decode().strip()

            # 👇 Attempt JSON decoding
            try:
                data = json.loads(response_text)
                message = data.get("response", response_text)
            except json.JSONDecodeError:
                # Fallback: treat as plain text
                message = response_text

            # Strip <think>...</think> tags if disabled
            clean_message = strip_reasoning_tags(message)

            wrapped_response = textwrap.fill(clean_message, width=WRAP_WIDTH)
            print(f"{Icons.robot} Orac: {wrapped_response}\n")

    except ConnectionRefusedError:
        print(f"{Icons.error} Could not connect to Orac at {host}:{port}. Is it running?")
    except KeyboardInterrupt:
        print(f"\n{Icons.wave} Client terminated by user.")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except NameError:
            pass  # writer was never created


if __name__ == "__main__":
    asyncio.run(tcp_client())
