import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { formatAmount } from '@/lib/utils'
import { toast } from '@/components/ui/Toast'

// 실제 백엔드 응답 구조 (GET /api/v1/dashboard/summary)
interface SummaryData {
  orders: {
    total: number
    draft: number
    confirmed: number
    cancelled: number
    closed: number
  }
  order_items: {
    total: number
    received: number
    on_hold: number
    reviewing: number
    ready_to_route: number
    assigned: number
    in_progress: number
    done: number
    confirmed: number
    settlement_ready: number
    closed: number
    cancelled: number
  }
  amounts: {
    in_progress: number
    done: number
    settlement_ready: number
    closed: number
    total_contracted: number
  }
  place: {
    total: number
    pending_review: number
    in_review: number
    confirmed: number
    rejected: number
  }
}

// 실제 백엔드 응답 구조 (GET /api/v1/dashboard/items-by-status)
interface ItemsByStatusRow {
  status: string
  count: number
  total_amount: number
  avg_unit_price: number
}
interface ItemsByStatusData {
  source_type_filter: string | null
  statuses: ItemsByStatusRow[]
}

export default function DashboardPage() {
  const [summary, setSummary]         = useState<SummaryData | null>(null)
  const [itemsByStatus, setItemsByStatus] = useState<ItemsByStatusRow[]>([])
  const [loading, setLoading]         = useState(true)

  useEffect(() => {
    Promise.all([
      api.get<{ data: SummaryData }>('/dashboard/summary'),
      api.get<{ data: ItemsByStatusData }>('/dashboard/items-by-status'),
    ])
      .then(([s, i]) => {
        setSummary(s.data.data)
        setItemsByStatus(i.data.data?.statuses ?? [])
      })
      .catch(() => toast('대시보드 로드 실패', 'error'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <FullPageSpinner />

  const orders    = summary?.orders
  const items     = summary?.order_items
  const amounts   = summary?.amounts

  const statCards = [
    { label: '전체 주문',     value: orders?.total   ?? 0, color: 'border-blue-400' },
    { label: '진행중 아이템', value: items?.in_progress ?? 0, color: 'border-violet-400' },
    { label: '정산대기',      value: items?.settlement_ready ?? 0, color: 'border-amber-400' },
    { label: '종료 아이템',   value: items?.closed   ?? 0, color: 'border-emerald-400' },
  ]

  const amountRows = [
    { label: '진행중',           key: 'in_progress'      as const, color: 'text-violet-600' },
    { label: '완료',             key: 'done'              as const, color: 'text-green-600' },
    { label: '정산대기',         key: 'settlement_ready'  as const, color: 'text-amber-600' },
    { label: '종료(정산완료)',   key: 'closed'            as const, color: 'text-slate-500' },
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
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">💰 금액 현황</h3>
          <div className="space-y-3">
            {amountRows.map(({ label, key, color }) => (
              <div key={key} className="flex justify-between items-center">
                <span className="text-sm text-slate-500">{label}</span>
                <span className={`font-semibold text-sm ${color}`}>
                  {formatAmount(amounts?.[key] ?? 0)}
                </span>
              </div>
            ))}
            <div className="border-t border-slate-100 pt-3 flex justify-between items-center">
              <span className="text-sm font-semibold text-slate-700">총 계약액</span>
              <span className="font-bold text-sm text-slate-900">
                {formatAmount(amounts?.total_contracted ?? 0)}
              </span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">📊 OrderItem 상태별</h3>
          <div className="space-y-2">
            {itemsByStatus.slice(0, 8).map((row) => (
              <div key={row.status} className="flex justify-between items-center">
                <StatusBadge status={row.status} />
                <div className="text-right">
                  <span className="font-semibold text-sm text-slate-700">{row.count}건</span>
                  {row.total_amount > 0 && (
                    <span className="text-xs text-slate-400 ml-2">
                      {formatAmount(row.total_amount)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 주문 상태별 요약 */}
      <div className="card">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">📋 주문 상태별</h3>
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: '초안',   key: 'draft',    color: 'bg-slate-100 text-slate-600' },
            { label: '확정',   key: 'confirmed', color: 'bg-cyan-50 text-cyan-700' },
            { label: '종료',   key: 'closed',   color: 'bg-emerald-50 text-emerald-700' },
            { label: '취소',   key: 'cancelled', color: 'bg-red-50 text-red-600' },
            { label: '전체',   key: 'total',    color: 'bg-blue-50 text-blue-700' },
          ].map(({ label, key, color }) => (
            <div key={key} className={`rounded-lg p-3 text-center ${color}`}>
              <p className="text-xs mb-1">{label}</p>
              <p className="text-xl font-bold">
                {orders?.[key as keyof typeof orders] ?? 0}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
