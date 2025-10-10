# 로컬 Prometheus 환경 구성 가이드

이 디렉터리는 Windows와 macOS 모두에서 Prometheus를 로컬 설치하고, 샘플 메트릭 소스로 Incident Response Console을 테스트할 수 있도록 돕는 스크립트와 설정을 제공합니다. 실제로는 Windows에서만 동작 검증을 할 예정이지만, macOS용 스크립트도 함께 제공합니다.

## 구성 요소

```
prometheus/
  README.md                # 이 문서
  prometheus.yml           # 로컬 개발용 기본 설정(샘플 메트릭 타깃 포함)
  sample_metrics_service.py# Prometheus client 라이브러리를 이용한 샘플 측정치 서버
  windows_setup.ps1        # Windows용 다운로드/설치 스크립트
  mac_setup.sh             # macOS용 다운로드/설치 스크립트
  dist/                    # (자동 생성) 다운로드 받은 원본 압축 파일 보관 폴더
  windows/                 # (자동 생성) Windows용 Prometheus 압축 해제 위치
  mac/                     # (자동 생성) macOS용 Prometheus 압축 해제 위치
```

## 선행 조건

- Python 3.10 이상 (샘플 메트릭 서버 실행용)
- PowerShell 5+ (Windows) 혹은 bash (macOS)
- 인터넷 연결 (Prometheus 바이너리 다운로드)

## 1. 샘플 메트릭 서버 실행

Incident Response Console이 기대하는 `http_error_rate` / `cpu_usage` 메트릭을 제공하기 위해 간단한 HTTP 서버를 띄웁니다.

```powershell
# Windows PowerShell
python -m pip install prometheus-client
python prometheus\sample_metrics_service.py  # 5회 중 1회 정도 임계값을 넘도록 값이 변동합니다.
```

```bash
# macOS / Linux
python3 -m pip install prometheus-client
python3 prometheus/sample_metrics_service.py  # 5회 중 1회 정도 임계값을 넘도록 값이 변동합니다.
```

서버는 기본적으로 `http://127.0.0.1:9001/metrics`에서 노출됩니다. Prometheus 설정 파일(`prometheus.yml`)에는 해당 엔드포인트가 이미 타깃으로 등록돼 있습니다.

## 2. Prometheus 설치 및 실행

### Windows (테스트 대상)

```powershell
# 1) 스크립트 실행 (필요 시 관리자 권한 PowerShell)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
./prometheus/windows_setup.ps1 -Version 2.51.0

# 2) Prometheus 실행
Set-Location -Path .\prometheus\windows\prometheus-2.51.0.windows-amd64
./prometheus.exe --config.file="..\..\prometheus.yml" --storage.tsdb.path="..\..\data"
```

> **Tip:** `--storage.tsdb.path`는 원하는 경로로 자유롭게 바꿔도 됩니다. 예제에서는 프로젝트 루트의 `data/` 폴더를 사용합니다.

### macOS (참고용)

```bash
chmod +x prometheus/mac_setup.sh
./prometheus/mac_setup.sh 2.51.0

cd prometheus/mac/prometheus-2.51.0.darwin-amd64
./prometheus --config.file="../../prometheus.yml" --storage.tsdb.path="../../data"
```

## 3. Incident Response Console에서 Prometheus 연결

Electron UI의 **Prometheus** 탭에 아래 값을 입력한 뒤 `Save` / `Test` 버튼으로 연결을 확인합니다.

- Base URL: `http://127.0.0.1:9090`
- HTTP Error Query: `http_error_rate`
- HTTP Threshold: `0.05`
- CPU Usage Query: `cpu_usage`
- CPU Threshold: `0.80`

샘플 메트릭 서버는 메트릭 값을 주기적으로 업데이트하므로, `Verify Recovery` 버튼으로 실제 쿼리가 수행되는지 확인할 수 있습니다.

## 문제 해결

- **포트 충돌**: `sample_metrics_service.py`가 사용하는 9001 포트나 Prometheus 기본 포트(9090)가 이미 사용 중이라면 스크립트/설정 파일에서 포트를 변경합니다.
- **다운로드 차단**: 사내 프록시 등으로 인해 다운로드가 실패할 경우, 미리 바이너리를 수동으로 내려받아 `prometheus/dist/`에 배치한 후 스크립트에서 Unzip 단계만 수행하세요.
- **인증서 문제**: 회사 네트워크 정책으로 HTTPS 다운로드가 차단되면, 스크립트의 `Invoke-WebRequest`(Windows)나 `curl`(macOS)에 `-Proxy` 옵션 등을 추가해 응용할 수 있습니다.

필요에 따라 스크립트/설정을 수정해도 무방합니다. Windows 환경에서 테스트한 후 Incident Response Console과 Prometheus 연동이 정상 작동하는지 확인하세요.

