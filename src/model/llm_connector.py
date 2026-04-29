"""LLM connector implementations for Orac backends."""

# Author: Clive Bostock
# Date: 2026-04-27
# Description: Provides LM Studio and Ollama connector implementations for
#   Orac, including Ollama retry handling for truncated responses.

from model.orac_abc import LLMConnectorABC, MODEL_SERVICE_DESCRIPTORS
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from typing import Any, cast
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home


APP_HOME = project_home()
RESOURCES_DIR = APP_HOME / 'resources'
CONFIG_DIR = RESOURCES_DIR / 'config'
CONFIG_FILE_PATH = CONFIG_DIR / 'orac.ini'


class LLMConnector(LLMConnectorABC):
    def __init__(self, model_service_id: str):
        self.config_mgr = ConfigManager(config_file_path=CONFIG_FILE_PATH)
        self.llm_service_id = self.config_mgr.config_value(
            section='service', key='llm_service_id'
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


import requests
import re
import time
import math
from urllib.parse import urlparse, urlunparse
from lib.logutil import Logger

class OllamaConnector(LLMConnector):
    def __init__(self, model_name: str, service_url: str):
        super().__init__("ollama")
        self.logger = Logger()
        self.logger.log_info('OllamaConnector instantiated')
        self.model_name = model_name.strip()
        clean_url = service_url.strip()
        parsed_url = urlparse(clean_url)
        if not parsed_url.scheme:
            clean_url = f"http://{clean_url}"
            parsed_url = urlparse(clean_url)
        self.service_url = urlunparse(parsed_url._replace(path="")).rstrip("/")

        self.logger.log_info(f"🔗 Ollama base_url: '{self.service_url}'")
        self.logger.log_info(f"📝 Ollama model: '{self.model_name}'")
        print(f"🔗 Ollama base_url: '{self.service_url}'")
        print(f"📝 Ollama model: '{self.model_name}'")


        # config -> default hide reasoning (strip_reasoning_tags=true => default_show_reasoning False)
        strip_reasoning = (
            self.config_mgr.config_value("settings", "strip_reasoning_tags", default="true")
            .strip().lower() in {"1", "true", "yes", "on", "y"}
        )
        self.default_show_reasoning = not strip_reasoning

        # HTTP timeouts
        req_to = int(self.config_mgr.config_value("service", "llm_timeout", default="60"))
        # split connect/read to avoid hanging the server-side loop
        self._connect_timeout = 5
        self._read_timeout = min(req_to, 25)
        self.default_num_predict = max(
            1,
            self.config_mgr.int_config_value(
                "service",
                "default_num_predict",
                default=120,
            ),
        )
        self.num_predict_incr_pct = max(
            1,
            self.config_mgr.int_config_value(
                "service",
                "num_predict_incr_pct",
                default=100,
            ),
        )
        self._max_num_predict_retries = 2

        # Keep the connector hint minimal. User-facing behaviour belongs in
        # Orac's main system prompt policy, not the transport wrapper.
        self.system_hint = (
            "You are Orac. Be concise. If the user poses a hypothetical or "
            "counterfactual premise, answer under that premise and do not "
            "correct it unless the user explicitly asks you to verify facts."
        )

    # ---------- helpers ----------

    def _strip_visible_think(self, text: str) -> str:
        """Remove <think>…</think>; if closing tag missing, drop from <think> to end."""
        if not isinstance(text, str):
            return ""
        if "<think>" in text and "</think>" not in text:  # dangling / truncated block
            return text.split("<think>", 1)[0].strip()
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def _post_json(self, url: str, payload: dict) -> dict:
        t0 = time.perf_counter()
        r = requests.post(url, json=payload, timeout=(self._connect_timeout, self._read_timeout))
        r.raise_for_status()
        data = r.json()
        dt = time.perf_counter() - t0
        model = data.get("model") or self.model_name
        done = data.get("done_reason")
        pe = data.get("prompt_eval_count")
        ce = data.get("eval_count")
        self.logger.log_info(f"⏱️ Ollama RT: {dt:.2f}s model={model} done={done} pe={pe} ce={ce}")
        return data

    def _next_num_predict(self, current_num_predict: int) -> int:
        """Return the next token budget after a truncated response."""
        increment = max(
            1,
            math.ceil(current_num_predict * (self.num_predict_incr_pct / 100.0)),
        )
        return current_num_predict + increment

    def _chat_once(
        self,
        prompt: str,
        *,
        show_reasoning: bool,
        num_predict: int,
        use_system: bool,
    ) -> dict[str, Any]:
        url = f"{self.service_url}/api/chat"
        msgs = [{"role": "user", "content": prompt}]
        if use_system and self.system_hint:
            msgs.insert(0, {"role": "system", "content": self.system_hint})

        payload = {
            "model": self.model_name,
            "messages": msgs,
            "stream": False,
            "think": bool(show_reasoning),   # we’ll force False in send_prompt
            "options": {
                "num_predict": int(num_predict),
                "temperature": 0.2,
                "repeat_penalty": 1.1,
            }
        }
        self.logger.log_info(
            f"➡️ /api/chat think={payload['think']} stream={payload['stream']} "
            f"np={payload['options']['num_predict']} sys={use_system}"
        )
        data = self._post_json(url, payload)
        text = (data.get("message") or {}).get("content") or data.get("response") or ""
        return {
            "text": text if isinstance(text, str) else str(text),
            "done_reason": data.get("done_reason"),
        }

    def _generate_once(self, prompt: str, *, num_predict: int) -> dict[str, Any]:
        url = f"{self.service_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": int(num_predict),
                "temperature": 0.2,
                "repeat_penalty": 1.1,
            }
        }
        self.logger.log_info(f"➡️ /api/generate np={num_predict}")
        data = self._post_json(url, payload)
        text = data.get("response") or ""
        return {
            "text": text if isinstance(text, str) else str(text),
            "done_reason": data.get("done_reason"),
        }

    def _run_with_num_predict_growth(
        self,
        runner,
        *,
        runner_name: str,
        initial_num_predict: int,
    ) -> str:
        """Retry a completion with a larger token budget after truncation."""
        num_predict = max(1, int(initial_num_predict))
        last_text = ""

        for attempt in range(self._max_num_predict_retries + 1):
            result = runner(num_predict)
            text = self._strip_visible_think(result.get("text", "")).strip()
            done_reason = str(result.get("done_reason") or "").strip().lower()

            if text:
                last_text = text

            if done_reason != "length":
                return text

            if attempt >= self._max_num_predict_retries:
                return last_text

            next_num_predict = self._next_num_predict(num_predict)
            self.logger.log_info(
                f"↩️ Retrying {runner_name} after truncated response "
                f"(done=length): num_predict {num_predict} -> {next_num_predict}"
            )
            num_predict = next_num_predict

        return last_text

    # ---------- public API ----------

    def list_models(self):
        """List available models from Ollama."""
        response = requests.get(
            f"{self.service_url}/api/tags",
            timeout=(self._connect_timeout, self._read_timeout),
        )
        response.raise_for_status()
        return [
            model.get("name")
            for model in response.json().get("models", [])
            if isinstance(model.get("name"), str) and model.get("name").strip()
        ]

    def send_prompt(self, prompt_type: str, prompt: str, stream: bool = False) -> str:
        """
        FORCE think=False (hide visible chain-of-thought). For very short prompts (like "Hi"),
        avoid a system prompt to match the working curl. Retry with larger budget, then fall back
        to /api/generate. Always return non-empty text.
        """
        # Hard override: do NOT show visible reasoning
        show_reasoning = False

        # Heuristic: for very short inputs, match your curl exactly (no system message)
        p = (prompt or "").strip()
        is_very_short = len(p) <= 12  # "Hi", "Hello", etc.

        text = self._run_with_num_predict_growth(
            lambda num_predict: self._chat_once(
                p,
                show_reasoning=False,
                num_predict=num_predict,
                use_system=not is_very_short,
            ),
            runner_name="/api/chat",
            initial_num_predict=self.default_num_predict,
        )
        if text:
            return text

        # Fallback: /api/generate with the same truncation-aware budget growth.
        text = self._run_with_num_predict_growth(
            lambda num_predict: self._generate_once(
                p or "Say hi",
                num_predict=num_predict,
            ),
            runner_name="/api/generate",
            initial_num_predict=self.default_num_predict,
        )
        if text:
            return text

        # Absolute last resort: avoid empty payload to server
        return "Hello! 👋"
