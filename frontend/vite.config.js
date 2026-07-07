import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: Vite serves the app on :5173 and proxies /api to the FastAPI backend
// on :8000, so the frontend can use same-origin relative URLs in both dev and
// production (where FastAPI serves the built dist/).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
