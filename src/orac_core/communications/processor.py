"""Provide the authoritative transport-neutral Orac processing entrypoint."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Validates requests and coordinates one injected core runtime.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol

from lib.logutil import log_call
from orac_core.communications.models import MessageRole
from orac_core.communications.models import OracRequest
from orac_core.communications.models import OracResponse
from orac_core.communications.models import ProcessingError
from orac_core.communications.models import StreamEvent
from orac_core.communications.models import StreamEventKind

EventSink = Callable[[StreamEvent], Awaitable[None]]


class CommunicationsRuntime(Protocol):
    """Narrow collaborator implemented by the host orchestration runtime."""

    @log_call
    async def process(
        self,
        request: OracRequest,
        *,
        event_sink: EventSink | None = None,
    ) -> OracResponse:
        """Process one validated canonical request."""


class OracRequestProcessor:
    """Validate and execute all supported requests through one core runtime."""

    def __init__(self, runtime: CommunicationsRuntime) -> None:
        """Initialise the processor with the authoritative runtime."""
        self._runtime = runtime

    async def process(
        self,
        request: OracRequest,
        *,
        event_sink: EventSink | None = None,
    ) -> OracResponse:
        """Validate and process one canonical request exactly once."""
        error = self._validate(request)
        if error is not None:
            if event_sink is not None:
                await event_sink(
                    StreamEvent(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        sequence=1,
                        kind=StreamEventKind.ERROR,
                        error=error,
                    )
                )
            return OracResponse(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                conversation_id=request.conversation.conversation_id,
                model=request.model,
                message=None,
                finish_reason="error",
                error=error,
            )
        last_sequence = 0

        async def tracked_sink(event: StreamEvent) -> None:
            nonlocal last_sequence
            last_sequence = max(last_sequence, event.sequence)
            if event_sink is not None:
                await event_sink(event)

        try:
            return await self._runtime.process(
                request,
                event_sink=tracked_sink if event_sink is not None else None,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            error = ProcessingError(
                code="INTERNAL_ERROR",
                message="Request processing failed.",
                retryable=True,
                correlation_id=request.correlation_id,
            )
            if event_sink is not None:
                await event_sink(
                    StreamEvent(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        sequence=last_sequence + 1,
                        kind=StreamEventKind.ERROR,
                        error=error,
                    )
                )
            return OracResponse(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                conversation_id=request.conversation.conversation_id,
                model=request.model,
                message=None,
                finish_reason="error",
                error=error,
            )

    @log_call
    async def stream(self, request: OracRequest) -> AsyncIterator[StreamEvent]:
        """Queue-wrap ``process`` without introducing a second engine."""
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue()

        async def sink(event: StreamEvent) -> None:
            await queue.put(event)

        task = asyncio.create_task(self.process(request, event_sink=sink))
        emitted_terminal = False
        last_sequence = 0
        try:
            while not task.done() or not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue
                emitted_terminal = event.kind in {
                    StreamEventKind.COMPLETE,
                    StreamEventKind.ERROR,
                }
                last_sequence = max(last_sequence, event.sequence)
                yield event
            response = await task
            if not emitted_terminal:
                kind = (
                    StreamEventKind.ERROR
                    if response.error is not None
                    else StreamEventKind.COMPLETE
                )
                yield StreamEvent(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    sequence=last_sequence + 1,
                    kind=kind,
                    result=response if response.error is None else None,
                    error=response.error,
                )
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @staticmethod
    def _validate(request: OracRequest) -> ProcessingError | None:
        """Return a safe error when a canonical request is invalid."""
        if not request.request_id.strip() or not request.correlation_id.strip():
            return ProcessingError(
                code="INVALID_REQUEST",
                message="Request and correlation identifiers are required.",
                retryable=False,
                correlation_id=request.correlation_id,
            )
        if not request.principal.username.strip():
            return ProcessingError(
                code="UNAUTHORISED",
                message="An authenticated principal is required.",
                retryable=False,
                correlation_id=request.correlation_id,
            )
        if request.message.role is not MessageRole.USER:
            return ProcessingError(
                code="INVALID_REQUEST",
                message="The current message must have the user role.",
                retryable=False,
                correlation_id=request.correlation_id,
            )
        if not request.message.text.strip():
            return ProcessingError(
                code="INVALID_REQUEST",
                message="A user message is required.",
                retryable=False,
                correlation_id=request.correlation_id,
            )
        if (
            request.selected_capability_id
            and request.restrictions.capability_ids is not None
            and request.selected_capability_id
            not in request.restrictions.capability_ids
        ):
            return ProcessingError(
                code="CAPABILITY_NOT_AUTHORISED",
                message="The requested capability is not authorised.",
                retryable=False,
                correlation_id=request.correlation_id,
            )
        if (
            request.model
            and request.model != "orac"
            and request.restrictions.model_ids is not None
            and request.model not in request.restrictions.model_ids
        ):
            return ProcessingError(
                code="MODEL_NOT_AUTHORISED",
                message="The requested model is not authorised.",
                retryable=False,
                correlation_id=request.correlation_id,
            )
        return None
