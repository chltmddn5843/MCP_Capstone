// /api/* 를 로컬 서버로 넘긴다. Quick Tunnel 주소는 켤 때마다 바뀌어서 scripts/tunnel.sh가 KV(TUNNEL, 키 origin)에 적는다.
// 로컬 Vite(:5173)가 /api, /api/ai 를 backend·agent로 나눠 주므로 경로는 그대로 붙인다. SSE도 스트림 그대로 통과한다.
export default {
  async fetch(request, env) {
    const origin = await env.TUNNEL.get('origin', { cacheTtl: 60 }) // ponytail: 터널을 다시 켜면 최대 60초간 옛 주소를 볼 수 있다
    if (!origin) {
      return Response.json({ error: { code: 'internal', message: '로컬 서버가 꺼져 있습니다. scripts/run_all.sh 와 scripts/tunnel.sh 를 실행하세요.' } }, { status: 503 })
    }
    const url = new URL(request.url)
    try {
      return await fetch(new Request(origin + url.pathname + url.search, request))
    } catch (e) {
      return Response.json({ error: { code: 'internal', message: `로컬 서버(터널)에 연결하지 못했습니다: ${e.message}` } }, { status: 502 })
    }
  },
}
