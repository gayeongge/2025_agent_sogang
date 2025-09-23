# 2025_agent_sogang
## 2025년 2학기 Agent 수업
- 2025년 2학기 Agent 수업 프로젝트로 Codex와 함께 `src/` 디렉터릴 설계하고 있습니다.

### `src/` 구조
```text
src/
  watchops/
    actions/
    ai/
    alarm_sources/
    analytics/
    diagnostics/
    ingestion/
    monitoring/
    reporting/
    services/
    verification/
    workflows/
```

### 폴더 관계
```text
[alarm_sources] -> [ingestion] -> [services]
[services] -> [workflows]
[services] -> [diagnostics], [ai], [analytics]
[services] -> [verification]
[services] -> [actions] -> [reporting], [monitoring]
```

### 폴더 역할 메모
- actions/: 등록된 클라이언트를 실행하고 결과를 서비스로 다시 전달한다.
- ai/: 복구 계획을 보완할 가설을 생성한다.
- alarm_sources/: 외부 알람을 공용 도메인 모델로 파싱한다.
- analytics/: 조사를 위해 지표와 로그 간의 상관관계를 제안한다.
- diagnostics/: 기준선(alert baseline) 상태 점검을 모아둔다.
- ingestion/: 페이로드를 오케스트레이터와 선택적 실행기로 라우팅한다.
- monitoring/: 조치 후 Prometheus를 통한 후속 모니터링 항목을 나열한다.
- reporting/: actions 및 monitoring 작업으로부터 효과 보고서를 작성한다.
- services/: 계획 수립, 실행, 검증, 보고를 오케스트레이션한다.
- verification/: 계획의 커버리지와 시뮬레이션 요구사항을 검증한다.
- workflows/: 알람 시나리오를 복구 플레이북에 매핑한다.