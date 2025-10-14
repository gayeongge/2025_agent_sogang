# Incident Response Console 요약 가이드

## Windows 환경

### 1. 초기 환경 구축
- Python 3.10 이상과 Node.js 18 이상을 설치합니다.
- `python -m venv .venv`로 가상환경을 만든 뒤 `./.venv/Scripts/python -m pip install -r requirements.txt`로 백엔드 의존성을 설치합니다.
- `cd electron` 후 `npm install`로 Electron 렌더러 의존성을 준비합니다.
- **prometheus**폴더 하위에 있는 README.md 를 따라 로컬에 프로메테우스를 설치하고, 샘플 데이터 제너레이터를 실행시킵니다.

### 2. 콘솔 실행
- 터미널 1: `python prometheus\sample_metrics_service.py`를 실행해 9001 포트에 샘플 메트릭을 노출합니다.
- 터미널 2: `cd prometheus\windows\prometheus-2.51.0.windows-amd64` 후 `./prometheus.exe --config.file="..\..\prometheus.yml" --storage.tsdb.path="..\..\data"`로 Prometheus 서버(9090)를 시작합니다.
- 터미널 3: `cd electron`에서 `npm run start`를 실행하면 FastAPI 백엔드와 Electron 데스크톱 앱이 함께 올라옵니다. UI 상단의 `Verify Now` 버튼은 `/alerts/verify`를 호출해 즉시 임계치 검증을 수행합니다.

### 3. 화면 안내
- `Monitoring Snapshot`: HTTP Error Rate와 CPU Usage 현재값 및 임계치를 표시하며 실시간 검증 결과를 보여줍니다.
- `Recent Incidents`: 시나리오별 최신 알림 타임라인을 나열합니다.
- `Incident Analysis`: 백엔드가 생성한 분석 리포트와 제안 액션을 표시합니다.
- `System Feed`: Slack/Jira 전송 내역, Prometheus 검증 이벤트 등 운영 로그를 순차적으로 제공합니다.
- 우측 `자동 알림 채널` 토글: Slack/Jira 대상에 대한 자동 알림 사용 여부를 저장하며 `/notifications/preferences`로 동기화됩니다.
- `Slack` 탭: 봇 토큰, 워크스페이스, 기본 채널을 입력 후 `Test`로 연결 확인, `Save`로 백엔드 메모리 상태에 반영합니다.
- `Jira` 탭: 사이트 URL·프로젝트 키·계정 정보를 입력하고 `Test`로 REST 연결을 확인한 뒤 `Save` 저장, `Create Jira Issue`로 최신 인시던트를 바로 등록합니다.
- `Prometheus` 탭: 샘플 환경 기준으로 `Base URL`에 `http://127.0.0.1:9090`, `HTTP Error Query`에 `http_error_rate`, `CPU Usage Query`에 `cpu_usage`, 임계치 0.05/0.80을 입력 후 `Test`와 `Save`로 검증 및 저장합니다.

## macOS 환경

### 1. 초기 환경 구축
- Python 3.10 이상과 Node.js 18 이상을 설치합니다.
- `python3 -m venv .venv`로 가상환경을 생성하고 `source .venv/bin/activate && pip install -r requirements.txt`로 Python 의존성을 설치합니다.
- `cd electron && npm install`로 Electron 의존성을 설치합니다.
- **prometheus**폴더 하위에 있는 README.md 를 따라 로컬에 프로메테우스를 설치하고, 샘플 데이터 제너레이터를 실행시킵니다.

### 2. 콘솔 실행
- 터미널 1: `python3 prometheus/sample_metrics_service.py`로 샘플 메트릭 엔드포인트(9001)를 실행합니다.
- 터미널 2: `cd prometheus/mac/prometheus-2.51.0.darwin-amd64` 후 `./prometheus --config.file="../../prometheus.yml" --storage.tsdb.path="../../data"`로 Prometheus 서버(9090)를 구동합니다.
- 터미널 3: `cd electron && npm run start`로 Electron 앱을 실행하면 FastAPI 백엔드가 자동으로 함께 시작되며, `Verify Now` 버튼으로 즉시 Prometheus 검증을 재실행할 수 있습니다.

### 3. 화면 안내
- UI 구성과 설정 방법은 Windows와 동일하며, `Monitoring Snapshot`, `Recent Incidents`, `Incident Analysis`, `System Feed`가 중앙 패널에, Slack/Jira/Prometheus 설정 탭이 우측 패널에 위치합니다.
- `Prometheus` 탭에는 macOS에서도 동일하게 `http://127.0.0.1:9090`, `http_error_rate`, `cpu_usage`, 임계치 0.05/0.80을 입력하고 `Test`·`Save`로 연결 상태를 확인합니다.
- Slack/Jira 탭과 알림 토글 역시 동일하게 작동하며, `Create Jira Issue` 버튼으로 최신 인시던트를 Jira에 생성할 수 있습니다.

> 필요 시 `scripts/setup_env.py`로 가상환경 설정을 자동화하거나, `python -m src.backend.main`을 별도 터미널에서 실행해 백엔드 헬스체크를 선행할 수 있습니다.
