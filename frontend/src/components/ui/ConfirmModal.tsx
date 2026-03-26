import { cn } from '@/lib/utils'

interface ConfirmModalProps {
  title: string
  message: string
  confirmLabel?: string
  danger?: boolean
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
  children?: React.ReactNode
}

export function ConfirmModal({
  title,
  message,
  confirmLabel = '확인',
  danger = false,
  loading = false,
  onConfirm,
  onCancel,
  children,
}: ConfirmModalProps) {
  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-bold text-slate-900 mb-2">{title}</h3>
        <p className="text-sm text-slate-500 mb-4">{message}</p>
        {children}
        <div className="flex gap-2 justify-end mt-5">
          <button
            className="px-4 py-2 rounded-lg border border-slate-200 bg-white text-slate-600 text-sm font-medium hover:bg-slate-50"
            onClick={onCancel}
          >
            취소
          </button>
          <button
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium',
              danger
                ? 'bg-red-500 text-white hover:bg-red-600'
                : 'bg-blue-500 text-white hover:bg-blue-600',
              loading && 'opacity-60 cursor-not-allowed'
            )}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? '처리중…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
