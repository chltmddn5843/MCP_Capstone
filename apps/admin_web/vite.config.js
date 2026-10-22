import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// /api/* → 백엔드(8000). AI 비서(/ai/tasks)도 백엔드가 에이전트로 중계한다. 운영은 nginx.conf.template이 같은 규칙.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/api': { target: process.env.BACKEND_URL || 'http://localhost:8000', rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
})
