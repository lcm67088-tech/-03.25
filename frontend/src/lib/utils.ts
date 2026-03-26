import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatDate(iso: string | null | undefined, withTime = false): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '-'
  if (withTime) return d.toLocaleString('ko-KR')
  return d.toLocaleDateString('ko-KR')
}

export function formatAmount(amount: number | null | undefined): string {
  if (amount == null) return '-'
  return amount.toLocaleString('ko-KR') + '원'
}

export function truncateId(id: string | null | undefined, len = 8): string {
  if (!id) return '-'
  return id.slice(0, len) + '…'
}

/** axios 에러에서 메시지 추출 */
export function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const resp = (error as { response?: { data?: { detail?: string } } }).response
    return resp?.data?.detail ?? '알 수 없는 오류가 발생했습니다.'
  }
  return '알 수 없는 오류가 발생했습니다.'
}
