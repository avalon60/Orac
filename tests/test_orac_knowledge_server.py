"""Synthetic contract tests for read-only MCP project retrieval."""
# Author: Clive Bostock
# Date: 11-Oct-2026
# Description: Verifies scope, identity, freshness, bounds, and MCP transport.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from orac_core.knowledge.project_bridge import CoreProjectRetrievalBridge
from orac_core.knowledge.project_bridge import ProjectRetrievalDenied
from orac_core.knowledge.scope import KnowledgeScope
from plugins.orac_knowledge_server.auth import McpAuthenticationError
from plugins.orac_knowledge_server.auth import McpAuthenticator
from plugins.orac_knowledge_server.service import _AuthenticatedMcpApp
from plugins.orac_knowledge_server.service import OracKnowledgeServerService


@dataclass(frozen=True)
class SyntheticChunk:
    """One synthetic Core chunk used by the service fixture."""

    document_id: int = 11
    document_version_id: int = 21
    chunk_id: int = 31
    document_title: str = "Synthetic record"
    chunk_text: str = "Synthetic clinical example only."
    chunk_metadata_json: str | None = '{"page_start": 2, "page_end": 3}'
    classification_tags: tuple[str, ...] = ("RAW_REFERENCE",)
    scope: KnowledgeScope = KnowledgeScope("PROJECT", "NHS_RECORDS")


class SyntheticRetrieval:
    """Model live Core decisions without storing real document text."""

    def __init__(self) -> None:
        self.chunk: SyntheticChunk | None = SyntheticChunk()
        self.grants = {"clive", "nicola"}
        self.calls: list[tuple[str, KnowledgeScope]] = []

    def retrieve(
        self,
        query: str,
        *,
        principal_username: str,
        scope: KnowledgeScope,
        **_limits: object,
    ) -> object:
        """Return a current synthetic chunk only to an authorised principal."""
        self.calls.append((principal_username, scope))
        if principal_username not in self.grants:
            return SimpleNamespace(status="failed", scope=scope, results=())
        results = (self.chunk,) if self.chunk is not None else ()
        return SimpleNamespace(
            status="grounded" if results else "no_evidence",
            scope=scope,
            results=results,
        )


def _bridge(retrieval: SyntheticRetrieval) -> CoreProjectRetrievalBridge:
    """Create the host-bound bridge with explicit classification policy."""
    return CoreProjectRetrievalBridge(
        project_code="NHS_RECORDS",
        allowed_classifications=frozenset({"RAW_REFERENCE"}),
        retrieval_service=retrieval,  # type: ignore[arg-type]
    )


def test_fetch_rechecks_grant_document_and_current_version() -> None:
    """A stale search reference never returns cached passage content."""
    retrieval = SyntheticRetrieval()
    bridge = _bridge(retrieval)
    reference = bridge.search(principal="clive", query="synthetic")[0].reference
    fetched = bridge.fetch(principal="clive", reference=reference)
    assert fetched.chunk_id == 31
    assert (fetched.page_start, fetched.page_end) == (2, 3)
    assert retrieval.calls == [
        ("clive", KnowledgeScope("PROJECT", "NHS_RECORDS")),
        ("clive", KnowledgeScope("PROJECT", "NHS_RECORDS")),
    ]

    retrieval.grants.remove("clive")
    with pytest.raises(ProjectRetrievalDenied):
        bridge.fetch(principal="clive", reference=reference)
    retrieval.grants.add("clive")
    retrieval.chunk = replace(retrieval.chunk, document_version_id=22)
    with pytest.raises(ProjectRetrievalDenied):
        bridge.fetch(principal="clive", reference=reference)
    retrieval.chunk = None
    with pytest.raises(ProjectRetrievalDenied):
        bridge.fetch(principal="clive", reference=reference)


def test_identity_scope_and_classification_isolation() -> None:
    """References cannot cross people or retrieve newly restricted content."""
    retrieval = SyntheticRetrieval()
    bridge = _bridge(retrieval)
    reference = bridge.search(principal="nicola", query="synthetic")[0].reference
    with pytest.raises(ProjectRetrievalDenied):
        bridge.fetch(principal="clive", reference=reference)
    retrieval.chunk = replace(retrieval.chunk, classification_tags=("PRIVATE",))
    with pytest.raises(ProjectRetrievalDenied):
        bridge.fetch(principal="nicola", reference=reference)
    assert bridge.search(principal="nicola", query="synthetic") == ()
    retrieval.chunk = replace(retrieval.chunk, scope=KnowledgeScope("PROJECT", "OTHER"))
    assert bridge.search(principal="nicola", query="synthetic") == ()


def test_each_person_is_attributed_to_core_retrieval() -> None:
    """The bridge passes each resolved principal to Core's audit path."""
    retrieval = SyntheticRetrieval()
    bridge = _bridge(retrieval)
    bridge.search(principal="nicola", query="synthetic")
    bridge.search(principal="clive", query="synthetic")
    assert retrieval.calls == [
        ("nicola", KnowledgeScope("PROJECT", "NHS_RECORDS")),
        ("clive", KnowledgeScope("PROJECT", "NHS_RECORDS")),
    ]


