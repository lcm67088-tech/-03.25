/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL (절대 URL 또는 /api/v1 상대경로) */
  readonly VITE_API_BASE_URL: string
  /** 실행 환경: development | staging | production */
  readonly VITE_APP_ENV: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
