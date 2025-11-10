1. 알람 소스 확정
- 모니터링 시스템 알람 : Prometheus Alertmanager
- 협업 툴 알람 : Slack
- 알람 소스 확정 및 MVP 시나리오 매핑:
A.Nginx/웹 5xx오류 급증
- Prometheus(http_error_rate 임계치 초과)
- slack(운영 채널 알림)
B. CPU 스파이크
- Prometheus(cpu_usage 임계치 초과)
2. 아키텍처 스켈레톤
- 알림 수집 모듈
-- Prometheus Alertmanager Webhook 수집
-- Slack API 채널 알람 수집
- 진단 모듈
-- AI 및 사용자 데이터 기반 원인 가설 생성 ( top_k)
-- 알람 소스별 메트릭, 로그 연계 분석
- 조치 모듈
-- 조치 방안 제안 및 실행 mcp 또는 api 호출
-- 안전 가드 적용 ( 권한 검증, 실행 전 시뮬레이션 등 )
- 검증 모듈
-- Prometheus 지표 기반 사후 모니터링
-- 조치 효과 리포트 생성 ( 정상화 여부 등 )
3-1. 기능 요구사항 (Functional Requirements)
F1: Prometheus Alertmanager와 Slack에서 알람을 수집한다.
F2: 회사 데이터를 활용하여 알람을 분석하고 원인 가설 Top-3과 증거를 생성한다.
F3: 조치 방안을 제안하고, 선택된 방안을 실행 가능하게 한다.
F4: 조치 후 Prometheus 지표를 기반으로 회복 여부를 검증한다.
3-2.비기능 요구사항 (Non-Functional Requirements)
NF1: 안전 가드를 통해 잘못된 자동 조치를 예방한다.
NF2: Slack, Prometheus와의 연동 시 API Rate Limit 내에서 안정적으로 동작해야 한다
