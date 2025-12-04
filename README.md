# Incident Response Console

Prometheus 알림에 대한 퍼스트 리스폰더 흐름을 시뮬레이션하는 Python FastAPI 백엔드와 Electron 데스크톱 UI입니다. `order.md`의 MVP 기능(F1-F4)인 러너북 시나리오 실행, 가설·증거 확인, Slack 알림 전송, Prometheus 쿼리 기반 복구 검증을 모두 제공합니다.

## 아키텍처

```
src/
  main.py                         # python -m src.main -> FastAPI 백엔드 실행
  backend/
    app.py                        # FastAPI 라우트 (alerts, Slack, Prometheus)
    services.py                   # 비즈니스 로직 및 공유 상태 헬퍼
    state.py                      # API가 쓰는 인메모리 상태
    main.py                       # uvicorn 실행기 (INCIDENT_BACKEND_* env 사용)
  incident_console/
    models.py | scenarios.py      # 도메인 모델과 샘플 인시던트 시나리오
    integrations/                 # Slack/Prometheus HTTP 클라이언트(requests 기반)
    errors.py                     # 공용 IntegrationError 타입
    utils.py                      # 시간/임계치 파싱 등 헬퍼
electron/
  package.json                    # npm 메타데이터 (Electron 런타임)
  main.js | preload.js            # 데스크톱 셸 + Python 백엔드 부트스트랩
  renderer/                       # API와 통신하는 HTML/CSS/JS 프런트엔드
prometheus/
  README.md                       # 로컬 Prometheus 설정 & 샘플 메트릭 피더
  sample_metrics_service.py       # 결정론적 임계치 초과 샘플러
scripts/
  setup_env.py                    # venv 생성 및 Python 의존성 설치
```

## 운영 가이드

- 플랫폼별 설치/실행/UI 안내는 `SETUP.md`를 참고하세요.

## 사전 준비물

- Python 3.10+
- Node.js 18+ (Electron 런타임)
- 실서비스 연동 시 Slack/Prometheus 자격 증명
- 선택: OpenAI API 키(`OPENAI_API_KEY`)를 넣으면 AI 기반 한국어 분석/액션 플랜 생성 가능

환경 변수(`OPENAI_API_KEY`, 통합 토큰 등)는 프로젝트 루트의 `.env`에 저장해도 됩니다.

### 선택: 이메일 알림(MCP)

UI에서 등록한 수신자에게 액션 실행/연기 결과를 메일로 보내려면 다음 환경 변수를 설정하세요.

- `INCIDENT_EMAIL_SMTP_HOST` / `INCIDENT_EMAIL_SMTP_PORT`
- `INCIDENT_EMAIL_SMTP_USER` / `INCIDENT_EMAIL_SMTP_PASSWORD`
- `INCIDENT_EMAIL_FROM` (미지정 시 SMTP 사용자로 기본값 설정)
- `INCIDENT_EMAIL_SMTP_TLS` (`1`이면 STARTTLS, `0`이면 비활성)

값을 비워두면 안전상 이메일 발송 기능은 꺼진 상태로 유지됩니다.

## Electron UI 설정

```bash
cd electron
npm install
npm run start  # python -m src.backend.main을 띄우고 데스크톱 창을 엽니다
```

Electron 런처는 FastAPI 백엔드를 자동으로 시작합니다(기본 `http://127.0.0.1:8000`). 데스크톱 창을 닫으면 Python 프로세스도 함께 종료됩니다.

### 서비스 개별 실행

각 레이어를 따로 띄우고 싶다면:

```bash
# 터미널 1 - 백엔드만 실행
python -m src.backend.main
# 서버: http://127.0.0.1:8000

# 터미널 2 - Python 자동 실행 없이 렌더러만 열기
cd electron
INCIDENT_BACKEND_HOST=127.0.0.1 INCIDENT_BACKEND_PORT=8000 npm start
```

## 주요 API 경로

| Method | Route               | Purpose                                          |
| ------ | ------------------- | ------------------------------------------------ |
| POST   | `/alerts/trigger`   | 데모 시나리오를 골라 피드/가설/액션을 채움        |
| POST   | `/alerts/verify`    | 저장된 임계치로 Prometheus 즉시 쿼리 실행         |
| POST   | `/slack/test`       | `auth.test` 연결 확인                             |
| POST   | `/slack/save`       | Slack 기본값을 메모리에 저장                      |
| POST   | `/slack/dispatch`   | 마지막 시나리오를 Slack으로 전송                  |
| POST   | `/prometheus/test`  | HTTP + CPU 쿼리를 1회 실행                        |
| POST   | `/prometheus/save`  | Prometheus 설정을 저장                            |
| GET    | `/state`            | 현재 인메모리 설정/피드/최근 알림 덤프            |
| GET    | `/health`           | Electron 부팅 시 사용하는 라이브니스 체크         |

모든 응답은 JSON이며, 오류는 FastAPI Problem Details 형식을 사용하고 `detail`에 실패 원인을 담습니다(원래 코드의 `IntegrationError`를 유지).

