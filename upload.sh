#!/bin/bash
set -eu

log() {
  echo "$(date --iso-8601=seconds): ${*}" | tee --append /tmp/strava-uploader.log
}

log "Starting Strava uploader wrapper..."

trap 'log "Exiting Strava uploader wrapper..."' EXIT

SCRIPT_DIR="$(realpath "$(dirname "$0")")"
SYNC_PATH="$(awk -F "=" '/syncpath/ {print $2}' "${SCRIPT_DIR}/config.ini" | tr -d ' ')"
WORK_PATH="$(awk -F "=" '/workpath/ {print $2}' "${SCRIPT_DIR}/config.ini" | tr -d ' ')"

if [[ ! -d "${SCRIPT_DIR}/venv" ]]; then
  log "Setting up..."
  python3 -m venv "${SCRIPT_DIR}/venv"
  . "${SCRIPT_DIR}/venv/bin/activate"
  pip install stravalib
  log "Installation finished"
fi

. "${SCRIPT_DIR}/venv/bin/activate"

if [[ "${1:-}" != "--help" ]]; then
  [[ -d "${WORK_PATH}" ]] || mkdir -p "${WORK_PATH}"

  if [[ ! -f "${SYNC_PATH}/Gadgetbridge.zip" ]]; then
    log "No new Gadgetbridge.zip file found"
    exit 0
  fi

  mv "${SYNC_PATH}/Gadgetbridge.zip" "${WORK_PATH}/Gadgetbridge.zip"

  cd "${WORK_PATH}"

  unzip -q -o Gadgetbridge.zip -d Gadgetbridge

  cd "${SCRIPT_DIR}"
fi

./main.py "$@"
