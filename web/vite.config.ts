import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 개발 서버에서 /api 요청은 VITE_API_PROXY(백엔드 주소)로 넘깁니다. 비어 있으면 프록시하지 않습니다.
const target = process.env.VITE_API_PROXY;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: target ? { '/api': { target, changeOrigin: true } } : undefined,
  },
});
