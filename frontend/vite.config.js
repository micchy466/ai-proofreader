import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,   // 0.0.0.0 にバインドし、Dockerホストからアクセス可能にする
    port: 5173,
    watch: {
      // Docker の volume マウントはネイティブの inotify が効かないことがあるためポーリング
      usePolling: true,
    },
  },
})
