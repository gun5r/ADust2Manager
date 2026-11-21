import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// Built output is served by FastAPI at / (assets under /app/assets); in dev, /api and /ws go to the Python server.
export default defineConfig({
  base: '/app/',
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8082',
      '/static': 'http://127.0.0.1:8082',
      '/ws': { target: 'ws://127.0.0.1:8082', ws: true },
    },
  },
  test: { environment: 'node' },
})
