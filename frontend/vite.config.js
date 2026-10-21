import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 개발: /api/ai/* → 에이전트(8002, 백엔드 중계가 생기면 삭제), /api/* → 백엔드(8000). 운영은 nginx.conf.template이 같은 규칙.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api/ai': { target: process.env.AGENT_URL || 'http://localhost:8002', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') },
      '/api': { target: process.env.BACKEND_URL || 'http://localhost:8000', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') },
    },
  },
})
