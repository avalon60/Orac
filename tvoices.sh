#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 2026-05-04
# Description: Generates Piper WAV samples for every downloaded voice in the Orac Piper voice directory.

set -euo pipefail

ORAC_DEV_HOME="${ORAC_DEV_HOME:-$HOME/PycharmProjects/Orac}"
VOICE_DIR="${ORAC_DEV_HOME}/var/voices/piper"
OUTPUT_DIR="${ORAC_DEV_HOME}/var/tmp/piper_voice_samples"
SAMPLE_TEXT="${1:-Hello Clive. This is an Orac voice test using Piper text to speech.}"

mkdir -p "${OUTPUT_DIR}"

if [[ ! -d "${VOICE_DIR}" ]]
then
  echo "ERROR: Piper voice directory does not exist: ${VOICE_DIR}" >&2
  exit 1
fi

mapfile -t voice_models < <(find "${VOICE_DIR}" -type f -name "*.onnx" | sort)

if [[ "${#voice_models[@]}" -eq 0 ]]
then
  echo "ERROR: No Piper .onnx voice models found under: ${VOICE_DIR}" >&2
  exit 1
fi

echo "Orac dev home : ${ORAC_DEV_HOME}"
echo "Voice dir     : ${VOICE_DIR}"
echo "Output dir    : ${OUTPUT_DIR}"
echo "Sample text   : ${SAMPLE_TEXT}"
echo

for model_file in "${voice_models[@]}"
do
  voice_name="$(basename "${model_file}" .onnx)"
  output_file="${OUTPUT_DIR}/${voice_name}.wav"

  echo "Generating: ${voice_name}"

  python -m piper \
    --data-dir "${VOICE_DIR}" \
    -m "${voice_name}" \
    -f "${output_file}" \
    -- "${SAMPLE_TEXT}"
done

echo
echo "Generated WAV files:"
ls -lh "${OUTPUT_DIR}"/*.wav
