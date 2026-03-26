export interface ApiResponse<T> {
  data: T
  message?: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  // 일부 엔드포인트는 items 키를 사용
  items?: T[]
}

export type UserRole = 'ADMIN' | 'OPERATOR'
