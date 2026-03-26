import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { formatDate } from '@/lib/utils'
import { toast } from '@/components/ui/Toast'
import type { OrderItemStatusHistory } from '@/types/order'

export default function OrderItemHistoryPage() {
  const { itemId } = useParams<{ itemId: string }>()
  const navigate = useNavigate()
  const [history, setHistory] = useState<OrderItemStatusHistory[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!itemId) return
    api.get(`/order-items/${itemId}/history`)
      .then((r) => {
        const d = r.data as { data: OrderItemStatusHistory[] }
        setHistory(d.data ?? [])
      })
      .catch(() => toast('이력 로드 실패', 'error'))
      .finally(() => setLoading(false))
  }, [itemId])

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button className="btn btn-secondary btn-sm" onClick={() => navigate(-1)}>
          ← 뒤로
        </button>
        <h1 className="text-xl font-bold text-slate-900">OrderItem 상태 이력</h1>
      </div>

      {loading ? (
        <FullPageSpinner />
      ) : (
        <div className="table-wrap">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-slate-50">
                {['이전 상태', '', '변경 상태', '변경자', '사유', '일시'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide border-b border-slate-200">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-slate-400">이력이 없습니다</td>
                </tr>
              ) : (
                history.map((h, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3">
                      {h.from_status
                        ? <StatusBadge status={h.from_status} />
                        : <span className="text-xs text-slate-400">(시작)</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-center">→</td>
                    <td className="px-4 py-3"><StatusBadge status={h.to_status} /></td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {h.changed_by ? h.changed_by.slice(0, 8) + '…' : '-'}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">{h.reason ?? '-'}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{formatDate(h.created_at, true)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
