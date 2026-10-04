"""Generate conversation titles outside the interactive response path."""

# Author: Clive Bostock
# Date: 04-Oct-2026
# Description: Implements the supervised scheduled conversation-title worker.

from __future__ import annotations

import os
import re
import socket
from typing import Any, Callable

from model.llm_connector import OllamaConnector

from .repository import ConversationTitleRepository


class ConversationTitleService:
    """Process one bounded batch of durable title requests per scheduled tick."""

    def __init__(
        self,
        logger: Any | None = None,
        config_mgr: Any | None = None,
        manifest: Any | None = None,
        *,
        repository: ConversationTitleRepository | None = None,
        connector_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        """Initialise the worker with injectable repository and connector factory."""
        del manifest
        self._logger = logger
        self._config_mgr = config_mgr
        self._repository = repository or ConversationTitleRepository()
        self._connector_factory = connector_factory or OllamaConnector
        self._owner_id = f"conversation-title:{socket.gethostname()}:{os.getpid()}"
        self._lease_seconds = self._int_config("lease_seconds", 180)
        self._batch_size = max(1, self._int_config("batch_size", 2))
        self.last_error: str | None = None

    def tick(self, context: Any) -> None:
        """Claim and process a bounded batch without affecting chat delivery."""
        del context
        self.last_error = None
        for _index in range(self._batch_size):
            detail = self._repository.claim(
                owner_id=self._owner_id, lease_seconds=self._lease_seconds
            )
            if detail is None:
                break
            request_id = int(detail["title_request_id"])
            lease_token = str(detail["lease_token"])
            try:
                title = self._generate_title(int(detail["conversation_id"]))
                if not title:
                    raise ValueError("Title model returned no usable title.")
                self._repository.complete(
                    request_id=request_id,
                    owner_id=self._owner_id,
                    lease_token=lease_token,
                    title=title,
                )
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"[:1000]
                self._repository.fail(
                    request_id=request_id,
                    owner_id=self._owner_id,
                    lease_token=lease_token,
                    message=self.last_error,
                    retryable=True,
                )
                self._log_warning(
                    f"Conversation title request {request_id} failed: {self.last_error}"
                )

    def health(self, context: Any) -> bool:
        """Return whether the most recent scheduled tick completed cleanly."""
        del context
        return self.last_error is None

    def _generate_title(self, conversation_id: int) -> str:
        """Generate and sanitise a short title from bounded dialogue."""
        dialogue = self._repository.dialogue(conversation_id)
        lines = ["Dialog:"]
        for message in dialogue:
            content = str(message["content"]).replace("\n", " ").strip()[:1000]
            lines.append(f"{message['role'].upper()}: {content}")
        lines.extend(
            (
                "",
                "Return a descriptive English title of no more than six words.",
                "Return only the title, without quotes, punctuation, or emojis.",
            )
        )
        connector = self._connector_factory(
            self._config("model", "llama3.1-64K:latest"),
            self._config("service_url", self._config_service_url()),
        )
        connector._read_timeout = max(5, self._int_config("timeout_seconds", 30))
        raw = connector.send_prompt(
            prompt_type="U",
            prompt="\n".join(lines),
            stream=False,
            generation_options={"num_predict": self._int_config("max_output_tokens", 24)},
        )
        if hasattr(raw, "content"):
            raw = raw.content
        return sanitize_title(str(raw))

    def _config(self, key: str, default: str) -> str:
        if self._config_mgr is None:
            return default
        return str(self._config_mgr.config_value("conversation_title", key, default=default))

    def _int_config(self, key: str, default: int) -> int:
        if self._config_mgr is None:
            return default
        return int(self._config_mgr.int_config_value("conversation_title", key, default=default))

    def _config_service_url(self) -> str:
        if self._config_mgr is None:
            return "http://127.0.0.1:11434"
        return str(
            self._config_mgr.config_value(
                "service", "service_url", default="http://127.0.0.1:11434"
            )
        )

    def _log_warning(self, message: str) -> None:
        if self._logger is not None and hasattr(self._logger, "log_warning"):
            self._logger.log_warning(message)


def sanitize_title(text: str) -> str:
    """Return title-cased, punctuation-free text bounded to six words."""
    value = re.sub(r"\s+", " ", str(text or "").strip().strip("\"'“”‘’` "))
    value = re.sub(r"[^\w\s-]", "", value)
    return " ".join(value.split()[:6]).title()[:120].strip()
