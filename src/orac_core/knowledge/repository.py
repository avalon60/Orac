"""Database repository for Core knowledge ingestion APIs."""

# Author: Clive Bostock
# Date: 07-Sep-2026
# Description: Calls ORAC_CODE knowledge APIs through an Orac-owned runtime database session.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import json
from typing import Any, Callable, TYPE_CHECKING
import uuid

import oracledb

from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.session_manager import DBSession
from lib.user_security import UserSecurity

if TYPE_CHECKING:
    from .model_submission import PrepareModelSubmissionRequest
    from .model_submission import PreparedModelSubmission

_RETRIEVAL_TEXT_FIELDS = frozenset(
    {
        "chunk_text",
        "classification_tags_json",
        "embedding_vector",
        "legacy_extracted_text",
    }
)


def default_orac_session() -> Any:
    """Open the saved Orac runtime database connection."""
    config_mgr = ConfigManager(
        config_file_path=project_home() / "resources" / "config" / "orac.ini"
    )
    project_identifier = config_mgr.config_value(
        "global", "project_identifier", default="Orac"
    )
    security = UserSecurity(project_identifier=project_identifier, resource_type="dsn")
    username, password, dsn = security.named_connection_creds(connection_name="orac")
    wallet = security.connection_property(
        connection_name="orac",
        property_key="wallet_zip_path",
        default_value="",
    )
    return DBSession(
        wallet_zip_path=wallet or "",
        verbose=False,
        user=username,
        password=password,
        dsn=dsn,
    )


