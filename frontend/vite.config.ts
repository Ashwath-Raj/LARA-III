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
  const localDemo = (process.env.LARA_LOCAL_DEMO || env.LARA_LOCAL_DEMO || '0') === '1'
  if ((process.env.LARA_LOCAL_DEMO || env.LARA_LOCAL_DEMO || '0') !== '0' &&
      (process.env.LARA_LOCAL_DEMO || env.LARA_LOCAL_DEMO) !== '1') {
    throw new Error('LARA_LOCAL_DEMO must be 0 or 1.')
  }
  const publicOrigin = localDemo
    ? configuredPublicOrigin(process.env.LARA_PUBLIC_ORIGIN || env.LARA_PUBLIC_ORIGIN || 'http://127.0.0.1:5173')
    : configuredPublicOrigin(process.env.LARA_PUBLIC_ORIGIN || env.LARA_PUBLIC_ORIGIN)
  if (localDemo && (publicOrigin.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]'].includes(publicOrigin.hostname))) {
    throw new Error('LARA_LOCAL_DEMO requires a loopback HTTP frontend origin.')
  }
  const publicHost = publicOrigin.hostname.replace(/^\[|\]$/g, '')
  const server: NonNullable<UserConfig['server']> = {
    host: '127.0.0.1',
    allowedHosts: [...new Set(['localhost', '127.0.0.1', publicHost])],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        // Rewrite only the upstream Host header. Browser Origin stays intact for backend checks.
        changeOrigin: true,
        configure: (proxy) => {
          if (!localDemo) return
          proxy.on('proxyReq', (proxyRequest, request) => {
            // Browsers omit Origin for safe same-origin reads. Stamp the configured origin
            // only on GET/HEAD; mutations must carry the browser's actual Origin header.
            if ((request.method === 'GET' || request.method === 'HEAD') && !request.headers.origin) {
              proxyRequest.setHeader('Origin', publicOrigin.origin)
            }
          })
        },
      },
    },
  }
  if (publicOrigin.protocol === 'https:') {
    server.hmr = { protocol: 'wss', host: publicHost, clientPort: 443 }
  }
  return { plugins: [react()], server, define: { __LARA_LOCAL_DEMO__: JSON.stringify(localDemo) } }
})
