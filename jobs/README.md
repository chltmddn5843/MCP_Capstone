# 배치 (담당: 백엔드+DB)

지금은 `POST /internal/jobs/{name}/run`으로 동기 실행. RabbitMQ + Celery 전환은 `docs/추후개발.md` 1절. 이름은 백엔드 `JOBS`와 같아야 한다:
`collect_release_notes`, `collect_usage`, `check_thresholds`.
AI 없이 코드만. 새 업데이트를 찾으면 시스템 계정(`dev.sys`)으로 에이전트를 한 번 호출한다.
