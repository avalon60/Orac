"""Verify system preferences and installation user provisioning contracts."""

# Author: Clive Bostock
# Date: 2026-10-03
# Description: Covers reserved principals, model migration, and installer bootstrap.

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
import time

from model.orac_auth import ZenFrameAuth


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "resources" / "db" / "schema"
BOOTSTRAP_BODY = (
    SCHEMA_ROOT
    / "orac_code"
    / "package_body"
    / "installation_bootstrap_api.sql"
)
PREFERENCE_BODY = (
    SCHEMA_ROOT / "orac_code" / "package_body" / "user_preferences_api.sql"
)
PREFERENCE_SPEC = (
    SCHEMA_ROOT / "orac_code" / "package_spec" / "user_preferences_api.sql"
)
PREFERENCE_CATALOG = (
    SCHEMA_ROOT
    / "orac_core"
    / "seed_data"
    / "prfdfn_preference_catalog.sql"
)
APEX_EXPORT = PROJECT_ROOT / "resources" / "db" / "apex" / "orac_apps" / "f1042.sql"
DEPLOY_SCRIPT = PROJECT_ROOT / "bin" / "orac-db-deploy.sh"
COMPOSE_FILE = PROJECT_ROOT / "resources" / "docker" / "oracle" / "docker-compose.yaml"
SETUP_SCRIPT = (
    PROJECT_ROOT
    / "resources"
    / "docker"
    / "oracle"
    / "setup"
    / "042-orac-principals.sh"
)
USERS_UPDATE_TRIGGER = (
    SCHEMA_ROOT / "orac_core" / "trigger" / "users_bu.sql"
)
CORE_RUN_ALL = SCHEMA_ROOT / "orac_core" / "run_all.sql"
RUNTIME = PROJECT_ROOT / "src" / "orac_core" / "communications" / "runtime.py"


def test_preference_catalog_separates_system_and_legacy_model_keys() -> None:
    """Only the canonical key is active and neither model key seeds users."""
    sql = PREFERENCE_CATALOG.read_text(encoding="utf-8").lower()
    canonical = sql[sql.index("'general_chat_llm'") : sql.index("'default_llm_id'")]
    legacy = sql[sql.index("'default_llm_id'") : sql.index("'personality_code'")]

    assert "'general chat llm'" in canonical
    assert "'n',\n    20," in canonical
    assert "'n',\n    21," in legacy
    assert "'n'\n  from dual" in legacy


def test_scalar_catalogue_keys_are_installation_wide_and_not_user_seeded() -> None:
    """System scalar definitions must remain active but non-user-editable."""
    sql = PREFERENCE_CATALOG.read_text(encoding="utf-8").lower()
    boundaries = {
        "max_tokens": "push_opt_in",
        "show_reasoning": "strip_reasoning_tags",
        "strip_reasoning_tags": "temperature",
    }

    for pref_key, next_key in boundaries.items():
        block = sql[sql.index(f"'{pref_key}'") : sql.index(f"'{next_key}'")]
        assert "installation-wide" in block
        assert "'y',\n    'n'," in block


def test_generic_system_scalar_api_is_allowlisted_and_catalogue_validated() -> None:
    """The dedicated API should expose only the three approved scalar keys."""
    spec = PREFERENCE_SPEC.read_text(encoding="utf-8").lower()
    body = PREFERENCE_BODY.read_text(encoding="utf-8").lower()

    assert "function get_system_scalar" in spec
    assert "procedure set_system_scalar" in spec
    assert "procedure migrate_system_scalar" in spec
    allowlist = body[
        body.index("function is_system_scalar_key") :
        body.index("end is_system_scalar_key;")
    ]
    assert "'max_tokens'" in allowlist
    assert "'show_reasoning'" in allowlist
    assert "'strip_reasoning_tags'" in allowlist
    assert "validate_catalogue_value" in body
    assert "p_require_user_editable => false" in body


