import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Pagination } from '@/components/ui/Pagination'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { formatDate, truncateId } from '@/lib/utils'
import { toast } from '@/components/ui/Toast'
import type { Order, OrderStatus } from '@/types/order'

const ORDER_STATUSES: OrderStatus[] = ['draft', 'pending_review', 'confirmed', 'closed', 'cancelled']
const SOURCE_TYPES = ['web_portal', 'google_sheet_import', 'excel_upload']

interface Filters {
  status: string
  source_type: string
}

export default function OrdersPage() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal]   = useState(0)
  const [page, setPage]     = useState(1)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<Filters>({ status: '', source_type: '' })

  const fetchOrders = useCallback(async (p: number, f: Filters) => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { page: p, page_size: 20 }
      if (f.status)      params.status      = f.status
      if (f.source_type) params.source_type = f.source_type

      const { data: resp } = await api.get<{ data: Order[]; meta: { total: number } }>('/orders', { params })
      setOrders(resp.data ?? [])
      setTotal(resp.meta?.total ?? 0)
    } catch {
      toast('주문 목록 로드 실패', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchOrders(page, filters) }, [page]) // eslint-disable-line

  const handleSearch = () => { setPage(1); fetchOrders(1, filters) }

  return (
    <div>
      <div className="page-header">
        <h1>주문 관리</h1>
        <p>총 {total}건의 주문</p>
      </div>

      {/* 필터 */}
      <div className="card mb-4 py-4">
        <div className="flex gap-3 items-end flex-wrap">
          <div className="min-w-40">
            <label className="block text-xs font-semibold text-slate-500 mb-1">상태</label>
            <select
              className="input"
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
            >
              <option value="">전체</option>
              {ORDER_STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="min-w-40">
            <label className="block text-xs font-semibold text-slate-500 mb-1">소스 타입</label>
            <select
              className="input"
              value={filters.source_type}
              onChange={(e) => setFilters((f) => ({ ...f, source_type: e.target.value }))}
            >
              <option value="">전체</option>
              {SOURCE_TYPES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary btn-sm" onClick={handleSearch}>
            🔍 검색
          </button>
        </div>
      </div>

      {/* 테이블 */}
      <div className="table-wrap">
        {loading ? (
          <FullPageSpinner />
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-slate-50">
                {['주문 ID', '대행사', '영업담당', '소스', '상태', '아이템', '생성일', ''].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide border-b border-slate-200">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-slate-400">
                    주문이 없습니다
                  </td>
                </tr>
              ) : (
                orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50 border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">{truncateId(o.id)}</td>
                    <td className="px-4 py-3 text-sm">{o.agency_name_snapshot ?? <span className="text-slate-400">미지정</span>}</td>
                    <td className="px-4 py-3 text-sm">{o.sales_rep_name ?? '-'}</td>
                    <td className="px-4 py-3">
                      <span className="bg-indigo-50 text-indigo-700 rounded px-1.5 py-0.5 text-xs font-semibold">
                        {o.source_type}
                      </span>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                    <td className="px-4 py-3 text-center font-semibold text-sm">{o.item_count ?? '-'}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{formatDate(o.created_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        className="btn btn-secondary btn-xs"
                        onClick={() => navigate(`/orders/${o.id}`)}
                      >
                        상세 →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
      <Pagination page={page} total={total} pageSize={20} onPage={setPage} />
    </div>
  )
}
