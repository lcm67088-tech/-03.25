import { cn } from '@/lib/utils'
import {
  ORDER_ITEM_STATUS_STYLES,
  ORDER_STATUS_STYLES,
  PLACE_REVIEW_STATUS_STYLES,
  IMPORT_JOB_STATUS_STYLES,
} from '@/lib/constants'
import type { OrderItemStatus, OrderStatus } from '@/types/order'
import type { PlaceReviewStatus } from '@/types/place'

type AllStatus = OrderItemStatus | OrderStatus | PlaceReviewStatus | keyof typeof IMPORT_JOB_STATUS_STYLES

function getStyle(status: string) {
  return (
    ORDER_ITEM_STATUS_STYLES[status as OrderItemStatus] ??
    ORDER_STATUS_STYLES[status as OrderStatus] ??
    PLACE_REVIEW_STATUS_STYLES[status as PlaceReviewStatus] ??
    IMPORT_JOB_STATUS_STYLES[status as keyof typeof IMPORT_JOB_STATUS_STYLES] ??
    { bg: 'bg-slate-100', text: 'text-slate-600', border: 'border-slate-200', label: status }
  )
}

interface StatusBadgeProps {
  status: AllStatus | string
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const s = getStyle(status)
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border',
        s.bg, s.text, s.border,
        className
      )}
    >
      {s.label}
    </span>
  )
}
