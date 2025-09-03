#!/bin/bash
SYNC_PATH="$(awk -F "=" '/syncpath/ {print $2}' config.ini | tr -d ' ')"
WORK_PATH="$(awk -F "=" '/workpath/ {print $2}' config.ini | tr -d ' ')"
SCRIPT_DIR="$(realpath "$(dirname "$0")")"

if [[ ! -d "${SCRIPT_DIR}/venv" ]]; then
  python3 -m venv "${SCRIPT_DIR}/venv"
  . venv/bin/activate
  pip install stravalib
fi

. venv/bin/activate

[[ -d "${WORK_PATH}" ]] || mkdir -p "${WORK_PATH}"

cp "${SYNC_PATH}/Gadgetbridge.zip" "${WORK_PATH}/Gadgetbridge.zip"

cd "${WORK_PATH}"

unzip -o Gadgetbridge.zip -d Gadgetbridge

cd "${SCRIPT_DIR}"
./uploader.py "$@"
