# Environment Setup Guide

이 문서는 Incident Response Console 프로젝트를 실행하기 위한 개발 환경 구성 절차를 정리한 것입니다.

## 사전 요구사항
- Python 3.10 이상
- git (선택) 및 인터넷 연결
- 운영 체제: Windows 10/11, macOS, Linux (WSL 포함)

## 1. 리포지토리 준비
```bash
# 예시: GitHub clone
# git clone <repo-url>
# cd 20250925
```

## 2. 가상환경 구성
### 옵션 A — 자동 스크립트 사용 (권장)
```bash
python scripts/setup_env.py
```
- 기존 `venv/` 또는 `.venv/` 디렉터리가 있으면 재사용합니다.
- 없으면 `.venv/` 경로에 새 가상환경을 생성합니다.
- 의존성 설치 후 가상환경이 활성화된 새 셸이 실행됩니다 (`exit` 또는 `deactivate`로 종료).
- `PYTHON_BIN` 환경 변수를 설정하면 다른 파이썬 실행기를 지정할 수 있습니다.

### 옵션 B — 수동 구성
```bash
python -m venv .venv        # 또는 python -m venv venv
source .venv/bin/activate   # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 참고: 가상환경 커밋 정책
- 일반적으로 `.venv/`나 `venv/`는 커밋하지 않습니다. 필요 시 `.gitignore`에 등록하세요.

## 3. 환경 변수 (.env) 설정
- OpenAI 기반 기능을 사용하려면 `OPENAI_API_KEY`를 설정해야 합니다.
- 방법 1: 시스템 환경 변수로 설정
  ```bash
  export OPENAI_API_KEY=sk-your-key
  ```
- 방법 2: 프로젝트 루트에 `.env` 파일 생성 후 값 기입
  ```bash
  cp .env.example .env
  # .env 안에 OPENAI_API_KEY=sk-your-key-here 입력
  ```
- 애플리케이션은 `.env` 파일과 환경 변수에서 자동으로 키를 로드합니다.

## 4. 애플리케이션 실행
가상환경이 활성화된 상태에서 다음을 실행합니다.
```bash
python -m src.main
```
실행 후 Slack 톤의 GUI 창이 열리고, 설정 탭에서 자격 정보를 입력한 뒤 `Trigger Alert` → `Verify Recovery` 흐름을 확인합니다.

## 5. 로그/디버깅
- UI 좌측 하단 `System Feed` 패널에서 상태 메시지를 확인할 수 있습니다.
- 콘솔 로그를 파일로 저장하고 싶다면 리다이렉션을 이용하세요.
  ```bash
  python -m src.main > src/log/2025-09-29.log 2>&1
  ```
- 빈 로그 파일은 실행 내용이 기록되지 않았음을 의미합니다.

## 6. 문제 해결 팁
| 증상 | 해결책 |
| --- | --- |
| `ModuleNotFoundError: No module named 'PySide6'` | 가상환경 활성화 후 `pip install -r requirements.txt` 실행 |
| Qt 창이 나타나지 않음 (WSL) | `wsl --update` 후 XServer 혹은 WSLg 확인 |
| `.env` 값이 적용되지 않음 | 파일 위치 확인 (프로젝트 루트), 변수명 오타 확인 |
| `python scripts/setup_env.py` 실행 시 다른 파이썬 사용 | `PYTHON_BIN` 환경 변수로 원하는 인터프리터 지정 |

## 7. 추가 참고 자료
- 메인 README: 프로젝트 구조 및 기능 요약
- `scripts/setup_env.py`: 자동 환경 구성 로직
- `.env.example`: 환경 변수 템플릿

필요에 따라 문서를 업데이트하여 팀원과 공유하세요.
