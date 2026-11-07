import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  // Relative asset paths so the same build works at / (FastAPI) and /BettorsOracle/ (GitHub Pages).
  base: './',
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