def test_bridge_bounds_and_personal_rate_limit() -> None:
    """Reject oversized queries and calls above the per-person budget."""
    retrieval = SyntheticRetrieval()
    bridge = _bridge(retrieval)
    with pytest.raises(ValueError):
        bridge.search(principal="clive", query="x" * 2049)
    for _ in range(30):
        bridge.search(principal="clive", query="synthetic")
    with pytest.raises(ProjectRetrievalDenied):
        bridge.search(principal="clive", query="synthetic")
    assert bridge.search(principal="nicola", query="synthetic")


def test_bridge_rejects_wildcards_and_hides_core_errors() -> None:
    """A misconfigured scope or failing Core call cannot widen or leak access."""
    retrieval = SyntheticRetrieval()
    with pytest.raises(ValueError):
        CoreProjectRetrievalBridge(
            project_code="*",
            allowed_classifications=frozenset({"RAW_REFERENCE"}),
            retrieval_service=retrieval,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        CoreProjectRetrievalBridge(
            project_code="NHS_RECORDS",
            allowed_classifications=frozenset({"*"}),
            retrieval_service=retrieval,  # type: ignore[arg-type]
        )

    def fail_retrieval(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("private database detail")

    retrieval.retrieve = fail_retrieval  # type: ignore[method-assign]
    with pytest.raises(
        ProjectRetrievalDenied, match="Evidence is unavailable"
    ) as error:
        _bridge(retrieval).search(principal="clive", query="synthetic")
    assert "private" not in str(error.value)


def test_page_references_require_valid_chunk_coordinates() -> None:
    """Only positive, ordered page coordinates become MCP source references."""
    assert CoreProjectRetrievalBridge._page_range('{"page_number": 4}') == (4, 4)
    assert CoreProjectRetrievalBridge._page_range(
        '{"page_start": 5, "page_end": 3}'
    ) == (
        None,
        None,
    )
    assert CoreProjectRetrievalBridge._page_range('{"page_number": "4"}') == (
        None,
        None,
    )


def test_local_tokens_map_to_distinct_principals() -> None:
    """Transport credentials establish people but grant no scope themselves."""
    auth = McpAuthenticator(
        local_tokens={"clive-secret": "clive", "nicola-secret": "nicola"}
    )
    assert auth.authenticate("Bearer clive-secret") == "clive"
    assert auth.authenticate("Bearer nicola-secret") == "nicola"
    with pytest.raises(McpAuthenticationError):
        auth.authenticate("Bearer unknown")


def test_external_tokens_require_valid_claims_and_subject_mapping() -> None:
    """External issuer identity never becomes an Orac grant by itself."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    auth = McpAuthenticator(
        issuer="https://identity.example.test/application/o/mcp/",
        audience="https://mcp.example.test/mcp",
        jwks_url="https://identity.example.test/jwks/",
        subject_bindings={"stable-clive-subject": "clive"},
    )
    auth._jwks = SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=key.public_key())
    )
    now = datetime.now(timezone.utc)
    claims = {
        "iss": auth.issuer,
        "aud": auth.audience,
        "sub": "stable-clive-subject",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    token = jwt.encode(claims, key, algorithm="RS256")
    assert auth.authenticate(f"Bearer {token}") == "clive"
    for changed in (
        {**claims, "sub": "unmapped-subject"},
        {**claims, "aud": "https://other.example.test"},
        {**claims, "exp": now - timedelta(seconds=1)},
    ):
        with pytest.raises(McpAuthenticationError):
            auth.authenticate(f"Bearer {jwt.encode(changed, key, algorithm='RS256')}")


@pytest.mark.anyio
async def test_mcp_protocol_lists_only_read_only_tools_and_requires_identity() -> None:
    """The SDK transport accepts authenticated MCP calls with synthetic data."""
    retrieval = SyntheticRetrieval()
    mcp = OracKnowledgeServerService._mcp(_bridge(retrieval))
    inner = mcp.streamable_http_app()
    app = _AuthenticatedMcpApp(
        inner,
        McpAuthenticator(local_tokens={"clive-secret": "clive"}),
    )
    async with inner.router.lifespan_context(inner):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
        ) as client:
            unauthorised = await client.post(
                "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            )
            assert unauthorised.status_code == 401
            headers = {
                "Authorization": "Bearer clive-secret",
                "Accept": "application/json, text/event-stream",
            }
            initialised = await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "synthetic-test", "version": "1"},
                    },
                },
            )
            assert initialised.status_code == 200
            listed = await client.post(
                "/mcp",
                headers=headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            assert listed.status_code == 200
            assert {tool["name"] for tool in listed.json()["result"]["tools"]} == {
                "search",
                "fetch",
            }
            for tool in listed.json()["result"]["tools"]:
                assert set(tool["inputSchema"]["properties"]) == {
                    "query" if tool["name"] == "search" else "reference"
                }
            searched = await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"query": "synthetic"}},
                },
            )
            assert searched.status_code == 200
            assert (
                searched.json()["result"]["structuredContent"]["results"][0][
                    "document_id"
                ]
                == 11
            )
            reference = searched.json()["result"]["structuredContent"]["results"][0][
                "reference"
            ]
            fetched = await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "fetch", "arguments": {"reference": reference}},
                },
            )
            assert fetched.status_code == 200
            assert fetched.json()["result"]["structuredContent"]["chunk_id"] == 31