class KnowledgeIngestionRepository:
    """Thin wrapper around ORAC_CODE knowledge ingestion package calls."""

    _PACKAGE = "orac_code.knowledge_ingestion_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise the repository with an optional session factory."""
        self._session_factory = session_factory or default_orac_session

    def submit_managed_file(
        self,
        *,
        source_type: str,
        source_reference: str,
        parent_source_reference: str | None,
        content_sha256: str,
        content_uri: str,
        mime_type: str,
        original_filename: str,
        byte_size: int,
        target_scope_type: str,
        target_scope_key: str,
        processing_profile_code: str | None,
        processing_instruction: str | None,
        source_modified_on: Any | None = None,
        legacy_parent_source_reference: str | None = None,
        source_format_code: str | None = None,
        normalised_markdown: str | None = None,
        normalised_text_sha256: str | None = None,
        normalised_byte_size: int | None = None,
        output_mime_type: str | None = None,
        extractor_code: str | None = None,
        extractor_version: str | None = None,
        extraction_metadata_json: str | None = None,
        classification_tags_json: str | None = None,
        output_set_json: str | None = None,
    ) -> int:
        """Register a captured managed file and return its ingestion request id."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                request_id = cursor.callfunc(
                    f"{self._PACKAGE}.submit_managed_file",
                    int,
                    [
                        source_type,
                        source_reference,
                        parent_source_reference,
                        content_sha256,
                        content_uri,
                        mime_type,
                        original_filename,
                        int(byte_size),
                        target_scope_type,
                        target_scope_key,
                        processing_profile_code,
                        processing_instruction,
                        source_modified_on,
                        legacy_parent_source_reference,
                        source_format_code,
                        normalised_markdown,
                        normalised_text_sha256,
                        normalised_byte_size,
                        output_mime_type,
                        extractor_code,
                        extractor_version,
                        extraction_metadata_json,
                        classification_tags_json,
                        output_set_json,
                    ],
                )
            session.commit()
            return int(request_id)
        finally:
            _close_quietly(session)

    def request_status(self, ingestion_request_id: int) -> str:
        """Return the current durable status for one ingestion request."""
        detail = self.request_detail(ingestion_request_id)
        return str(detail["status_code"])

    def try_claim_next_request(
        self, *, owner_id: str, lease_seconds: int
    ) -> int | None:
        """Claim the next available ingestion request, if any."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                request_id = cursor.callfunc(
                    f"{self._PACKAGE}.try_claim_next_request",
                    int,
                    [owner_id, lease_seconds],
                )
            session.commit()
            return int(request_id) if request_id is not None else None
        finally:
            _close_quietly(session)

    def requeue_failed_request(self, ingestion_request_id: int) -> None:
        """Requeue one failed request without changing its source lineage."""
        self.call_procedure(
            "requeue_failed_request",
            [int(ingestion_request_id)],
        )

    def request_detail(self, ingestion_request_id: int) -> dict[str, Any]:
        """Load request and source-object detail for worker processing."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.execute(
                    """
                    select req.ingestion_request_id,
                           req.status_code,
                           req.lease_owner,
                           req.lease_token,
                           req.source_object_id,
                           req.source_type,
                           req.source_reference,
                           req.parent_source_reference,
                           req.document_id,
                           req.document_version_id,
                           req.content_uri,
                           req.content_sha256,
                           req.mime_type,
                           req.original_filename,
                           req.byte_size,
                           req.source_modified_on
                           , ext.extraction_id
                           , ext.extracted_text
                           , req.artefact_count
                      from orac_code.knowledge_ingestion_requests_v req
                      left join orac_api.knowledge_extractions_v ext
                        on ext.document_version_id = req.document_version_id
                     where req.ingestion_request_id = :request_id
                    """,
                    {"request_id": ingestion_request_id},
                )
                row = cursor.fetchone()
                if row is None:
                    raise LookupError(
                        f"Knowledge request not found: {ingestion_request_id}"
                    )
                columns = [description[0].lower() for description in cursor.description]
                detail = dict(zip(columns, row, strict=True))
                detail["extracted_text"] = _optional_oracle_text(
                    detail.get("extracted_text"),
                    field_name="extracted_text",
                )
                return detail
        finally:
            _close_quietly(session)

    def mark_stage(
        self,
        *,
        ingestion_request_id: int,
        owner_id: str,
        lease_token: str,
        status: str,
        stage: str,
    ) -> None:
        """Persist a durable request stage transition."""
        self.call_procedure(
            "mark_stage",
            [ingestion_request_id, owner_id, lease_token, status, stage],
        )

    def ensure_document_version(
        self,
        *,
        ingestion_request_id: int,
        title: str | None,
        source_modified_on: Any | None,
    ) -> int:
        """Create or reuse the document version for a request."""
        return int(
            self.call_function(
                "ensure_document_version",
                int,
                [ingestion_request_id, title, source_modified_on],
            )
        )

    def create_extraction(
        self,
        *,
        document_version_id: int,
        extractor_code: str,
        extractor_version: str,
        extracted_text: str,
        text_sha256: str,
    ) -> int:
        """Create or reuse an extraction row."""
        return int(
            self.call_function(
                "create_extraction",
                int,
                [
                    document_version_id,
                    extractor_code,
                    extractor_version,
                    extracted_text,
                    text_sha256,
                ],
            )
        )

    def create_chunk_set(
        self,
        *,
        extraction_id: int,
        chunker_code: str,
        chunker_version: str,
        chunk_size_tokens: int,
        overlap_tokens: int,
        source_artefact_id: int | None = None,
    ) -> int:
        """Create or reuse a chunk-set row."""
        return int(
            self.call_function(
                "create_chunk_set",
                int,
                [
                    extraction_id,
                    chunker_code,
                    chunker_version,
                    chunk_size_tokens,
                    overlap_tokens,
                    source_artefact_id,
                ],
            )
        )

    def output_set(self, extraction_id: int) -> dict[str, Any]:
        """Load one complete managed artefact descriptor set."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                payload = cursor.callfunc(
                    "orac_code.knowledge_ingestion_api.worker_output_set_json",
                    str,
                    [extraction_id],
                )
            text_payload = _optional_oracle_text(
                payload,
                field_name="output_set_json",
            )
            if text_payload is None:
                raise LookupError(f"Knowledge output set not found: {extraction_id}")
            result = json.loads(text_payload)
            if not isinstance(result, dict):
                raise TypeError("Knowledge output-set JSON must be an object.")
            return result
        finally:
            _close_quietly(session)

    def insert_chunk(
        self,
        *,
        chunk_set_id: int,
        chunk_no: int,
        span_start: int,
        span_end: int,
        chunk_text: str,
        token_count: int,
        content_sha256: str,
        metadata_json: str | None = None,
    ) -> int:
        """Insert or reuse one chunk row."""
        return int(
            self.call_function(
                "insert_chunk",
                int,
                [
                    chunk_set_id,
                    chunk_no,
                    span_start,
                    span_end,
                    chunk_text,
                    token_count,
                    content_sha256,
                    metadata_json,
                ],
            )
        )

    def upsert_embedding_model(
        self,
        *,
        provider_code: str,
        model_name: str,
        model_revision: str,
        dimensions: int,
        distance_metric: str = "COSINE",
        normalisation: str = "UNIT",
    ) -> int:
        """Create or reuse an embedding-model registry row."""
        return int(
            self.call_function(
                "upsert_embedding_model",
                int,
                [
                    provider_code,
                    model_name,
                    model_revision,
                    dimensions,
                    distance_metric,
                    normalisation,
                ],
            )
        )

    def call_function(self, name: str, return_type: Any, parameters: list[Any]) -> Any:
        """Call a knowledge ingestion package function and commit."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                result = cursor.callfunc(
                    f"{self._PACKAGE}.{name}", return_type, parameters
                )
            session.commit()
            return result
        finally:
            _close_quietly(session)

    def call_procedure(self, name: str, parameters: list[Any]) -> None:
        """Call a knowledge ingestion package procedure and commit."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(f"{self._PACKAGE}.{name}", parameters)
            session.commit()
        finally:
            _close_quietly(session)

    def complete_request(
        self,
        *,
        ingestion_request_id: int,
        owner_id: str,
        lease_token: str,
        embedding_profile_id: int,
    ) -> None:
        """Mark a leased request complete."""
        self.call_procedure(
            "complete_request",
            [
                ingestion_request_id,
                owner_id,
                lease_token,
                embedding_profile_id,
            ],
        )

    def fail_request(
        self,
        *,
        ingestion_request_id: int,
        owner_id: str,
        lease_token: str,
        error_code: str,
        error_message: str,
        retryable: bool = True,
    ) -> None:
        """Mark a leased request failed or dead-lettered."""
        self.call_procedure(
            "fail_request",
            [
                ingestion_request_id,
                owner_id,
                lease_token,
                error_code,
                error_message,
                "Y" if retryable else "N",
            ],
        )


