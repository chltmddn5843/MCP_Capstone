"""공유 스키마 패키지. 백엔드·MCP·에이전트·UI가 전부 여기서 import한다.

규칙
- id는 전부 문자열.
- enum 값은 영어 snake_case. 한글은 UI 라벨에서만 쓴다.
- 날짜·시각은 ISO 8601, 시각은 UTC(aware datetime).
- 금액은 원화 정수(krw)와 달러 소수(usd)를 함께 둔다.
- 응답은 항상 {"data", "meta"} 또는 {"error"} 봉투.
"""

from schemas.common import *  # noqa: F401,F403