## 로컬 Prometheus 환경 (상세)

이 섹션은 `prometheus/README.md`의 내용을 통합한 것입니다. 로컬에서 샘플 메트릭을 제공하고 Prometheus를 실행해 UI를 바로 연결할 수 있습니다.

### 구성 요소

```
prometheus/
  prometheus.yml           # 로컬 개발용 기본 설정(샘플 메트릭 타깃 포함)
  sample_metrics_service.py# http_error_rate / cpu_usage를 내보내는 샘플 서버
  windows_setup.ps1        # Windows용 Prometheus 다운로드/설치 스크립트
  mac_setup.sh             # macOS용 다운로드/설치 스크립트
  dist/                    # (자동 생성) 다운로드 받은 원본 압축 파일
  windows/                 # (자동 생성) Windows용 압축 해제 위치
  mac/                     # (자동 생성) macOS용 압축 해제 위치
```

선행 조건: Python 3.10+, PowerShell 5+ 또는 bash, 인터넷 연결(바이너리 다운로드용).

### 1) 샘플 메트릭 서버 실행

```powershell
# Windows PowerShell
python -m pip install prometheus-client
python prometheus\sample_metrics_service.py  # 값이 주기적으로 변동하며 임계치도 넘습니다.
```

```bash
# macOS / Linux
python3 -m pip install prometheus-client
python3 prometheus/sample_metrics_service.py
```

- 기본 엔드포인트: `http://127.0.0.1:9001/metrics`
- `prometheus.yml`에 이미 타깃으로 등록돼 있습니다.

### 2) Prometheus 설치 및 실행

**Windows(검증 대상)**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
./prometheus/windows_setup.ps1 -Version 2.51.0

Set-Location -Path .\prometheus\windows\prometheus-2.51.0.windows-amd64
./prometheus.exe --config.file="..\..\prometheus.yml" --storage.tsdb.path="..\..\data"
```

> `--storage.tsdb.path`는 원하는 위치로 바꿀 수 있습니다(예: 프로젝트 루트의 `data/`).

**macOS(참고)**

```bash
chmod +x prometheus/mac_setup.sh
./prometheus/mac_setup.sh 2.51.0

cd prometheus/mac/prometheus-2.51.0.darwin-amd64
./prometheus --config.file="../../prometheus.yml" --storage.tsdb.path="../../data"
```

### 3) 콘솔에서 Prometheus 연결

Electron UI의 **Prometheus** 탭에 아래 값을 넣고 `Save` / `Test`를 눌러 확인합니다.

- Base URL: `http://127.0.0.1:9090`
- HTTP Error Query: `http_error_rate`
- HTTP Threshold: `0.05`
- CPU Usage Query: `cpu_usage`
- CPU Threshold: `0.80`

샘플 메트릭 서버가 값을 갱신하므로 `Verify Recovery` 버튼으로 실제 쿼리·임계치 검증을 확인할 수 있습니다.

### 문제 해결

- 포트 충돌: 샘플 서버(9001)나 Prometheus(9090)가 이미 점유 중이면 스크립트/설정에서 포트를 바꿉니다.
- 다운로드 차단: 바이너리를 미리 받아 `prometheus/dist/`에 두고 압축 해제 단계만 수행하세요.
- 인증서/프록시: 회사 네트워크 제약이 있으면 `Invoke-WebRequest`(Windows)나 `curl`(macOS)에 프록시 옵션을 추가해 사용하세요.

## 현재 동작

- 알림 트리거는 여전히 `scenarios.py`에서 시나리오를 선택해 가설/증거/액션을 채웁니다.
- Slack/Prometheus 연동은 기존 `requests` 기반 클라이언트를 그대로 사용하므로 실서비스로 포인팅할 수 있습니다.
- 백엔드가 살아있는 동안 피드는 인메모리에 유지되며, 재시작 시 초기화됩니다.
- Electron 렌더러가 유일한 UI이며, 빠른 훑어보기를 위한 밝은 모노톤 스타일을 사용합니다.
- 백그라운드 Prometheus 모니터가 몇 초 간격으로 샘플링하고, 최근 5개 중 하나라도 임계치 초과 시 이상을 감지해 인시던트 리포트를 자동 생성합니다.
- 체크박스로 Slack 등 알림 대상을 토글해 자동 보고가 어느 채널로 갈지 바로 확인할 수 있습니다.
- 설정 패널에서 MCP 이메일 수신자를 추가/삭제할 수 있고, 페이지당 최대 5개 주소와 페이징된 히스토리를 제공합니다. SMTP가 설정되어 있고 주소가 하나 이상 있을 때만 액션 실행 결과를 메일로 보냅니다.
- OpenAI API 키가 설정되면 Prometheus 이상 징후 시 Slack 전송 전에 AI가 작성한 한국어 분석/액션 플랜을 사용하고, 없으면 결정론적 텍스트를 사용합니다.
