"""Oracle orchestrator, orac.py"""
import asyncio
import subprocess
import re
import json
from model.network import OracListener
from model.llm_connector import LMStudioConnector, OllamaConnector
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons
from lib.logutil import Logger
logger = Logger()

APP_HOME = project_home()
RESOURCES_DIR = APP_HOME / 'resources'
CONFIG_DIR = RESOURCES_DIR / 'config'
CONFIG_FILE_PATH = CONFIG_DIR / 'orac.ini'


class Orac:
    """
    Orac is the AI orchestrator that routes messages
    to the LLM and skills system.
    """
    def __init__(self):
        self.config_mgr = ConfigManager(config_file_path=CONFIG_FILE_PATH)
        self.llm_service_id = self.config_mgr.config_value(
            config_section='service', config_key='llm_service_id'
        )
        self.model_name = self.config_mgr.config_value(
            config_section='service', config_key='default_model_name'
        )
        self.service_url = self.config_mgr.config_value(
            config_section='service', config_key='service_url'
        )
        self.strip_reasoning_tags = self.config_mgr.config_value(
            config_section='settings', config_key='strip_reasoning_tags', default="true"
        ).lower() == "true"

        # Map LLM service names to connector classes
        service_map = {
            "ollama": OllamaConnector,
            "lmstudio": LMStudioConnector
        }

        try:
            # 🛡 Validate model availability
            self._validate_or_pull_model()

            # Initialize connector
            self.llm = service_map[self.llm_service_id](
                service_url=self.service_url,
                model_name=self.model_name
            )

        except KeyError:
            message = f"{Icons.error} LLM service not implemented: {self.llm_service_id}"
            raise NotImplementedError(message)

        print(f"{Icons.robot} Orac orchestrator initialized with model: {self.model_name}")
        print(f"{Icons.settings} Reasoning tags stripped by default: {self.strip_reasoning_tags}")

    def _validate_or_pull_model(self):
        """
        Validates that the configured model is available in the LLM service.
        For Ollama, auto-pulls the model if missing.
        """
        if self.llm_service_id == "ollama":
            try:
                output = subprocess.check_output(["ollama", "list"], text=True)
                if self.model_name not in output:
                    print(f"{Icons.warn} Model '{self.model_name}' not found in Ollama. Pulling it now...")
                    subprocess.run(["ollama", "pull", self.model_name], check=True)
                    print(f"{Icons.tick} Model '{self.model_name}' pulled successfully.")
                else:
                    print(f"{Icons.tick} Model '{self.model_name}' is already available in Ollama.")
            except FileNotFoundError:
                raise RuntimeError(f"{Icons.error} Ollama is not installed or not in PATH.")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"{Icons.error} Failed to pull model '{self.model_name}': {e}")

        elif self.llm_service_id == "lmstudio":
            import requests
            try:
                response = requests.get(f"{self.service_url}/v1/models")
                response.raise_for_status()
                models = response.json().get("data", [])
                available_models = [model["id"] for model in models]
                if self.model_name not in available_models:
                    raise RuntimeError(
                        f"{Icons.error} Model '{self.model_name}' not loaded in LM Studio at {self.service_url}."
                        f"\n{Icons.right_arrow} Please load it in LM Studio and try again."
                    )
                else:
                    print(f"{Icons.tick} Model '{self.model_name}' is loaded in LM Studio.")
            except requests.exceptions.ConnectionError:
                raise RuntimeError(
                    f"{Icons.error} Could not connect to LM Studio server at {self.service_url}."
                )
            except Exception as e:
                raise RuntimeError(
                    f"{Icons.error} Error validating model in LM Studio: {e}"
                )

        else:
            raise RuntimeError(f"{Icons.error} Unknown LLM service: {self.llm_service_id}")

    def _strip_reasoning_tags(self, text: str) -> str:
        """
        Strips <think>...</think> blocks from the text if enabled.
        """
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    async def handle_request(self, message: str) -> str:
        """
        Process incoming message from OracListener.
        Expects a JSON payload or plain string.
        """
        try:
            # Try to parse message as JSON
            try:
                payload = json.loads(message)
                prompt = payload.get("prompt", "")
                client = payload.get("client", "unknown")
                show_reasoning = payload.get("show_reasoning", not self.strip_reasoning_tags)
            except json.JSONDecodeError:
                # Fallback: treat plain string as prompt
                prompt = message.strip()
                client = "legacy-client"
                show_reasoning = not self.strip_reasoning_tags

            print(f"{Icons.info} [{client}] Prompt received: {prompt}")

            # Call the LLM connector
            raw_response = self.llm.send_prompt(prompt_type="U", prompt=prompt)

            # Apply reasoning tag stripping if needed
            if show_reasoning:
                clean_response = raw_response
            else:
                clean_response = self._strip_reasoning_tags(raw_response)

            print(f"{Icons.robot} Raw response: {raw_response}")
            print(f"{Icons.docs} Cleaned response: {clean_response}")

            return clean_response

        except Exception as e:
            print(f"{Icons.error} Error while processing request: {e}")
            return f"Orac encountered an error: {e}"


async def main():
    orchestrator = Orac()
    listener = OracListener(orchestrator=orchestrator, host="127.0.0.1", port=8765)
    await listener.start_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"{Icons.stop} Orac shutting down.")
