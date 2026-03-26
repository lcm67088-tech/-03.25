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
    // PlaceOpt 백엔드: JSON body { email, password }
    const { data: tokenData } = await api.post<{ access_token: string }>(
      '/login',
      { email, password }
    )
    localStorage.setItem(TOKEN_KEY, tokenData.access_token)

    const { data: meResp } = await api.get<User>('/me')
    localStorage.setItem(USER_KEY, JSON.stringify(meResp))
    set({ user: meResp })
    return meResp
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
