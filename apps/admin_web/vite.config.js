import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// /api/* → 백엔드(8000). 실제 연결 시 src/api.js에서 fetch('/api/...')로 부른다.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', rewrite: (p) => p.replace(/^\/api/, '') } },
  },
})
