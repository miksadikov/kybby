import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/assets': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
      '/profile/avatar': 'http://127.0.0.1:8000',
      '/projects': 'http://127.0.0.1:8000',
      '/generation-jobs': 'http://127.0.0.1:8000',
      '/generation-history': 'http://127.0.0.1:8000',
      '/logout': 'http://127.0.0.1:8000',
    },
  },
})
