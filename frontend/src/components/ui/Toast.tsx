/**
 * 최소 Toast 구현 (외부 라이브러리 없이)
 * useToast() 훅 + ToastContainer 컴포넌트
 */
import { useState, useCallback, useEffect } from 'react'
import { cn } from '@/lib/utils'

export type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  message: string
  type: ToastType
}

let _addToast: ((msg: string, type?: ToastType) => void) | null = null
let _counter = 0

/** 어디서든 호출 가능한 전역 toast 함수 */
export function toast(message: string, type: ToastType = 'success') {
  _addToast?.(message, type)
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const addToast = useCallback((message: string, type: ToastType = 'success') => {
    const id = ++_counter
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3000)
  }, [])

  useEffect(() => {
    _addToast = addToast
    return () => { _addToast = null }
  }, [addToast])

  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'px-4 py-3 rounded-lg text-white text-sm font-medium shadow-lg animate-in slide-in-from-bottom-2',
            t.type === 'success' && 'bg-green-600',
            t.type === 'error'   && 'bg-red-600',
            t.type === 'info'    && 'bg-slate-700'
          )}
        >
          {t.message}
        </div>
      ))}
    </div>
  )
}
