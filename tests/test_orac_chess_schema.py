"""Verify the Orac Chess storage and controlled administration source contract."""

# Author: Clive Bostock
# Date: 2026-10-25
# Description: Checks Chess manifest isolation and deployable schema metadata.
# Purpose: Protect the plugin storage, migration and consumer privilege contract.
# Usage: PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_orac_chess_schema

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_database_deployment import expected_deployment_objects  # noqa: E402
from model.plugin_database_deployment import (  # noqa: E402
    validate_plugin_liquibase_changelog,
)
from model.plugin_database_deployment import validate_schema_payload  # noqa: E402
from model.plugin_package import PluginPackageBuilder  # noqa: E402
from model.plugin_routing.discovery import (  # noqa: E402
    PluginDiscovery,
    PluginManifestError,
)


class OracChessSchemaTests(unittest.TestCase):
    """Protect the plugin's database-only deployment boundary."""

    MANIFEST = PROJECT_ROOT / "plugins" / "orac_chess.json"
    PLUGIN_DIR = PROJECT_ROOT / "plugins" / "orac_chess"
    SCHEMA = PLUGIN_DIR / "db" / "schema"

    def test_manifest_has_no_executable_surface(self) -> None:
        """A database-only plugin has no runtime entry point or route."""
        manifest = PluginDiscovery(self.MANIFEST.parent).load_manifest(self.MANIFEST)
        self.assertEqual(manifest.plugin_id, "orac_chess")
        self.assertEqual(manifest.capabilities, ())
        self.assertEqual(manifest.route_capabilities, ())
        self.assertIsNone(manifest.entry_point)
        self.assertEqual(manifest.service_runtimes, ())
        self.assertEqual(manifest.database_schemas[0].schema_name, "orac_chess")
        self.assertEqual(manifest.database_deployment.deployment_type, "liquibase")
        self.assertEqual(manifest.database_schemas[0].bridge_api_dependencies, ())

    def test_empty_capabilities_still_fail_for_non_database_plugin(self) -> None:
        """The manifest exception cannot silently enable ordinary empty plugins."""
        data = json.loads(self.MANIFEST.read_text())
        data["database"]["required"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orac_chess.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(PluginManifestError, "capabilities"):
                PluginDiscovery(path.parent).load_manifest(
                    path, plugin_dir=self.PLUGIN_DIR
                )

    def test_controller_reaches_only_plugin_owned_assets(self) -> None:
        """Every Chess source changeset is reachable and has rollback text."""
        manifest = PluginDiscovery(self.MANIFEST.parent).load_manifest(self.MANIFEST)
        referenced = validate_plugin_liquibase_changelog(manifest)
        source = set(self.SCHEMA.rglob("*.sql"))
        self.assertEqual(set(referenced), source)
        self.assertEqual(len(list((self.SCHEMA / "table").glob("*.sql"))), 25)
        self.assertEqual(len(list((self.SCHEMA / "constraint_fk").glob("*.sql"))), 38)
        self.assertEqual(len(list((self.SCHEMA / "constraint_pk").glob("*.sql"))), 25)
        self.assertEqual(len(list((self.SCHEMA / "index").glob("*.sql"))), 54)
        change_ids: list[str] = []
        for path in source:
            content = path.read_text()
            self.assertTrue(content.startswith("--liquibase formatted sql"), path)
            self.assertIn("--rollback ", content, path)
            self.assertNotRegex(content, r"(?i)\bpublic\s+synonym\b")
            if path.parent.name == "grant":
                self.assertNotRegex(content, r"(?i)\b(?:insert|update|delete|all)\b")
                self.assertNotRegex(content, r"(?i)\bto\s+public\b")
            change_ids.extend(re.findall(r"^--changeset\s+(\S+)", content, re.M))
            if path.parent.name not in {"comment", "view", "package_spec", "package_body", "grant", "post_install", "annotation", "mle_module", "mle_env", "function"}:
                self.assertNotIn("runOnChange:true", content, path)
        self.assertEqual(len(change_ids), len(set(change_ids)))
        validate_schema_payload(self.SCHEMA, manifest=manifest)

    def test_content_sources_use_creator_identity_and_preserve_video_contract(self) -> None:
        """Source migration keeps names, permits many videos and adds no surrogate key."""
        table = (self.SCHEMA / "table/chess_content_source.sql").read_text().lower()
        self.assertIn("creator varchar2(300 char) not null", table)
        self.assertIn("author varchar2(300 char)", table)
        self.assertIn("notes clob", table)
        self.assertNotIn("identity", table)
        pk = (self.SCHEMA / "constraint_pk/chs_csr_pk.sql").read_text().lower()
        self.assertIn("primary key (creator) using index", pk)
        fk = (self.SCHEMA / "constraint_fk/chs_vid_creator_fk.sql").read_text().lower()
        self.assertIn("foreign key (creator) references orac_chess.chess_content_source (creator)", fk)
        self.assertNotIn("cascade", fk)
        index = (self.SCHEMA / "index/chs_vid_creator_ix.sql").read_text().lower()
        self.assertIn("create index", index)
        self.assertNotIn("create unique index", index)
        spec = (self.SCHEMA / "package_spec/chess_admin_api.sql").read_text()
        self.assertIn("p_creator in varchar2", spec)
        self.assertIn("p_original_creator in varchar2", spec)

    def test_content_source_migration_preserves_user_edits_and_existing_names(self) -> None:
        """Insert-only source seeds and backfill precede the restrictive video FK."""
        seed = (self.SCHEMA / "seed_data/chess_content_source.sql").read_text()
        for creator, author, notes in (
            ("ChessVibes", "Nelson Lopez", "NM"),
            ("Square One Chess", "squareonechess6939", "Pundit"),
            ("Remote Chess Academy", "Igor Smirnov", "GM"),
            ("ChesswithAkeem", "Akeem Brown", "CM"),
            ("ChessCenturion", "Alex", "~2000"),
        ):
            self.assertIn(f"'{creator}' creator, '{author}' author, '{notes}' notes", seed)
        self.assertIn("when not matched then insert", seed.lower())
        self.assertNotIn("when matched", seed.lower())
        self.assertNotIn("delete from", seed.lower())
        backfill = (self.SCHEMA / "seed_data/chess_content_source_existing.sql").read_text().lower()
        self.assertIn("select distinct creator from orac_chess.chess_video", backfill)
        self.assertNotIn("trim(", backfill)
        self.assertNotIn("update", backfill)
        controller = (self.PLUGIN_DIR / "db/liquibase/controllers/08_content_source.xml").read_text()
        self.assertLess(controller.index("chess_content_source_existing.sql"), controller.index("chs_vid_creator_fk.sql"))
        root = (self.PLUGIN_DIR / "db/liquibase/pluginController.xml").read_text()
        self.assertLess(root.index("08_content_source.xml"), root.index("09_admin_views.xml"))
        self.assertLess(root.index("08_content_source.xml"), root.index("10_admin_api.xml"))

    def test_seed_repeat_acceptance_uses_production_seed_and_restores_edits(self) -> None:
        """The rollback proof executes the real seed rather than a copied MERGE."""
        acceptance = (self.PLUGIN_DIR / "db/acceptance/verify_content_source_seed_repeat.sql").read_text()
        self.assertIn("@@../schema/seed_data/chess_content_source.sql", acceptance)
        self.assertIn("rollback to content_source_seed_acceptance", acceptance.lower())
        self.assertIn("row_version=:source_seed_version", acceptance)
        self.assertIn("dbms_lob.compare", acceptance)
        self.assertNotRegex(acceptance, r"(?im)^\s*commit\s*;")

    def test_relational_contract_is_explicit(self) -> None:
        """The important subject and branching rules live in Oracle DDL."""
        variation = (self.SCHEMA / "table" / "chess_variation.sql").read_text()
        game = (self.SCHEMA / "table" / "chess_game.sql").read_text()
        image = (self.SCHEMA / "table" / "chess_image.sql").read_text()
        self.assertRegex(variation, r"(?i)\bpgn\s+clob not null")
        self.assertRegex(game, r"(?i)\bpgn\s+clob not null")
        self.assertRegex(image, r"(?i)\bimage_content\s+blob not null")
        self.assertRegex(variation, r"(?i)\bstarting_fen\s+varchar2")
        self.assertIn(
            "opening_id is not null and gambit_id is null",
            (self.SCHEMA / "constraint_other" / "chs_var_subject_ck.sql").read_text(),
        )
        for subject in ("opn", "gmb"):
            self.assertIn(
                "foreign key (parent_variation_id,",
                (
                    self.SCHEMA / "constraint_fk" / f"chs_var_parent_{subject}_fk.sql"
                ).read_text(),
            )
        for link in (
            "chess_opening_gambit",
            "chess_video_opening",
            "chess_video_gambit",
            "chess_video_variation",
            "chess_concept_opening",
            "chess_concept_gambit",
            "chess_concept_variation",
            "chess_image_opening",
            "chess_image_gambit",
            "chess_image_variation",
        ):
            self.assertTrue((self.SCHEMA / "table" / f"{link}.sql").exists())
        self.assertFalse(
            any(
                re.search(
                    r"(?i)\b(drop user|create user|grant .* to public)\b", p.read_text()
                )
                for p in self.SCHEMA.rglob("*.sql")
            )
        )

    def test_fresh_baseline_ownership_and_eco_contract(self) -> None:
        """The baseline replaces over-restrictive keys and normalises opening ECO."""
        variation = (self.SCHEMA / "table/chess_variation.sql").read_text()
        self.assertRegex(
            variation,
            r"(?s)variation_type\s+generated always as.*cast\(case.*"
            r"opening_id is not null then 'O'.*gambit_id is not null then 'G'.*"
            r"as varchar2\(1 char\)\)\) virtual",
        )
        key = (self.SCHEMA / "constraint_uc/chs_var_subject_name_uk.sql").read_text()
        self.assertIn("unique (variation_type, opening_id, gambit_id, name)", key)
        self.assertIn("using index orac_chess.chs_var_subject_name_ux", key)
        for obsolete in (
            "chs_var_opn_name_uk",
            "chs_var_gmb_name_uk",
            "chs_var_opn_name_ux",
            "chs_var_gmb_name_ux",
            "chs_opn_eco_ck",
            "chs_opn_eco_ix",
        ):
            self.assertFalse(list(self.SCHEMA.rglob(f"{obsolete}.sql")))
            for sql in self.SCHEMA.rglob("*.sql"):
                self.assertNotIn(obsolete, sql.read_text(), sql)
        opening = (self.SCHEMA / "table/chess_opening.sql").read_text()
        self.assertNotIn("eco_code", opening)
        eco = (self.SCHEMA / "table/chess_opening_eco.sql").read_text()
        self.assertRegex(eco, r"eco_code\s+varchar2\(3 char\) not null")
        self.assertIn(
            "primary key (opening_id, eco_code)",
            (self.SCHEMA / "constraint_pk/chs_oec_pk.sql").read_text(),
        )
        self.assertIn(
            "references orac_chess.chess_opening (opening_id)",
            (self.SCHEMA / "constraint_fk/chs_oec_opening_fk.sql").read_text(),
        )
        self.assertIn(
            "regexp_like(eco_code, '^[A-E][0-9]{2}$')",
            (self.SCHEMA / "constraint_other/chs_oec_eco_ck.sql").read_text(),
        )
        self.assertIn(
            "(eco_code, opening_id)",
            (self.SCHEMA / "index/chs_oec_eco_ix.sql").read_text(),
        )
        self.assertIn(
            "orac_chess,chess_opening_eco,chs_oec",
            (
                PROJECT_ROOT / "docs/agent-guardrails/table-abbreviations.csv"
            ).read_text(),
        )
        for subject in ("opn", "gmb"):
            self.assertTrue(
                (self.SCHEMA / f"index/chs_var_main_{subject}_ux.sql").exists()
            )
            self.assertTrue(
                (self.SCHEMA / f"index/chs_var_{subject}_ref_ux.sql").exists()
            )
        for link in ("cmt", "cvr", "ivr", "vvr"):
            self.assertIn(
                "references orac_chess.chess_variation (variation_id)",
                (
                    self.SCHEMA / f"constraint_fk/chs_{link}_variation_fk.sql"
                ).read_text(),
            )

    def test_deployment_verifier_checks_virtual_column_presence(self) -> None:
        """Managed deployment verification includes the new derived column."""
        manifest = PluginDiscovery(self.MANIFEST.parent).load_manifest(self.MANIFEST)
        expected = expected_deployment_objects(
            manifest=manifest, schema_payload_path=self.SCHEMA
        )
        self.assertIn(
            {
                "owner": "ORAC_CHESS",
                "object_name": "CHESS_VARIATION",
                "column_name": "VARIATION_TYPE",
            },
            expected["columns"],
        )

    def test_opening_classification_is_a_fresh_baseline_contract(self) -> None:
        """Openings and systems share one identity with a strict defaulted type."""
        opening = (self.SCHEMA / "table/chess_opening.sql").read_text()
        self.assertRegex(
            opening,
            r"opening_type\s+varchar2\(20 char\) default 'OPENING' not null",
        )
        check = (self.SCHEMA / "constraint_other/chs_opn_type_ck.sql").read_text()
        self.assertIn("check (opening_type in ('OPENING', 'SYSTEM'))", check)
        self.assertIn("drop constraint chs_opn_type_ck", check)
        comments = (self.SCHEMA / "comment/chess_opening.sql").read_text()
        self.assertIn(
            "comment on column orac_chess.chess_opening.opening_type", comments
        )
        manifest = PluginDiscovery(self.MANIFEST.parent).load_manifest(self.MANIFEST)
        expected = expected_deployment_objects(
            manifest=manifest, schema_payload_path=self.SCHEMA
        )
        self.assertIn(
            {
                "owner": "ORAC_CHESS",
                "object_name": "CHESS_OPENING",
                "column_name": "OPENING_TYPE",
            },
            expected["columns"],
        )

    def test_package_contains_database_assets(self) -> None:
        """The ordinary plugin packager accepts a package without Python code."""
        with tempfile.TemporaryDirectory() as directory:
            archive = PluginPackageBuilder().package(self.PLUGIN_DIR, Path(directory))
            self.assertTrue(archive.is_file())


if __name__ == "__main__":
    unittest.main()