class KnowledgeEmbeddingRepository:
    """Persist and activate native knowledge embeddings through ORAC_CODE."""

    _PACKAGE = "orac_code.knowledge_embedding_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise native embedding access with an injectable session."""
        self._session_factory = session_factory or default_orac_session

    def ensure_profile(self, profile: Any) -> int:
        """Register one immutable semantic profile and return its identity."""
        return int(
            self._call_function(
                "ensure_profile",
                int,
                [
                    profile.profile_version,
                    profile.provider_code,
                    profile.model_id,
                    profile.model_digest,
                    profile.document_input_prefix,
                    profile.query_input_prefix,
                    profile.retrieval_policy_version,
                    profile.semantic_threshold,
                ],
            )
        )

    def active_profile(self) -> dict[str, Any] | None:
        """Return the currently active production knowledge profile."""
        raw = self._call_function("active_profile_json", oracledb.DB_TYPE_CLOB, [])
        text = _optional_oracle_text(raw, field_name="active_profile_json")
        if text is None:
            return None
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise TypeError("Active knowledge profile must be a JSON object.")
        return parsed

    def begin_run(self, embedding_profile_id: int) -> int:
        """Create one resumable native re-embedding run."""
        return int(
            self._call_function(
                "begin_reembedding_run",
                int,
                [int(embedding_profile_id)],
            )
        )

    def open_run_chunks(
        self,
        *,
        reembedding_run_id: int,
        chunk_limit: int,
    ) -> list[dict[str, Any]]:
        """Load a bounded batch of normalized chunks missing native vectors."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                result_cursor = session.cursor()
                try:
                    cursor.callproc(
                        f"{self._PACKAGE}.open_reembedding_chunks",
                        [int(reembedding_run_id), int(chunk_limit), result_cursor],
                    )
                    columns = [item[0].lower() for item in result_cursor.description]
                    rows = []
                    for row in result_cursor.fetchall():
                        materialized = {
                            column: (
                                _optional_oracle_text(value, field_name=column)
                                if column == "chunk_text"
                                else _materialize_query_value(value)
                            )
                            for column, value in zip(columns, row, strict=True)
                        }
                        rows.append(materialized)
                    return rows
                finally:
                    result_cursor.close()
        finally:
            _close_quietly(session)

    def store_native_embedding(
        self,
        *,
        embedding_profile_id: int,
        chunk_id: int,
        embedding_text_sha256: str,
        vector: list[float],
        reembedding_run_id: int | None = None,
    ) -> int:
        """Store one vector natively; JSON is transient package input only."""
        return int(
            self._call_function(
                "store_native_embedding",
                int,
                [
                    int(embedding_profile_id),
                    int(chunk_id),
                    embedding_text_sha256,
                    json.dumps(vector, separators=(",", ":"), allow_nan=False),
                    reembedding_run_id,
                ],
            )
        )

    def validate_run(self, reembedding_run_id: int) -> None:
        """Validate native coverage without promoting the profile."""
        self._call_procedure(
            "validate_reembedding_run",
            [int(reembedding_run_id)],
        )

    def activate_run(self, reembedding_run_id: int) -> None:
        """Atomically activate a validated native embedding run."""
        self._call_procedure(
            "activate_reembedding_run",
            [int(reembedding_run_id)],
        )

    def activate_profile(self, embedding_profile_id: int) -> None:
        """Atomically return to a previously validated, still-current profile."""
        self._call_procedure(
            "activate_profile",
            [int(embedding_profile_id)],
        )

    def run_status(self, reembedding_run_id: int) -> dict[str, Any]:
        """Return safe progress counters for one re-embedding run."""
        raw = self._call_function(
            "reembedding_run_status_json",
            oracledb.DB_TYPE_CLOB,
            [int(reembedding_run_id)],
        )
        text = _optional_oracle_text(raw, field_name="reembedding_run_status_json")
        parsed = json.loads(text or "{}")
        if not isinstance(parsed, dict):
            raise TypeError("Re-embedding status must be a JSON object.")
        return parsed

    def _call_function(
        self,
        name: str,
        return_type: Any,
        parameters: list[Any],
    ) -> Any:
        """Call a lifecycle function and commit its transaction."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                result = cursor.callfunc(
                    f"{self._PACKAGE}.{name}",
                    return_type,
                    parameters,
                )
                materialized = _materialize_query_value(result)
            session.commit()
            return materialized
        finally:
            _close_quietly(session)

    def _call_procedure(self, name: str, parameters: list[Any]) -> None:
        """Call a lifecycle procedure and commit its transaction."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(f"{self._PACKAGE}.{name}", parameters)
            session.commit()
        finally:
            _close_quietly(session)


def _optional_oracle_text(value: Any, *, field_name: str) -> str | None:
    """Materialise and validate one optional Oracle text projection.

    Args:
        value: Plain text, null, or a connection-bound Oracle LOB.
        field_name: Projection name used in validation errors.

    Returns:
        The materialised Python string, or ``None`` for a database null.

    Raises:
        TypeError: If the value or its LOB payload is not text.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    read_value = getattr(value, "read", None)
    if not callable(read_value):
        raise TypeError(f"Core knowledge {field_name} must be text or an Oracle LOB.")
    payload = read_value()
    if not isinstance(payload, str):
        raise TypeError(
            f"Core knowledge {field_name} Oracle LOB must contain text."
        )
    return payload


