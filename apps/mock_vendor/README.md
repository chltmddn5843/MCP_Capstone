# Mock 벤더 API (담당: 백엔드+DB)

FastAPI, 포트 8001. 설계 문서 10절 엔드포인트 6개 (`/mock/{vendor}/orgs/{org}/seats`, `/usage`, `/release-notes`, `/projects/{id}/model`).
실행기와 수집 배치는 10절 `VendorAdapter` Protocol로만 부른다. 만들 파일: `main.py`, `adapter.py`.
