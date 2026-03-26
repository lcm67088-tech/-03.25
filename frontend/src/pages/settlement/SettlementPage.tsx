import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { formatAmount } from '@/lib/utils'
import { toast } from '@/components/ui/Toast'

interface PipelineItem {
  count: number
  total_amount: number
}

interface PendingAdminApproval {
  count: number
  total_amount: number
  description: string
}

interface ClosedByAgency {
  agency_name: string | null  // 백엔드 실제 필드명
  agency_id: string | null
  closed_count: number
  total_amount: number
}

interface TotalClosed {
  count: number
  total_amount: number
}

interface SettlementData {
  filter?: Record<string, unknown>
  pipeline?: Record<string, PipelineItem>
  pending_admin_approval?: PendingAdminApproval
  total_closed?: TotalClosed
  closed_by_agency?: ClosedByAgency[]
}

const PIPELINE_STAGES = [
  { key: 'done',             label: '완료(done)',      color: 'border-emerald-400' },
  { key: 'confirmed',        label: '확인됨',           color: 'border-cyan-400' },
  { key: 'settlement_ready', label: '정산대기',         color: 'border-amber-400' },
  { key: 'closed',           label: '종료(정산완료)',  color: 'border-slate-400' },
]

export default function SettlementPage() {
  const [data, setData]       = useState<SettlementData | null>(null)
  const [loading, setLoading] = useState(true)
  const [closedFrom, setClosedFrom] = useState('')
  const [closedTo,   setClosedTo]   = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (closedFrom) params.closed_from = closedFrom
      if (closedTo)   params.closed_to   = closedTo
      const { data: resp } = await api.get<{ data: SettlementData }>('/dashboard/settlement', { params })
      setData(resp.data ?? null)
    } catch {
      toast('정산 데이터 로드 실패', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, []) // eslint-disable-line

  return (
    <div>
      <div className="page-header">
        <h1>정산 현황</h1>
        <p>정산 집계 (ADMIN 전용)</p>
      </div>

      {/* 기간 필터 */}
      <div className="card mb-5 py-4">
        <div className="flex gap-3 items-end">
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">종료일 시작</label>
            <input
              type="date"
              className="input w-40"
              value={closedFrom}
              onChange={(e) => setClosedFrom(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">종료일 끝</label>
            <input
              type="date"
              className="input w-40"
              value={closedTo}
              onChange={(e) => setClosedTo(e.target.value)}
            />
          </div>
          <button className="btn btn-primary btn-sm" onClick={load}>조회</button>
        </div>
      </div>

      {loading ? (
        <FullPageSpinner />
      ) : data && (
        <>
          {/* 파이프라인 카드 */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            {PIPELINE_STAGES.map(({ key, label, color }) => {
              const s = data.pipeline?.[key] ?? { count: 0, total_amount: 0 }
              return (
                <div key={key} className={`card border-l-4 ${color}`}>
                  <p className="text-xs text-slate-500 mb-1">{label}</p>
                  <p className="text-2xl font-bold text-slate-900">{s.count}</p>
                  <p className="text-sm font-semibold text-slate-600 mt-1">{formatAmount(s.total_amount)}</p>
                </div>
              )
            })}
          </div>

          {/* ADMIN 승인 대기 배너 */}
          {data.pending_admin_approval && data.pending_admin_approval.count > 0 && (
            <div className="card mb-6 border border-amber-300 bg-amber-50">
              <div className="flex items-start gap-3">
                <span className="text-xl">⚠️</span>
                <div>
                  <p className="text-sm font-bold text-amber-800">
                    ADMIN 최종 승인 대기: {data.pending_admin_approval.count}건
                    ({formatAmount(data.pending_admin_approval.total_amount)})
                  </p>
                  <p className="text-xs text-amber-600 mt-0.5">
                    {data.pending_admin_approval.description}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* 전체 종료 요약 */}
          {data.total_closed && (
            <div className="card mb-6 border-l-4 border-green-500">
              <p className="text-xs text-slate-500 mb-1">전체 종료 (정산완료)</p>
              <p className="text-2xl font-bold text-slate-900">{data.total_closed.count}건</p>
              <p className="text-sm font-semibold text-green-700 mt-1">
                {formatAmount(data.total_closed.total_amount)}
              </p>
            </div>
          )}

          {/* 대행사별 정산 현황 */}
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-700 mb-4">
              대행사별 정산 현황 (종료 기준)
            </h3>
            <div className="table-wrap border-0">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-slate-50">
                    {['대행사', '종료 건수', '총 금액'].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide border-b border-slate-200">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(data.closed_by_agency ?? []).length > 0 ? (
                    (data.closed_by_agency ?? []).map((row, i) => (
                      <tr key={i} className="hover:bg-slate-50 border-b border-slate-100 last:border-0">
                        <td className="px-4 py-3 font-medium text-sm">{row.agency_name ?? '(미지정)'}</td>
                        <td className="px-4 py-3 text-center font-semibold text-sm">{row.closed_count}</td>
                        <td className="px-4 py-3 font-semibold text-sm text-green-700">{formatAmount(row.total_amount)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={3} className="text-center py-8 text-slate-400">데이터 없음</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
