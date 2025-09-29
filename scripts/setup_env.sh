#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=""
VENV_DIR="/.venv"
PYTHON_BIN=python3

if ! command -v "" >/dev/null 2>&1; then
  echo "[ERROR]  명령을 찾을 수 없습니다. PYTHON_BIN 환경 변수를 사용해 경로를 지정하세요." >&2
  return 1 2>/dev/null || exit 1
fi

if [ ! -d "" ]; then
  echo "[INFO] 가상환경을 생성합니다: "
  "" -m venv ""
fi

# shellcheck disable=SC1091
source "/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "/requirements.txt"

echo "[INFO] 가상환경이 활성화되었습니다. 작업이 끝나면 'deactivate' 명령으로 종료하세요."
