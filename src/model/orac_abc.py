# llm/base_connector.py
from abc import ABC, abstractmethod

MODEL_SERVICE_DESCRIPTORS = {
    "lmstudio": "LM Studio",
    "ollama": "Ollama",
    "openai": "OpenAI ChatGPT API"
}

class LLMConnectorABC(ABC):
    def __init__(self, model_service_id:str):
        self.model_interface_id = model_service_id

    @abstractmethod
    def send_prompt(self, prompt_type: str, prompt: str) -> str:
        """Send a prompt to the LLM and return the response.

        Args:
            prompt_type: 'C' => Conditioning prompt; 'U' => User dialogue (conversational or a directive)
            prompt: The prompt text
        """

    @abstractmethod
    def interface_name(self) -> str:
        """Return the backend name (e.g. 'LM Studio', 'Ollama', 'OpenAI ChatGPT API'...)."""
        pass

    @abstractmethod
    def interface_id(self) -> str:
        """Return the backend name (e.g. 'lmstudio', 'ollama', 'openai'...)."""
        pass

    @abstractmethod
    def list_models(self):
        """Return a list of available models within the LM service."""
        pass