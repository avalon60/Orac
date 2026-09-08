"""Conservative token accounting for production knowledge embeddings."""

# Author: Clive Bostock
# Date: 07-Sep-2026
# Description: Bounds Nomic embedding inputs without a heavyweight ML runtime.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass


EMBEDDING_INPUT_CONTEXT_EXCEEDED = "EMBEDDING_INPUT_CONTEXT_EXCEEDED"


class EmbeddingInputContextExceeded(ValueError):
    """Raised before embedding when an input cannot fit the active profile."""

    reason_code = EMBEDDING_INPUT_CONTEXT_EXCEEDED

    def __init__(
        self,
        *,
        estimated_tokens: int,
        usable_limit_tokens: int,
        model_context_tokens: int,
        profile_identity: str,
        input_index: int | None = None,
    ) -> None:
        """Initialise a content-free context-limit failure."""
        self.estimated_tokens = int(estimated_tokens)
        self.usable_limit_tokens = int(usable_limit_tokens)
        self.model_context_tokens = int(model_context_tokens)
        self.profile_identity = str(profile_identity)
        self.input_index = input_index
        super().__init__(
            f"{self.reason_code}: estimated_tokens={self.estimated_tokens}, "
            f"usable_limit_tokens={self.usable_limit_tokens}, "
            f"model_context_tokens={self.model_context_tokens}, "
            f"profile={self.profile_identity}"
        )


@dataclass(frozen=True, slots=True)
class ConservativeEmbeddingTokenCounter:
    """Provide a safe upper bound for BERT-family embedding token counts.

    UTF-8 byte count is deliberately conservative: a tokenizer cannot emit
    more non-special tokens than the bytes representing its input. Two model
    special tokens are then charged explicitly. This avoids shipping or
    downloading a second copy of the model vocabulary.
    """

    special_tokens: int = 2
    estimator_code: str = "utf8_byte_upper_bound_v1"

    def content_tokens(self, text: str) -> int:
        """Return the conservative non-special-token upper bound."""
        return len(str(text).encode("utf-8"))

    def input_tokens(self, text: str) -> int:
        """Return the conservative complete model-input upper bound."""
        return self.content_tokens(text) + self.special_tokens

    def truncate_to_content_tokens(self, text: str, limit: int) -> tuple[str, str]:
        """Split text at a code-point boundary within a byte-token limit."""
        if limit <= 0:
            return "", text
        used = 0
        for index, character in enumerate(text):
            width = len(character.encode("utf-8"))
            if used + width > limit:
                return text[:index], text[index:]
            used += width
        return text, ""
