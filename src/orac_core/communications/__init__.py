"""Expose Orac's transport-neutral communications API."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Provides stable imports for canonical communications contracts.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from orac_core.communications.models import CapabilityRestrictions
from orac_core.communications.models import ConversationContext
from orac_core.communications.models import Message
from orac_core.communications.models import MessageRole
from orac_core.communications.models import OracRequest
from orac_core.communications.models import OracResponse
from orac_core.communications.models import PrincipalContext
from orac_core.communications.models import ProcessingError
from orac_core.communications.models import StreamEvent
from orac_core.communications.models import StreamEventKind
from orac_core.communications.models import ToolCall
from orac_core.communications.models import ToolDefinition
from orac_core.communications.models import ToolResult
from orac_core.communications.models import Usage
from orac_core.communications.processor import CommunicationsRuntime
from orac_core.communications.processor import EventSink
from orac_core.communications.processor import OracRequestProcessor

__all__ = [
    "CapabilityRestrictions",
    "CommunicationsRuntime",
    "ConversationContext",
    "EventSink",
    "Message",
    "MessageRole",
    "OracRequest",
    "OracRequestProcessor",
    "OracResponse",
    "PrincipalContext",
    "ProcessingError",
    "StreamEvent",
    "StreamEventKind",
    "ToolCall",
    "ToolDefinition",
    "ToolResult",
    "Usage",
]
