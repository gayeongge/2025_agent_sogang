# Incident Response Console

Prometheus Alertmanager, Slack, Jira를 한 화면에서 다루는 인시던트 대응 콘솔입니다. `order.md` 기획서의 MVP 요구사항(F1~F4)과 비기능 요구를 반영해 Slack 스타일 UI, 연계 API 호출, 사후 검증 흐름을 제공합니다.

## 주요 기능 요약
- **알람 트리거 (F1)**: 선행 정의된 Nginx 5xx / CPU Spike 시나리오를 버튼 한 번으로 재현하고 타임라인에 기록.
- **원인 분석 (F2)**: 시나리오별 Top-3 가설과 증거를 자동으로 화면에 노출.
- **조치 실행 (F3)**: 사용자 확인 후 Slack 알림, Jira 이슈 생성, 추천 액션 안내를 Presenter가 비동기로 처리.
- **사후 검증 (F4)**: Prometheus 즉시 쿼리로 조치 효과를 확인하고 Feed/팝업으로 결과 피드백.
- **안전 가드**: 필수 입력값 검증, 실패 시 일관된 오류 메시지, 버튼 잠금 등 비기능 요구 충족.

## 코드 구조 (MVP 패턴)
```
src/
  main.py                         # python -m src.main 진입점
  incident_console/
    app.py                        # View + Presenter 초기화
    models.py                     # AlertScenario, 설정 데이터클래스
    scenarios.py                  # MVP 시나리오 시드 데이터
    async_tasks.py                # QThreadPool 기반 비동기 실행 헬퍼
    integrations/
      slack.py | jira.py | prometheus.py
    presenters/
      main_presenter.py           # 신호 연결 및 공통 에러 처리
      alert_presenter.py          # 알람 렌더링 & 후속 액션 오케스트레이션
      slack_presenter.py          # Slack 테스트/저장/발송
      jira_presenter.py           # Jira 테스트/저장/이슈 생성
      prometheus_presenter.py     # Prometheus 테스트/저장/복구 검증
      state.py | utils.py         # Presenter 공용 상태 & 유틸
    views/
      main_view.py                # Qt UI 구성 및 Signal 정의
scripts/
  setup_env.py                    # 가상환경 준비 & 활성화 자동화
```

## 환경 설정
자세한 환경 구성 및 OpenAI 키 설정 방법은 `docs/environment_setup.md` 문서를 참고하세요.

## 애플리케이션 실행
가상환경이 활성화된 셸에서 아래 명령을 실행합니다.
윈도우의 경우 powershell에서 수행합니다.
```bash
python -m src.main
```
실행되면 Slack 톤의 GUI 창이 열리고, 각 탭에서 자격 정보를 입력한 뒤 `Trigger Alert` → `Verify Recovery` 순서로 흐름을 확인할 수 있습니다.

## 로그 및 모니터링
- 모든 실시간 피드백은 UI 좌측 하단 **System Feed** 영역에 축적됩니다.
- CLI 로그가 필요하면 실행 시 리다이렉션으로 저장할 수 있습니다.
  ```bash
  python -m src.main > src/log/$(date +%Y_%m_%d).log 2>&1
  ```
- `src/log/` 아래 날짜별 로그 파일을 남길 수 있으며, 빈 파일은 실행 내용이 없는 상태를 의미합니다.

## 확장 아이디어
- 실제 Alertmanager Webhook 수신 → Presenter 연동
- Slack/Jira/Prometheus API Mocking 및 Presenter 단위 테스트 추가
- 시나리오/가설 정의를 외부 YAML, DB와 연동해 운영 확장
- UI 다국어 지원 및 로그 파일 뷰어 추가

## 라이선스
수업 목적의 예시 코드로 별도 라이선스를 명시하지 않습니다.