def _materialize_query_value(value: Any) -> Any:
    """Read a connection-bound value while preserving native Oracle JSON."""
    read_value = getattr(value, "read", None)
    return read_value() if callable(read_value) else value


def _close_quietly(session: Any) -> None:
    """Close a database session without masking the primary error."""
    try:
        session.close()
    except Exception:
        pass


class KnowledgeRetrievalRepository:
    """Call the single authorised retrieval boundary as the Core runtime."""

    _PACKAGE = "orac_code.knowledge_retrieval_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise authorised retrieval access with an injectable session."""
        self._session_factory = session_factory or default_orac_session

    def open_hybrid_search_candidates(
        self,
        *,
        principal_username: str,
        target_scope_type: str,
        target_scope_key: str,
        embedding_profile_id: int,
        query_vector: list[float],
        lexical_tokens: list[str],
        lexical_phrase: str,
        semantic_limit: int = 50,
        lexical_limit: int = 50,
        retrieval_id: str | None = None,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        """Return the bounded Oracle semantic/lexical candidate union."""
        return self._call_with_cursor(
            "open_hybrid_search_candidates",
            [
                retrieval_id or str(uuid.uuid4()),
                principal_username,
                target_scope_type,
                target_scope_key,
                int(embedding_profile_id),
                json.dumps(query_vector, separators=(",", ":"), allow_nan=False),
                json.dumps(lexical_tokens, separators=(",", ":")),
                lexical_phrase,
                int(semantic_limit),
                int(lexical_limit),
            ],
        )

    def open_plugin_hybrid_candidates(
        self,
        *,
        principal_username: str,
        plugin_id: str,
        embedding_profile_id: int,
        query_vector: list[float],
        lexical_tokens: list[str],
        lexical_phrase: str,
        semantic_limit: int = 50,
        lexical_limit: int = 50,
        retrieval_id: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        """Return plugin-scoped native hybrid candidates through the host bridge."""
        return self._call_with_cursor(
            "open_plugin_hybrid_candidates",
            [
                retrieval_id or str(uuid.uuid4()),
                principal_username,
                plugin_id,
                int(embedding_profile_id),
                json.dumps(query_vector, separators=(",", ":"), allow_nan=False),
                json.dumps(lexical_tokens, separators=(",", ":")),
                lexical_phrase,
                int(semantic_limit),
                int(lexical_limit),
                correlation_id,
            ],
        )

    def resolve_request(
        self,
        *,
        retrieval_id: str,
        principal_username: str,
        target_scope_type: str,
        target_scope_key: str,
        request_json: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Authorise and resolve controlled identities to internal descriptors."""
        _, resolution, rows = self._call_with_cursor(
            "resolve_request",
            [
                retrieval_id,
                principal_username,
                target_scope_type,
                target_scope_key,
                request_json,
            ],
        )
        return resolution, rows

    def record_policy_decision(
        self,
        *,
        policy_request_id: str,
        principal_username: str,
        target_scope_type: str,
        target_scope_key: str,
        target_type: str,
        target_id: int,
        decision_code: str,
        reason_code: str,
        purpose_code: str,
        requested_level_code: str,
        effective_level_code: str | None,
        policy_version: str,
        estimator_code: str | None,
        estimated_byte_size: int | None,
        estimated_token_count: int | None,
        usable_context_tokens: int | None,
        member_count: int | None,
        chunk_count: int | None,
        complete: bool,
        selected: bool,
        downgraded: bool,
        truncated: bool,
    ) -> None:
        """Record allowlisted P1-07 decision dimensions without content."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(
                    f"{self._PACKAGE}.record_policy_decision",
                    [
                        policy_request_id,
                        principal_username,
                        target_scope_type,
                        target_scope_key,
                        target_type,
                        int(target_id),
                        decision_code,
                        reason_code,
                        purpose_code,
                        requested_level_code,
                        effective_level_code,
                        policy_version,
                        estimator_code,
                        estimated_byte_size,
                        estimated_token_count,
                        usable_context_tokens,
                        member_count,
                        chunk_count,
                        "Y" if complete else "N",
                        "Y" if selected else "N",
                        "Y" if downgraded else "N",
                        "Y" if truncated else "N",
                    ],
                )
        finally:
            _close_quietly(session)

    def record_outcome(
        self,
        *,
        retrieval_id: str,
        outcome_code: str,
        reason_code: str,
        returned_byte_size: int | None = None,
        returned_sha256: str | None = None,
        member_count: int | None = None,
        chunk_count: int | None = None,
        duration_ms: int | None = None,
        selected_chunk_ids: tuple[int, ...] | list[int] | None = None,
    ) -> None:
        """Append a bounded terminal retrieval outcome."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(
                    f"{self._PACKAGE}.record_outcome",
                    [
                        retrieval_id,
                        outcome_code,
                        reason_code,
                        returned_byte_size,
                        returned_sha256,
                        member_count,
                        chunk_count,
                        duration_ms,
                        (
                            json.dumps(
                                [int(chunk_id) for chunk_id in selected_chunk_ids],
                                separators=(",", ":"),
                            )
                            if selected_chunk_ids is not None
                            else None
                        ),
                    ],
                )
        finally:
            _close_quietly(session)

    def record_model_submission_decision(
        self,
        *,
        request: "PrepareModelSubmissionRequest",
        prepared: "PreparedModelSubmission",
        reason_code: str,
    ) -> None:
        """Record allowlisted P1-08 submission dimensions without prompt content."""
        approval = request.approval
        envelope = request.envelope
        model = request.model
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(
                    f"{self._PACKAGE}.record_model_submission_decision",
                    [
                        request.submission_id,
                        approval.policy_request_id,
                        approval.principal_username,
                        approval.scope.scope_type,
                        approval.scope.scope_key,
                        approval.target_type,
                        approval.target_id,
                        model.llm_id,
                        model.row_version,
                        model.provider_code,
                        model.context_policy_code,
                        envelope.version,
                        envelope.effective_level,
                        envelope.part_count,
                        envelope.member_count or None,
                        envelope.chunk_count or None,
                        envelope.source_byte_size,
                        envelope.byte_size,
                        prepared.evidence_safe_tokens,
                        prepared.occupied_safe_tokens,
                        prepared.final_prompt_safe_tokens,
                        request.reserved_output_tokens,
                        prepared.context_safety_tokens,
                        "Y" if envelope.complete else "N",
                        "Y" if envelope.selected else "N",
                        "Y" if envelope.downgraded else "N",
                        "Y" if envelope.non_truncated else "N",
                        0,
                        reason_code,
                    ],
                )
        finally:
            _close_quietly(session)

    def _call_with_cursor(
        self,
        procedure_name: str,
        inputs: list[Any],
        *,
        row_defaults: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        """Materialise package CLOB/cursor outputs before closing the session."""
        session = self._session_factory()
        retrieval_id = str(inputs[0])
        try:
            with session.cursor() as cursor:
                resolution_var = cursor.var(oracledb.DB_TYPE_CLOB)
                result_cursor = session.cursor()
                try:
                    cursor.callproc(
                        f"{self._PACKAGE}.{procedure_name}",
                        [*inputs, resolution_var, result_cursor],
                    )
                    resolution_text = _optional_oracle_text(
                        resolution_var.getvalue(), field_name="resolution_json"
                    )
                    columns = [item[0].lower() for item in result_cursor.description]
                    rows = [
                        {
                            column: (
                                _optional_oracle_text(value, field_name=column)
                                if column in _RETRIEVAL_TEXT_FIELDS
                                else _materialize_query_value(value)
                            )
                            for column, value in zip(columns, row, strict=True)
                        }
                        for row in result_cursor.fetchall()
                    ]
                    for row in rows:
                        for column, value in (row_defaults or {}).items():
                            row.setdefault(column, value)
                finally:
                    result_cursor.close()
            if resolution_text is None:
                raise RuntimeError("Authorised retrieval returned no resolution.")
            resolution = json.loads(resolution_text)
            if not isinstance(resolution, dict):
                raise TypeError("Retrieval resolution JSON must be an object.")
            return retrieval_id, resolution, rows
        finally:
            _close_quietly(session)
