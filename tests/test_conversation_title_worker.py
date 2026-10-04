"""Verify scheduled conversation-title processing and failure isolation."""

# Author: Clive Bostock
# Date: 04-Oct-2026
# Description: Tests the durable conversation title worker behavior.

from __future__ import annotations

from pathlib import Path

from orac_core.conversation_title.worker import ConversationTitleService, sanitize_title


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FakeRepository:
    """Record the worker's durable request lifecycle calls."""

    def __init__(self) -> None:
        """Provide one claim and bounded dialogue."""
        self.claimed = False
        self.completed = []
        self.failed = []

    def claim(self, **kwargs):
        """Return a request once."""
        if self.claimed:
            return None
        self.claimed = True
        return {"title_request_id": 7, "conversation_id": 9,
                "lease_token": "token", "attempts": 1}

    def dialogue(self, conversation_id):
        """Return one user turn for generation."""
        assert conversation_id == 9
        return [{"role": "user", "content": "Python context managers"}]

    def complete(self, **kwargs):
        """Record successful completion."""
        self.completed.append(kwargs)

    def fail(self, **kwargs):
        """Record retryable failure."""
        self.failed.append(kwargs)


class FakeConnector:
    """Provide a controlled title model response."""

    def __init__(self, model, service_url, *, result="Managing Python Resources"):
        """Capture connector construction without network calls."""
        self.model = model
        self.service_url = service_url
        self.result = result
        self._read_timeout = 0

    def send_prompt(self, **kwargs):
        """Return the configured title."""
        return self.result


def test_title_worker_completes_one_claim() -> None:
    """A scheduled tick completes a claimed request through the repository."""
    repository = FakeRepository()
    worker = ConversationTitleService(
        repository=repository, connector_factory=FakeConnector)
    worker.tick(None)
    assert len(repository.completed) == 1
    assert repository.completed[0]["title"] == "Managing Python Resources"
    assert not repository.failed


def test_title_worker_records_generation_failure() -> None:
    """A failed model call is recorded for durable retry."""
    repository = FakeRepository()

    def failing_connector(model, service_url):
        raise TimeoutError("model timed out")

    worker = ConversationTitleService(
        repository=repository, connector_factory=failing_connector)
    worker.tick(None)
    assert not repository.completed
    assert len(repository.failed) == 1
    assert repository.failed[0]["retryable"] is True
    assert worker.health(None) is False


def test_title_sanitization_is_bounded() -> None:
    """Generated titles cannot exceed the configured display limits."""
    title = sanitize_title('"one two three four five six seven eight!"')
    assert title == "One Two Three Four Five Six"
    assert len(title) <= 120


def test_title_request_view_can_be_regranted_to_runtime() -> None:
    """The CODE layer must be able to expose its title-request projection."""
    grant_sql = (
        PROJECT_ROOT
        / "resources"
        / "db"
        / "schema"
        / "orac_api"
        / "grant"
        / "conversation_title_api_access.sql"
    ).read_text(encoding="utf-8").lower()

    assert (
        "grant read on orac_api.conversation_title_requests_v "
        "to orac_code with grant option;"
    ) in grant_sql
