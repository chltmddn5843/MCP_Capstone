"""docker compose의 tunnel_kv 서비스 (profile public).

cloudflared Quick Tunnel 컨테이너(tunnel)의 metrics 서버 GET /quicktunnel 에서 터널 주소를 읽어,
고정 주소(Cloudflare Workers, apps/admin_web/wrangler.jsonc)가 /api 를 보낼 곳(KV TUNNEL, 키 origin)에 적는다.
터널이 다시 열려 주소가 바뀌면 다시 적는다. worker.js는 KV를 최대 60초 캐시하므로 반영에 1분쯤 걸린다.

필요한 .env: CF_ACCOUNT_ID, CF_API_TOKEN(Workers KV Storage 편집 권한). 없으면 주소만 로그에 찍고 KV는 건드리지 않는다.
"""

from __future__ import annotations

import os
import time

import requests

METRICS = os.getenv("TUNNEL_METRICS_URL", "http://tunnel:2000/quicktunnel")
ACCOUNT = os.getenv("CF_ACCOUNT_ID", "").strip()
TOKEN = os.getenv("CF_API_TOKEN", "").strip()
NAMESPACE = os.getenv("CF_KV_NAMESPACE_ID", "03329001234647bb88e29f8b56a35027")  # wrangler.jsonc의 TUNNEL
FIXED = os.getenv("PUBLIC_URL", "https://nodi-admin.chltmddn5843.workers.dev")


def tunnel_url() -> str | None:
    try:
        host = requests.get(METRICS, timeout=5).json().get("hostname")
    except (requests.RequestException, ValueError):
        return None
    return f"https://{host}" if host else None


def put_origin(url: str) -> bool:
    if not (ACCOUNT and TOKEN):
        return False
    r = requests.put(f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/storage/kv/namespaces/{NAMESPACE}/values/origin",
                     headers={"Authorization": f"Bearer {TOKEN}"}, data=url.encode(), timeout=15)
    if not r.ok:
        print(f"tunnel_kv: KV 갱신 실패 {r.status_code} {r.text[:200]}", flush=True)
    return r.ok


def main() -> None:
    last = None
    if not (ACCOUNT and TOKEN):
        print("tunnel_kv: CF_ACCOUNT_ID·CF_API_TOKEN이 없어 고정 주소는 갱신하지 않습니다. 아래 터널 주소로 접속하세요.", flush=True)
    while True:
        url = tunnel_url()
        if url and url != last:
            print(f"tunnel_kv: 터널 {url}", flush=True)
            if put_origin(url):
                print(f"tunnel_kv: 고정 주소 {FIXED} 의 /api 가 1분 안에 이 터널로 바뀝니다.", flush=True)
            last = url
        time.sleep(15)


if __name__ == "__main__":
    main()
