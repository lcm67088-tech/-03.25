import type { UserRole } from './common'

export interface User {
  id: string
  email: string
  name: string
  role: UserRole
  is_active: boolean
  // /users/ 엔드포인트는 id, email, name, role, is_active만 반환
  // /auth/me는 전체 필드 반환 (last_login_at, created_at 포함 가능)
  last_login_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface LoginRequest {
  username: string  // FastAPI OAuth2PasswordRequestForm 호환
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface CreateUserRequest {
  email: string
  name: string
  password: string
  role: UserRole
}
