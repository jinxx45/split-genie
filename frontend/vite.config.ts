import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Forward /api calls to the FastAPI dev server, so the browser sees one origin and no CORS setup is needed.
    proxy: {
      // 127.0.0.1, not localhost: Node may look up localhost as IPv6 (::1), but uvicorn listens on IPv4.
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
