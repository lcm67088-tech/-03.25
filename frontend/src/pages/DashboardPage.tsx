import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { formatAmount } from '@/lib/utils'
import { toast } from '@/components/ui/Toast'

interface DashboardSummary {
  order_status_totals: Record<string, number>
  item_status_totals: Record<string, number>
  amount_totals: Record<string, number>
}

interface ItemsByStatus {
  by_status: Record<string, { count: number; total_amount: number }>
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [itemsByStatus, setItemsByStatus] = useState<ItemsByStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get<{ data: DashboardSummary } | DashboardSummary>('/dashboard/summary'),
      api.get<{ data: ItemsByStatus } | ItemsByStatus>('/dashboard/items-by-status'),
    ])
      .then(([s, i]) => {
        const sd = ('data' in s.data && s.data.data) ? s.data.data : s.data as DashboardSummary
        const id = ('data' in i.data && i.data.data) ? i.data.data : i.data as ItemsByStatus
        setSummary(sd)
        setItemsByStatus(id)
      })
      .catch(() => toast('대시보드 로드 실패', 'error'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <FullPageSpinner />

  const orderTotals = summary?.order_status_totals ?? {}
  const itemTotals  = summary?.item_status_totals  ?? {}
  const amounts     = summary?.amount_totals        ?? {}

  const totalOrders = Object.values(orderTotals).reduce((a, b) => a + b, 0)

  const statCards = [
    { label: '전체 주문',     value: totalOrders,                         color: 'border-blue-400' },
    { label: '진행중 아이템', value: itemTotals['in_progress'] ?? 0,      color: 'border-violet-400' },
    { label: '정산대기',      value: itemTotals['settlement_ready'] ?? 0, color: 'border-amber-400' },
    { label: '종료 아이템',   value: itemTotals['closed'] ?? 0,           color: 'border-emerald-400' },
  ]

  const amountRows = [
    { label: '진행중',          key: 'in_progress',      color: 'text-violet-600' },
    { label: '완료',            key: 'done',             color: 'text-green-600' },
    { label: '정산대기',        key: 'settlement_ready', color: 'text-amber-600' },
    { label: '종료(정산완료)', key: 'closed',           color: 'text-slate-500' },
  ]

  return (
    <div>
      <div className="page-header">
        <h1>대시보드</h1>
        <p>운영 현황 요약</p>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {statCards.map((c) => (
          <div key={c.label} className={`card border-l-4 ${c.color}`}>
            <p className="text-xs text-slate-500 mb-1">{c.label}</p>
            <p className="text-3xl font-bold text-slate-900">{c.value}</p>
          </div>
        ))}
      </div>

      {/* 금액 현황 + 상태별 집계 */}
      <div className="grid grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">💰 금액 현황</h3>
          <div className="space-y-3">
            {amountRows.map(({ label, key, color }) => (
              <div key={key} className="flex justify-between items-center">
                <span className="text-sm text-slate-500">{label}</span>
                <span className={`font-semibold text-sm ${color}`}>
                  {formatAmount(amounts[key])}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">📊 OrderItem 상태별</h3>
          <div className="space-y-2">
            {Object.entries(itemsByStatus?.by_status ?? {})
              .slice(0, 7)
              .map(([st, data]) => (
                <div key={st} className="flex justify-between items-center">
                  <StatusBadge status={st} />
                  <span className="font-semibold text-sm text-slate-700">{data.count}건</span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}
