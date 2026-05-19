import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5010,
    host: '0.0.0.0',
    allowedHosts: ['rmw01tfinner.doane.local'],
    proxy: {
      '/api': {
        target: 'http://localhost:5011',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
