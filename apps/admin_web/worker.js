// /api/* 를 로컬 서버로 넘긴다. Quick Tunnel 주소는 켤 때마다 바뀌어서 scripts/tunnel.sh가 KV(TUNNEL, 키 origin)에 적는다.
// 로컬 Vite(:5173)가 /api 를 backend로 넘기므로 경로는 그대로 붙인다(AI 비서도 backend가 중계). SSE도 스트림 그대로 통과한다.
const deny = (status, code, message) => Response.json({ error: { code, message, details: null } }, { status })

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    // 로컬 서버는 APP_ENV=dev라 dev-login·'dev.<id>' 토큰이 열려 있다. 공개 주소에서는 여기서 막는다.
    // ponytail: 터널 주소(*.trycloudflare.com)로 직접 오면 이 검사를 건너뛴다. 막으려면 공개용 서버를 APP_ENV=prod로 띄운다
    if (url.pathname === '/api/auth/dev-login' || /^bearer\s+dev\./i.test(request.headers.get('authorization') ?? '')) {
      return deny(403, 'forbidden', '공개 주소에서는 개발용 로그인을 쓸 수 없습니다. 사번·비밀번호로 로그인하세요.')
    }
    const origin = await env.TUNNEL.get('origin', { cacheTtl: 60 }) // ponytail: 터널을 다시 켜면 최대 60초간 옛 주소를 볼 수 있다
    if (!origin) return deny(503, 'internal', '로컬 서버가 꺼져 있습니다. scripts/run_all.sh 와 scripts/tunnel.sh 를 실행하세요.')
    try {
      const res = await fetch(new Request(origin + url.pathname + url.search, request))
      // 터널이 만료·종료되면 Cloudflare가 530/HTML을 준다. 화면이 JSON 오류로 읽게 바꾼다
      if (res.status === 530) return deny(503, 'internal', '로컬 서버(터널)에 연결하지 못했습니다. scripts/tunnel.sh 를 다시 실행하세요.')
      return res
    } catch (e) {
      return deny(502, 'internal', `로컬 서버(터널)에 연결하지 못했습니다: ${e.message}`)
    }
  },
}
