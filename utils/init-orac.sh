#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Rebuild Orac DB, prepare Home Assistant schema, and restore latest backup.

set -euo pipefail

orac-db-deploy.sh --force

# Pre-create bundled plugin schema objects so the data-only restore can import
# plugin-owned tables from the backup.
orac-plugin.sh install --source plugins/home_assistant

orac-restore.sh "${HOME}/OracBackup" <<'EOF'
RECOVER
EOF

# Restore quarantines plugin registry/APEX rows; reinstall all bundled plugins
# afterward to verify local assets and return them to installed/enabled state.
orac-plugin.sh install --all
orac-plugin.sh check home_assistant
