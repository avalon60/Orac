"""Database repository for Core knowledge ingestion APIs."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Calls ORAC_CODE knowledge APIs through an Orac-owned runtime database session.

from __future__ import annotations

import json
from typing import Any, Callable

from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.session_manager import DBSession
from lib.user_security import UserSecurity


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
                      from orac_code.knowledge_ingestion_requests_v req
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
                return dict(zip(columns, row, strict=True))
        finally:
            _close_quietly(session)

    def load_searchable_chunks(
        self,
        *,
        target_scope_type: str,
        target_scope_key: str,
        embedding_model_identifier: str,
        embedding_dimensions: int,
        candidate_limit: int,
    ) -> list[dict[str, Any]]:
        """Load searchable chunks visible to a retrieval scope."""
        if candidate_limit <= 0:
            raise ValueError("candidate_limit must be positive")
        session = self._session_factory()
        try:
            parameters: dict[str, Any] = {
                "embedding_model_identifier": embedding_model_identifier,
                "embedding_dimensions": int(embedding_dimensions),
                "target_scope_type": target_scope_type,
                "target_scope_key": target_scope_key,
                "candidate_fetch_limit": int(candidate_limit) + 1,
            }

            with session.cursor() as cursor:
                cursor.execute(
                    """
                    select *
                      from (
                        select chunk.ingestion_request_id,
                               chunk.source_object_id,
                               chunk.source_type,
                               chunk.source_reference,
                               chunk.parent_source_reference,
                               chunk.document_id,
                               chunk.title document_title,
                               chunk.document_version_id,
                               chunk.original_filename,
                               chunk.content_uri,
                               chunk.target_scope_type,
                               chunk.target_scope_key,
                               chunk.chunk_id,
                               chunk.chunk_no,
                               chunk.span_start,
                               chunk.span_end,
                               chunk.chunk_content_sha256,
                               chunk.chunk_text,
                               chunk.embedding_vector,
                               chunk.provider_code embedding_provider_code,
                               chunk.embedding_model_identifier,
                               chunk.model_revision embedding_model_revision,
                               chunk.embedding_dimensions,
                               request.processing_profile_code
                          from orac_code.knowledge_searchable_chunks_v chunk
                          join orac_code.knowledge_ingestion_requests_v request
                            on request.ingestion_request_id = chunk.ingestion_request_id
                         where chunk.embedding_model_identifier = :embedding_model_identifier
                           and chunk.embedding_dimensions = :embedding_dimensions
                           and chunk.target_scope_type = :target_scope_type
                           and chunk.target_scope_key = :target_scope_key
                         order by chunk.document_id,
                                  chunk.document_version_id,
                                  chunk.chunk_no
                      )
                     where rownum <= :candidate_fetch_limit
                    """,
                    parameters,
                )
                columns = [description[0].lower() for description in cursor.description]
                return [
                    {
                        column: _materialize_query_value(value)
                        for column, value in zip(columns, row, strict=True)
                    }
                    for row in cursor.fetchall()
                ]
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
                ],
            )
        )

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

    def insert_embedding(
        self,
        *,
        chunk_id: int,
        embedding_model_id: int,
        vector: list[float],
        embedding_text_sha256: str,
    ) -> int:
        """Persist one chunk embedding through the package API."""
        return int(
            self.call_function(
                "insert_chunk_embedding",
                int,
                [
                    chunk_id,
                    embedding_model_id,
                    json.dumps(vector, separators=(",", ":")),
                    embedding_text_sha256,
                ],
            )
        )

    def complete_request(
        self,
        *,
        ingestion_request_id: int,
        owner_id: str,
        lease_token: str,
    ) -> None:
        """Mark a leased request complete."""
        self.call_procedure(
            "complete_request",
            [ingestion_request_id, owner_id, lease_token],
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


def _materialize_query_value(value: Any) -> Any:
    """Read connection-bound Oracle values before their session is closed."""
    read_value = getattr(value, "read", None)
    return read_value() if callable(read_value) else value


def _close_quietly(session: Any) -> None:
    """Close a database session without masking the primary error."""
    try:
        session.close()
    except Exception:
        pass
