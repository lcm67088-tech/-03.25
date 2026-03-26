import { create } from 'zustand'
import { api, TOKEN_KEY, USER_KEY } from '@/lib/api'
import type { User } from '@/types/user'

interface AuthState {
  user: User | null
  login: (email: string, password: string) => Promise<User>
  logout: () => void
  setUser: (user: User | null) => void
}

function loadUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  user: loadUser(),

  login: async (email, password) => {
    // FastAPI OAuth2PasswordRequestForm: application/x-www-form-urlencoded
    const formData = new URLSearchParams({ username: email, password })
    const { data: tokenData } = await api.post<{ access_token: string }>(
      '/auth/login',
      formData,
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    )
    localStorage.setItem(TOKEN_KEY, tokenData.access_token)

    const { data: meResp } = await api.get<{ data: User } | User>('/auth/me')
    const user = ('data' in meResp && meResp.data) ? meResp.data as User : meResp as User
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    set({ user })
    return user
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    set({ user: null })
  },

  setUser: (user) => set({ user }),
}))

// 전역 401 이벤트 수신 → 자동 로그아웃
window.addEventListener('auth:logout', () => {
  useAuthStore.getState().setUser(null)
})
