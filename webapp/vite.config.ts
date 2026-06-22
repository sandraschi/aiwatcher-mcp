import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    allowedHosts: ['goliath'],
    port: 10947,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:10946', changeOrigin: true },
      '/mcp': { target: 'http://127.0.0.1:10946', changeOrigin: true, ws: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
