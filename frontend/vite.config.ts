import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': {
    target: 'http://127.0.0.1:8765', changeOrigin: false,
    configure(proxy) {
      proxy.on('proxyReq', (proxyRequest) => {
        // Same-origin GET fetches may omit Origin; write requests retain the browser value.
        if (!proxyRequest.getHeader('origin')) proxyRequest.setHeader('Origin', 'http://localhost:5173')
      })
    },
  } } },
})