def test_scalar_migration_precedence_cleanup_and_idempotence_contract() -> None:
    """Migration source ordering and TAPI cleanup must remain explicit."""
    sql = PREFERENCE_BODY.read_text(encoding="utf-8").lower()
    migration = sql[
        sql.index("procedure migrate_system_scalar") :
        sql.index("end migrate_system_scalar;")
    ]

    canonical = migration.index("l_candidate := get_system_scalar")
    unanimous = migration.index("l_valid_count = l_user_count")
    configured = migration.index(
        "normalise_system_scalar(p_pref_key, p_config_value)",
        unanimous,
    )
    fallback = migration.index("default_value", configured)
    write = migration.index("set_system_scalar", fallback)
    cleanup = migration.index("user_preferences_tapi.del", write)
    assert canonical < unanimous < configured < fallback < write < cleanup
    assert "not l_has_conflict" in migration
    assert "u.is_active = 'y'" in migration
    assert "u.user_id <> l_system_id" in migration


def test_ordinary_api_rejects_protected_keys_and_relocation() -> None:
    """Ordinary insert/update/delete paths must guard source and target rows."""
    sql = PREFERENCE_BODY.read_text(encoding="utf-8").lower()
    update = sql[sql.index("procedure upd(") : sql.index("end upd;")]
    delete = sql[sql.index("procedure del(") : sql.index("end del;")]

    assert "is_protected_system_key" in sql
    assert "lower(username) = gc_system_username" in sql
    assert "assert_existing_row_allowed(p_pref_id)" in update
    assert "assert_ordinary_target_allowed(p_user_id, p_pref_key)" in update
    assert "assert_existing_row_allowed(p_pref_id)" in delete


def test_scalar_migration_runs_before_model_discovery() -> None:
    """Scalar migration must not depend on LLM discovery at startup."""
    runtime = RUNTIME.read_text(encoding="utf-8")
    startup = runtime.index("self._migrate_system_scalar_preferences()")
    discovery = runtime.index("self._sync_llm_registry()", startup)
    assert startup < discovery
    assert "self.db_session.commit()" in runtime[
        runtime.index("def _migrate_system_scalar_preferences") :
        runtime.index("def _stale_llm_registry_row_ids")
    ]
    assert "self.db_session.rollback()" in runtime[
        runtime.index("def _migrate_system_scalar_preferences") :
        runtime.index("def _stale_llm_registry_row_ids")
    ]


def test_bootstrap_creates_system_and_seeds_only_new_ordinary_user() -> None:
    """Bootstrap must be idempotent and preserve existing ordinary accounts."""
    sql = BOOTSTRAP_BODY.read_text(encoding="utf-8").lower()

    assert "create_user(\n        gc_system_username,\n        gc_system_username," in sql
    assert "p_pref_key    => 'general_chat_llm'" in sql
    assert "l_user_id := create_user(\n          l_username," in sql
    assert "initcap(l_username),\n          'y'" in sql
    assert "orac_code.orac_prefs_seed.seed_user" in sql
    assert sql.index("when no_data_found then\n        l_user_id := create_user") < sql.index(
        "orac_code.orac_prefs_seed.seed_user"
    )
    assert "p_user_created := 'n'" in sql
    assert "l_username in (gc_system_username, 'orac_admin')" in sql
    assert "p_pref_key    => 'max_tokens'" not in sql
    assert "p_pref_key    => 'show_reasoning'" not in sql
    assert "p_pref_key    => 'strip_reasoning_tags'" not in sql


def test_general_chat_migration_has_deterministic_precedence_and_retirement() -> None:
    """Canonical, unanimous history, then configured registry is the precedence."""
    sql = PREFERENCE_BODY.read_text(encoding="utf-8").lower()

    canonical = sql.index("l_canonical_id := get_system_general_chat_llm")
    history = sql.index("count(distinct r.llm_id)")
    configured = sql.index("lower(provider) = lower(trim(p_config_provider))")
    retirement = sql.index("where pref_key = 'default_llm_id'", configured)
    assert canonical < history < configured < retirement
    assert "l_valid_count = l_user_count" in sql
    assert "l_distinct_ids = 1" in sql
    assert "and is_enabled = 'y'" in sql


def test_system_general_chat_getter_resolves_user_before_query() -> None:
    """The private system-user helper must not be invoked from SQL."""
    sql = PREFERENCE_BODY.read_text(encoding="utf-8").lower()
    getter = sql[
        sql.index("function get_system_general_chat_llm return number") :
        sql.index("end get_system_general_chat_llm;")
    ]

    assignment = getter.index("l_system_id := get_system_user_id;")
    query = getter.index("select json_value")
    predicate = getter.index("where user_id = l_system_id", query)

    assert "l_system_id orac_api.users_v.user_id%type;" in getter
    assert assignment < query < predicate
    assert "where user_id = get_system_user_id" not in getter


