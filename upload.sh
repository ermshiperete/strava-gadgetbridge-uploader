#!/bin/bash
set -eu

echo "Starting Strava uploader wrapper..." >> /tmp/strava-uploader.log

trap 'echo "Exiting Strava uploader wrapper..." >> /tmp/strava-uploader.log' EXIT

SCRIPT_DIR="$(realpath "$(dirname "$0")")"
SYNC_PATH="$(awk -F "=" '/syncpath/ {print $2}' "${SCRIPT_DIR}/config.ini" | tr -d ' ')"
WORK_PATH="$(awk -F "=" '/workpath/ {print $2}' "${SCRIPT_DIR}/config.ini" | tr -d ' ')"

if [[ ! -d "${SCRIPT_DIR}/venv" ]]; then
  echo "Setting up..."
  python3 -m venv "${SCRIPT_DIR}/venv"
  . "${SCRIPT_DIR}/venv/bin/activate"
  pip install stravalib
  echo "Installation finished"
fi

. "${SCRIPT_DIR}/venv/bin/activate"

[[ -d "${WORK_PATH}" ]] || mkdir -p "${WORK_PATH}"

cp "${SYNC_PATH}/Gadgetbridge.zip" "${WORK_PATH}/Gadgetbridge.zip"

cd "${WORK_PATH}"

unzip -q -o Gadgetbridge.zip -d Gadgetbridge

cd "${SCRIPT_DIR}"
./main.py "$@"
