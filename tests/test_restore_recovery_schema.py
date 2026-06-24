"""Tests for post-restore plugin recovery database assets."""
# Author: Clive Bostock
# Date: 2026-06-23
# Description: Verifies restore recovery quarantine uses approved schema boundaries.

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESTORE_RECOVERY_SPEC = (
    PROJECT_ROOT
    / "resources/db/schema/orac_code/package_spec/restore_recovery_api.sql"
)
RESTORE_RECOVERY_BODY = (
    PROJECT_ROOT
    / "resources/db/schema/orac_code/package_body/restore_recovery_api.sql"
)
PLUGIN_APEX_MENU_VIEW = (
    PROJECT_ROOT
    / "resources/db/schema/orac_code/view/plugin_apex_app_menu_v.sql"
)


class RestoreRecoverySchemaTests(unittest.TestCase):
    """Verifies post-restore plugin recovery safety objects."""

    def test_restore_recovery_api_quarantines_via_api_tapis(self) -> None:
        """Restore recovery should not update ORAC_CORE tables directly."""
        package_spec = RESTORE_RECOVERY_SPEC.read_text(encoding="utf-8").lower()
        package_body = RESTORE_RECOVERY_BODY.read_text(encoding="utf-8").lower()

        self.assertIn("procedure quarantine_plugin_state", package_spec)
        self.assertIn("orac_api.plugin_apex_apps_v", package_body)
        self.assertIn("orac_api.plugin_registry_v", package_body)
        self.assertIn("orac_api.plugin_apex_apps_tapi.upd", package_body)
        self.assertIn("orac_api.plugin_registry_tapi.upd", package_body)
        self.assertNotIn("update orac_core.", package_body)
        self.assertNotIn("delete from orac_core.", package_body)
        self.assertNotIn("insert into orac_core.", package_body)

    def test_restore_recovery_uses_non_launchable_plugin_states(self) -> None:
        """Quarantined rows should be disabled and excluded from app launch views."""
        package_body = RESTORE_RECOVERY_BODY.read_text(encoding="utf-8").lower()
        menu_view = PLUGIN_APEX_MENU_VIEW.read_text(encoding="utf-8").lower()

        self.assertIn("l_row.install_status := 'pending'", package_body)
        self.assertIn("l_row.installed_app_id := null", package_body)
        self.assertIn("l_row.enabled := 'n'", package_body)
        self.assertIn("gc_recovery_status", package_body)
        self.assertIn("recovery_pending", package_body)
        self.assertIn("where enabled = 'y'", menu_view)
        self.assertIn("and install_status = 'installed'", menu_view)
        self.assertIn("and installed_app_id is not null", menu_view)


if __name__ == "__main__":
    unittest.main()
