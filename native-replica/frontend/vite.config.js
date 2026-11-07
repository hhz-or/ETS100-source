import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base: './' 让构建产物可由 WebView2 虚拟主机、http 静态服务或 file:// 直接打开
export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    port: 5173,
    strictPort: false
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    chunkSizeWarningLimit: 2200
  }
})
