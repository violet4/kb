import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 25691,
    strictPort: true,
    // Proxy every backend call under one /api prefix, same shape as synth's
    // vite.config.ts -- keeps requests same-origin, rewrite strips /api back
    // off before forwarding since server.py's own routes aren't prefixed.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:25690',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
