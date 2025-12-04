# Incident Response Console 설정 가이드

## 공통 준비물
- Python 3.10+
- Node.js 18+
- (선택) `.env`에 `OPENAI_API_KEY`, Slack/Prometheus/SMTP 값 저장

## Windows

### 1) 초기 환경 구축 (scripts 사용)
- `python scripts\setup_env.py`  
  - `.venv`(없으면 생성)에서 `requirements.txt`를 설치하고, 완료 후 해당 가상환경이 활성화된 쉘로 진입합니다.
- `cd electron && npm install` (Electron 런타임 의존성 설치)

### 2) 콘솔 실행
- 샘플 메트릭 서버: `python prometheus\sample_metrics_service.py`
- Electron + 백엔드 동시 실행: `cd electron && npm run start`  
  - Electron이 FastAPI 백엔드를 자동으로 띄웁니다(기본 `http://127.0.0.1:8000`).
- 백엔드만 실행하려면: `python -m src.backend.main`

### 3) Prometheus 로컬 실행
- 상세 절차는 루트 `README.md`의 “로컬 Prometheus 환경 (상세)” 섹션을 따르세요. (필요 시 `prometheus/windows_setup.ps1` 사용)

## macOS

### 1) 초기 환경 구축 (scripts 사용)
- `python3 scripts/setup_env.py`
- `cd electron && npm install`

### 2) 콘솔 실행
- 샘플 메트릭 서버: `python3 prometheus/sample_metrics_service.py`
- Electron + 백엔드 동시 실행: `cd electron && npm run start`
- 백엔드만 실행: `python3 -m src.backend.main`

### 3) Prometheus 로컬 실행
- 루트 `README.md`의 “로컬 Prometheus 환경 (상세)” 섹션을 참고하세요. (필요 시 `prometheus/mac_setup.sh`)