def test_installer_username_flows_from_host_to_post_liquibase_bootstrap() -> None:
    """The host identity must reach the ordered container setup hook."""
    deploy = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    setup = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert 'ORAC_INSTALL_USERNAME="${SUDO_USER:-$(id -un)}"' in deploy
    assert "export PORT_SQLNET PORT_HTTP PORT_EM ORAC_INSTALL_USERNAME" in deploy
    assert "ORAC_INSTALL_USERNAME: ${ORAC_INSTALL_USERNAME:-}" in compose
    assert "installation_bootstrap_api.ensure_principals" in setup
    assert SETUP_SCRIPT.name > "040-orac-liquibase-deltas.sh"
    assert SETUP_SCRIPT.name < "045-orac-apex-import.sh"


def test_installer_username_validation_uses_canonical_username_rules() -> None:
    """Installer and database validation must reject malformed separators."""
    deploy = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    setup = SETUP_SCRIPT.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP_BODY.read_text(encoding="utf-8")
    shell_pattern = "^[a-z][a-z0-9]*([._-][a-z0-9]+)*$"

    assert shell_pattern in deploy
    assert shell_pattern in setup
    assert "${#ORAC_INSTALL_USERNAME} -lt 3" in deploy
    assert "${#installer_username} -gt 32" in setup
    assert "length(l_username) not between 3 and 32" in bootstrap
    assert "^[a-z][a-z0-9]*([._-][a-z0-9]+)*$" in bootstrap


def test_system_principal_cannot_be_created_by_renaming_an_ordinary_user() -> None:
    """The users update trigger must protect both sides of the reserved name."""
    sql = USERS_UPDATE_TRIGGER.read_text(encoding="utf-8").lower()

    assert "lower(:new.username) = 'system'" in sql
    assert "lower(:old.username) <> 'system'" in sql
    assert "lower(:old.username) = 'system'" in sql
    assert "lower(:new.username) <> 'system'" in sql


def test_system_delete_safeguard_is_wired_into_legacy_sqlcl_entrypoint() -> None:
    """The explicit core trigger list must install the reserved-user guard."""
    sql = CORE_RUN_ALL.read_text(encoding="utf-8")

    assert "@trigger/users_bd.sql" in sql


def test_system_is_hidden_from_users_and_has_dedicated_admin_control() -> None:
    """APEX should expose configuration, not the pseudo-user identity."""
    export = APEX_EXPORT.read_text(encoding="utf-8").lower()

    assert "lower(x.\"username\") <> ''system''" in export
    assert "p_name=>'system configuration'" in export
    assert "p_prompt=>'general chat llm'" in export
    assert "p_prompt=>'max tokens'" in export
    assert "p_prompt=>'show reasoning'" in export
    assert "p_prompt=>'strip reasoning tags'" in export
    assert "max tokens must be a whole number from 1 through 32768" in export
    assert "p_pref_value => json(lower(:p41_show_reasoning))" in export
    assert "p_pref_value => json(lower(:p41_strip_reasoning_tags))" in export
    assert "p_process_name=>'load system preferences'" in export
    assert "user_preferences_api.set_system_general_chat_llm" in export
    assert "p_required_role=>wwv_flow_imp.id(11450849677769089)" in export


def test_frame_auth_rejects_valid_signature_for_system_principal() -> None:
    """A valid shared-secret signature must not make system interactive."""
    secret = b"test-secret"
    timestamp = int(time.time())
    nonce = "nonce-system"
    route = "orac.prompt"
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    body_hash = hashlib.sha256(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    signature = base64.b64encode(
        hmac.new(
            secret,
            f"system|{timestamp}|{nonce}|{route}|{body_hash}".encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    frame = {
        "route": route,
        "payload": payload,
        "meta": {
            "auth": {
                "user": "system",
                "ts": timestamp,
                "nonce": nonce,
                "sig": signature,
            }
        },
    }

    result = ZenFrameAuth(secret).authenticate(frame)

    assert result.ok is False
    assert result.reason == "reserved non-interactive principal"
