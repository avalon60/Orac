#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 2026-05-17
# Description: Audition Kokoro British English voices using the Orac speech helper.

set -euo pipefail

resolve_path() {
  local target="$1"

  if command -v realpath >/dev/null 2>&1; then
    realpath "$target"
    return
  fi

  if [[ "$target" = /* ]]; then
    printf '%s\n' "$target"
  else
    printf '%s/%s\n' "$PWD" "${target#./}"
  fi
}

SCRIPT_PATH="$(resolve_path "${BASH_SOURCE[0]}")"
SCRIPTS_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
ORAC_SAY="${SCRIPTS_DIR}/orac-say.sh"

if [[ ! -x "$ORAC_SAY" ]]; then
  echo "ERROR: orac-say.sh not found or not executable: $ORAC_SAY" >&2
  exit 1
fi

SAMPLE_TEXT="I've seen things you people wouldn't believe. Attack ships on fire off the shoulder of Orion. I watched C-beams glitter in the dark near the Tannhäuser Gate. All those moments will be lost in time, like tears in rain."

echo "Testing female voices"
for VOICE in bf_alice bf_emma bf_lily bf_v0emma bf_v0isabella
do
  echo "Testing ${VOICE}..."
  "$ORAC_SAY" --voice "$VOICE" "$SAMPLE_TEXT"
  sleep 3
done

echo "Testing male voices"
for VOICE in bm_daniel bm_fable bm_george bm_lewis bm_v0george bm_v0lewis
do
  echo "Testing ${VOICE}..."
  "$ORAC_SAY" --voice "$VOICE" "$SAMPLE_TEXT"
  sleep 3
done

echo "Done."
