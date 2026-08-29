"""Static contract tests for conversation-memory Oracle deployment assets."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Verifies schema reachability, authority, lineage, and runtime grants.

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ConversationMemorySchemaTests(unittest.TestCase):
    """Check the minimal connected database control chain."""

    def test_three_conversation_specific_tables_are_declared(self) -> None:
        """The Phase 1 schema does not introduce a generic retrieval store."""
        table_dir = ROOT / "resources/db/schema/orac_core/table"
        expected = {
            "conversation_memory_requests.sql",
            "conversation_summary_checkpoints.sql",
            "conversation_summary_sources.sql",
        }
        self.assertTrue(expected.issubset({path.name for path in table_dir.iterdir()}))

    def test_runtime_receives_only_business_package_execute(self) -> None:
        """The runtime has no direct grant to conversational-memory tables."""
        schema_root = ROOT / "resources/db/schema"
        all_sql = "\n".join(
            path.read_text(encoding="utf-8")
            for path in schema_root.rglob("*.sql")
        ).lower()
        self.assertIn(
            "grant execute on orac_code.conversation_memory_api to orac",
            all_sql,
        )
        self.assertNotIn(
            "on orac_core.conversation_memory_requests to orac;",
            all_sql,
        )
        self.assertNotIn(
            "on orac_core.conversation_summary_checkpoints to orac;",
            all_sql,
        )

    def test_database_api_joins_principal_to_conversation_ownership(self) -> None:
        """Both retrieval stages enforce the authoritative conversation owner."""
        body = (
            ROOT
            / "resources/db/schema/orac_code/package_body/conversation_memory_api.sql"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("conversation.user_id = l_user_id", body)
        self.assertIn("source.message_row_version", body)
        self.assertIn("source.source_content_sha256", body)

    def test_checkpoint_update_is_rejected(self) -> None:
        """Completed checkpoint rows are immutable at the data boundary."""
        trigger = (
            ROOT
            / "resources/db/schema/orac_core/trigger/conv_sumchk_immutable.sql"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("before update", trigger)
        self.assertIn("raise_application_error", trigger)

    def test_source_embeddings_can_coexist_across_model_profiles(self) -> None:
        """An immutable source may be re-materialised with a governed profile."""
        migration = (
            ROOT
            / "resources/db/schema/orac_core/migration/"
            "conversation_message_embedding_profiles.sql"
        ).read_text(encoding="utf-8").lower()
        package_body = (
            ROOT
            / "resources/db/schema/orac_code/package_body/conversation_memory_api.sql"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("message_id,\n    chunk_index,\n    embedding_model", migration)
        self.assertIn("and embedding_model = l_embedding_model", package_body)
        self.assertIn(
            '<includeall path="migration"',
            (
                ROOT / "resources/db/schema/orac_core/schemaController.xml"
            ).read_text(encoding="utf-8").lower(),
        )


if __name__ == "__main__":
    unittest.main()
