import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type UserConfig } from 'vite'

function configuredPublicOrigin(raw: string | undefined): URL {
  const value = raw || 'http://localhost:5173'
  let url: URL
  try { url = new URL(value) } catch { throw new Error('LARA_PUBLIC_ORIGIN must be an absolute browser origin.') }
  if (url.username || url.password || url.pathname !== '/' || url.search || url.hash || url.origin !== value) {
    throw new Error('LARA_PUBLIC_ORIGIN must be a canonical origin without credentials, path, query, or fragment.')
  }
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) {
    throw new Error('LARA_PUBLIC_ORIGIN must use HTTPS except for a loopback development origin.')
  }
  if (url.protocol === 'http:' && !url.port) throw new Error('A loopback LARA_PUBLIC_ORIGIN must include its port.')
  return url
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const publicOrigin = configuredPublicOrigin(process.env.LARA_PUBLIC_ORIGIN || env.LARA_PUBLIC_ORIGIN)
  const publicHost = publicOrigin.hostname.replace(/^\[|\]$/g, '')
  const server: NonNullable<UserConfig['server']> = {
    host: '127.0.0.1',
    allowedHosts: [...new Set(['localhost', '127.0.0.1', publicHost])],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        // Rewrite only the upstream Host header. Browser Origin stays intact for backend checks.
        changeOrigin: true,
      },
    },
  }
  if (publicOrigin.protocol === 'https:') {
    server.hmr = { protocol: 'wss', host: publicHost, clientPort: 443 }
  }
  return { plugins: [react()], server }
})
