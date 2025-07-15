"""
Thin TCP client for Orac orchestrator (with JSON decoding and structured logging)
"""

import asyncio
import textwrap
import json
import re
from lib.icons import Icons
import os

os.environ["LOGURU_AUTOINIT"] = "0"  # 🛑 Must come before loguru is imported!
from lib.logutil import Logger
logger = Logger()

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
    # Log for developers only (written to file)
    logger.log_info(f"{Icons.rocket} Connecting to Orac at {host}:{port} ...")

    try:
        reader, writer = await asyncio.open_connection(host, port)

        # User-facing message (clean console)
        print(f"{Icons.robot} Connected. Type 'exit' or 'quit', to quit.\n")
        logger.log_info(f"{Icons.robot} Connected.")

        while True:
            user_input = input(f"{Icons.right_arrow} You: ").strip()
            if not user_input:
                logger.log_debug("Empty input received. Skipping send.")
                continue

            if user_input.lower() == "exit" or user_input.lower() == "quit":
                print(f"{Icons.wave} Exiting client session.")
                logger.log_info("Client session exited by user.")
                break

            # Log user input (developer log)
            logger.log_debug(f"Sending user input to Orac: {user_input}")

            writer.write((user_input + "\n").encode())
            await writer.drain()

            # Read response from Orac
            response = await reader.readline()
            response_text = response.decode().strip()
            logger.log_debug(f"Raw response from Orac: {response_text}")

            # 👇 Attempt JSON decoding
            try:
                data = json.loads(response_text)
                message = data.get("response", response_text)
            except json.JSONDecodeError:
                # Fallback: treat as plain text
                message = response_text
                logger.log_warning("Response could not be parsed as JSON. Treated as plain text.")

            # Strip <think>...</think> tags if disabled
            clean_message = strip_reasoning_tags(message)
            wrapped_response = textwrap.fill(clean_message, width=WRAP_WIDTH)

            # User-facing response (clean console)
            print(f"{Icons.robot} Orac: {wrapped_response}\n")

    except ConnectionRefusedError:
        print(f"{Icons.error} Could not connect to Orac at {host}:{port}. Is it running?")
        logger.log_error(f"Could not connect to Orac at {host}:{port}.")
    except KeyboardInterrupt:
        print(f"\n{Icons.wave} Client terminated by user.")
        logger.log_warning("Client session terminated by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"{Icons.critical} Unexpected error: {e}")
        logger.log_critical(f"Unexpected error in tcp_client: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
            logger.log_info("Connection to Orac closed.")
        except NameError:
            logger.log_warning("Writer was not created; skipping close.")


if __name__ == "__main__":
    # Initialise logger at startup
    asyncio.run(tcp_client())
