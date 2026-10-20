# DB (담당: 백엔드+DB)

`schema.sql`(6절 테이블 21개, SQLite로 시작하되 PostgreSQL로 옮길 수 있게)과 `seed/`(10절 '한빛제조' 시드).
컬럼 enum 값은 `schemas.common`의 영어 값과 같아야 한다. id는 문자열.
`apps/backend/fixtures.py`의 고정 데이터가 시드의 축약판이니, 시드는 그 id들을 포함해야 계약 테스트가 그대로 통과한다.
