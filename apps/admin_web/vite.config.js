import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// /api/* → 백엔드(8000). 실제 연결 시 src/api.js에서 fetch('/api/...')로 부른다.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 백엔드 /ai/tasks 중계가 생기면 '/api/ai' 항목을 지운다. 운영은 nginx.conf.template이 같은 규칙.
      '/api/ai': { target: process.env.AGENT_URL || 'http://localhost:8002', rewrite: (p) => p.replace(/^\/api/, '') },
      '/api': { target: process.env.BACKEND_URL || 'http://localhost:8000', rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
})
