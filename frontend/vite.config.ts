import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `vite preview` (used by vite-mode-run.sh's production mode) does not inherit `server`
// by default -- it falls back to Vite's own default port (4173) and no proxy unless a
// `preview` block is given explicitly. Share one config object so dev and production
// mode serve on the same host/port/proxy.
const serverConfig = {
  host: '127.0.0.1',
  port: 25691,
  strictPort: true,
  // Proxy every backend call under one /api prefix, same shape as synth's
  // vite.config.ts -- keeps requests same-origin, rewrite strips /api back
  // off before forwarding since server.py's own routes aren't prefixed.
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:25690',
      rewrite: (path: string) => path.replace(/^\/api/, ''),
    },
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: serverConfig,
  preview: serverConfig,
})
