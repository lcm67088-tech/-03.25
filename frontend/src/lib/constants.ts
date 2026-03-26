import type { OrderItemStatus, OrderStatus } from '@/types/order'
import type { PlaceReviewStatus } from '@/types/place'

export interface StatusStyle {
  bg: string
  text: string
  border: string
  label: string
}

export const ORDER_ITEM_STATUS_STYLES: Record<OrderItemStatus, StatusStyle> = {
  received:         { bg: 'bg-blue-50',   text: 'text-blue-700',   border: 'border-blue-200',   label: '접수됨' },
  on_hold:          { bg: 'bg-yellow-50', text: 'text-yellow-800', border: 'border-yellow-200', label: '보류' },
  reviewing:        { bg: 'bg-amber-50',  text: 'text-amber-800',  border: 'border-amber-200',  label: '검토중' },
  ready_to_route:   { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200', label: '라우팅대기' },
  assigned:         { bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-violet-200', label: '배정됨' },
  in_progress:      { bg: 'bg-emerald-50',text: 'text-emerald-700',border: 'border-emerald-200',label: '진행중' },
  done:             { bg: 'bg-green-50',  text: 'text-green-700',  border: 'border-green-200',  label: '완료' },
  confirmed:        { bg: 'bg-cyan-50',   text: 'text-cyan-700',   border: 'border-cyan-200',   label: '확인됨' },
  settlement_ready: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200', label: '정산대기' },
  closed:           { bg: 'bg-slate-100', text: 'text-slate-600',  border: 'border-slate-200',  label: '종료' },
  cancelled:        { bg: 'bg-red-50',    text: 'text-red-700',    border: 'border-red-200',    label: '취소' },
}

export const ORDER_STATUS_STYLES: Record<OrderStatus, StatusStyle> = {
  draft:          { bg: 'bg-slate-100', text: 'text-slate-600',  border: 'border-slate-200',  label: '초안' },
  pending_review: { bg: 'bg-yellow-50', text: 'text-yellow-800', border: 'border-yellow-200', label: '검토대기' },
  confirmed:      { bg: 'bg-cyan-50',   text: 'text-cyan-700',   border: 'border-cyan-200',   label: '확정' },
  closed:         { bg: 'bg-slate-100', text: 'text-slate-600',  border: 'border-slate-200',  label: '종료' },
  cancelled:      { bg: 'bg-red-50',    text: 'text-red-700',    border: 'border-red-200',    label: '취소' },
}

export const PLACE_REVIEW_STATUS_STYLES: Record<PlaceReviewStatus, StatusStyle> = {
  pending_review: { bg: 'bg-yellow-50', text: 'text-yellow-800', border: 'border-yellow-200', label: '검수대기' },
  confirmed:      { bg: 'bg-green-50',  text: 'text-green-700',  border: 'border-green-200',  label: '확정' },
  rejected:       { bg: 'bg-red-50',    text: 'text-red-700',    border: 'border-red-200',    label: '반려' },
}

export const IMPORT_JOB_STATUS_STYLES = {
  pending:    { bg: 'bg-yellow-50', text: 'text-yellow-800', border: 'border-yellow-200', label: '대기중' },
  processing: { bg: 'bg-blue-50',   text: 'text-blue-700',   border: 'border-blue-200',   label: '처리중' },
  done:       { bg: 'bg-green-50',  text: 'text-green-700',  border: 'border-green-200',  label: '완료' },
  failed:     { bg: 'bg-red-50',    text: 'text-red-700',    border: 'border-red-200',    label: '실패' },
} as const

// ADMIN 전용 전이 목록
export const ADMIN_ONLY_TRANSITIONS: Partial<Record<OrderItemStatus, OrderItemStatus[]>> = {
  settlement_ready: ['closed'],
}
