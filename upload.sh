#!/bin/bash
SYNC_PATH="$(awk -F "=" '/syncpath/ {print $2}' config.ini | tr -d ' ')"
SCRIPT_DIR="$(realpath "$(dirname "$0")")"

cd "${SYNC_PATH}"

unzip -o Gadgetbridge.zip -d Gadgetbridge

cd "${SCRIPT_DIR}"
./uploader.py "$@"
