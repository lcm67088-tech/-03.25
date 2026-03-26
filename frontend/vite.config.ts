import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  // mode: 'development' | 'staging' | 'production'
  const env = loadEnv(mode, process.cwd(), '')

  // 로컬 개발(dev)일 때만 Vite proxy 사용
  // 스테이징·운영 빌드는 VITE_API_BASE_URL에 절대 URL이 들어오므로 proxy 불필요
  const isDev = mode === 'development'

  return {
    plugins: [react()],

    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },

    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: isDev
        ? {
            '/api': {
              target: 'http://localhost:8000',
              changeOrigin: true,
            },
          }
        : undefined,
    },

    build: {
      outDir: 'dist',
      sourcemap: false,
    },

    // `vite preview` (로컬 빌드 검증용): proxy 그대로 유지
    // 스테이징·운영은 nginx의 try_files + proxy_pass가 담당
    preview: {
      host: '0.0.0.0',
      port: 5173,
      proxy: isDev
        ? {
            '/api': {
              target: 'http://localhost:8000',
              changeOrigin: true,
            },
          }
        : undefined,
    },

    // 환경변수 타입 노출 (vite-env.d.ts 없어도 동작)
    define: {
      __APP_ENV__: JSON.stringify(env.VITE_APP_ENV ?? mode),
    },
  }
})
