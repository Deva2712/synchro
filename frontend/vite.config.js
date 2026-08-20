import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The console talks to the API through a dev proxy, so the browser only ever
// sees one origin and no API URL is baked into the bundle.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/v1': { target: process.env.API_URL || 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
