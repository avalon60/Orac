# llm/base_connector.py
from model.orac_abc import LLMConnectorABC, MODEL_SERVICE_DESCRIPTORS
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
import subprocess
import requests
from pydantic import SecretStr
from typing import cast
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from urllib.parse import urlparse, urlunparse  # 🆕 For URL normalization

APP_HOME = project_home()
RESOURCES_DIR = APP_HOME / 'resources'
CONFIG_DIR = RESOURCES_DIR / 'config'
CONFIG_FILE_PATH = CONFIG_DIR / 'orac.ini'


class LLMConnector(LLMConnectorABC):
    def __init__(self, model_service_id: str):
        self.config_mgr = ConfigManager(config_file_path=CONFIG_FILE_PATH)
        self.llm_service_id = self.config_mgr.config_value(
            config_section='service', config_key='llm_service_id'
        )
        if model_service_id not in MODEL_SERVICE_DESCRIPTORS:
            valid_ids = ", ".join(MODEL_SERVICE_DESCRIPTORS.keys())
            message = (
                f'Invalid interface specification: "{model_service_id}". '
                f'Expected one of {valid_ids}'
            )
            raise ValueError(message)
        super().__init__(model_service_id)

    def list_models(self):
        """Return a list of available models within the LM service."""
        raise NotImplementedError(
            f"{self.__class__.__name__}.send_prompt() must be implemented in the subclass"
        )

    def switch_model(self, model_name):
        message = f"Switching models is not implemented for LLM Service {self.llm_service_id}"
        raise NotImplemented(message)

    def send_prompt(self, prompt_type: str, prompt: str, stream: bool = False) -> str:
        """
        Send a prompt to the LLM backend and return the response.

        Args:
            prompt_type (str): 'C' for conditioning prompt, 'U' for user dialogue.
            prompt (str): The prompt text to send.
            stream (bool): Whether to request streaming response.

        Returns:
            str: The LLM's textual response.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.send_prompt() must be implemented in the subclass"
        )

    def interface_name(self) -> str:
        """Return the backend name (e.g. 'LM Studio', 'Ollama', etc)."""
        return MODEL_SERVICE_DESCRIPTORS[self.model_interface_id]

    def interface_id(self) -> str:
        """Return the backend ID (e.g. 'lmstudio', 'ollama')."""
        return self.model_interface_id


class LMStudioConnector(LLMConnector):
    def __init__(self, model_name: str, service_url: str):
        super().__init__("lmstudio")
        # 🧹 Defensive strip
        self.model_name = model_name.strip()
        clean_url = service_url.strip()

        # 🧱 Normalize URL
        parsed_url = urlparse(clean_url)
        if not parsed_url.scheme:
            clean_url = f"http://{clean_url}"
            parsed_url = urlparse(clean_url)
        clean_url = urlunparse(parsed_url._replace(path="")).rstrip("/")

        print(f"🔗 LMStudio base_url: '{clean_url}'")
        print(f"📝 LMStudio model: '{self.model_name}'")

        self.service_url = clean_url
        self.llm_session = ChatOpenAI(
            base_url=self.service_url + "/v1",
            api_key=cast(SecretStr, "not-needed"),  # LM Studio ignores this
            model=self.model_name
        )

    def send_prompt(self, prompt_type: str, prompt: str, stream: bool = False) -> str:
        """Send prompt to LM Studio."""
        print(f"📤 Sending prompt to LM Studio (stream={stream})...")
        return self.llm_session.invoke(prompt)

    def list_models(self):
        """List available models from LM Studio."""
        response = requests.get(f"{self.service_url}/v1/models")
        return [model["id"] for model in response.json().get("data", [])]


class OllamaConnector(LLMConnector):
    def __init__(self, model_name: str, service_url: str):
        super().__init__("ollama")
        # 🧹 Defensive strip
        self.model_name = model_name.strip()
        clean_url = service_url.strip()

        # 🧱 Normalize URL
        parsed_url = urlparse(clean_url)
        if not parsed_url.scheme:
            clean_url = f"http://{clean_url}"
            parsed_url = urlparse(clean_url)
        clean_url = urlunparse(parsed_url._replace(path="")).rstrip("/")

        print(f"🔗 Ollama base_url: '{clean_url}'")
        print(f"📝 Ollama model: '{self.model_name}'")

        self.service_url = clean_url
        self.llm_session = ChatOllama(
            model=self.model_name,
            base_url=self.service_url
        )

    def send_prompt(self, prompt_type: str, prompt: str, stream: bool = False) -> str:
        """Send prompt to Ollama."""
        print(f"📤 Sending prompt to Ollama (stream={stream})...")
        if stream:
            # 🆕 Stream tokens
            result = ""
            for chunk in self.llm_session.stream(prompt):
                print(chunk, end="", flush=True)
                result += chunk
            print()  # Newline after streaming
            return result
        else:
            return self.llm_session.predict(prompt)

    def list_models(self):
        """List available models from Ollama."""
        try:
            output = subprocess.check_output(["ollama", "list"], text=True)
            models = []
            for line in output.strip().splitlines()[1:]:  # Skip header
                parts = line.split()
                if parts:
                    models.append(parts[0])
            return models
        except FileNotFoundError:
            raise RuntimeError("Ollama CLI not found. Ensure it is installed and in your PATH.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to list Ollama models: {e}")
