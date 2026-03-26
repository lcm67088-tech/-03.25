import axios from 'axios'

const TOKEN_KEY = 'placeopt_token'
const USER_KEY  = 'placeopt_user'

// 환경별 API base URL 결정:
//   - 로컬 개발(dev): '/api/v1' → Vite proxy가 localhost:8000으로 포워딩
//   - 스테이징 빌드:  'https://staging-api.papainite.co.kr/api/v1' (절대 URL)
//   - 운영 빌드:      'https://api.papainite.co.kr/api/v1' (절대 URL)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: false,  // JWT Bearer 토큰 방식 — credentials 불필요
})

// 요청 인터셉터: JWT 주입
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// 응답 인터셉터: 401 → 자동 로그아웃
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      window.dispatchEvent(new CustomEvent('auth:logout'))
    }
    return Promise.reject(error)
  }
)

export { TOKEN_KEY, USER_KEY, API_BASE_URL }
