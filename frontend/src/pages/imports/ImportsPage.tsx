import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Pagination } from '@/components/ui/Pagination'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { formatDate, truncateId, getErrorMessage } from '@/lib/utils'
import { toast } from '@/components/ui/Toast'
import type { ImportJob } from '@/types/place'

export default function ImportsPage() {
  const [jobs, setJobs]     = useState<ImportJob[]>([])
  const [total, setTotal]   = useState(0)
  const [page, setPage]     = useState(1)
  const [loading, setLoading] = useState(false)

  const load = async (p = page) => {
    setLoading(true)
    try {
      const { data: resp } = await api.get('/import-jobs', { params: { page: p, page_size: 20 } })
      const d = resp as { data?: ImportJob[]; items?: ImportJob[]; total?: number }
      setJobs(d.data ?? d.items ?? [])
      setTotal(d.total ?? 0)
    } catch {
      toast('ImportJob 로드 실패', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(page) }, [page]) // eslint-disable-line

  const doRetry = async (id: string) => {
    try {
      await api.post(`/import-jobs/${id}/retry`)
      toast('재시도 요청이 완료되었습니다')
      load(page)
    } catch (err) {
      toast(getErrorMessage(err), 'error')
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Import 이력</h1>
        <p>총 {total}건</p>
      </div>

      <div className="table-wrap">
        {loading ? (
          <FullPageSpinner />
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-slate-50">
                {['ID', '타입', '소스', '상태', '처리', '실패', '재시도', '생성일', ''].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide border-b border-slate-200">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-10 text-slate-400">ImportJob이 없습니다</td>
                </tr>
              ) : (
                jobs.map((j) => (
                  <tr key={j.id} className="hover:bg-slate-50 border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">{truncateId(j.id)}</td>
                    <td className="px-4 py-3 text-sm">{j.job_type}</td>
                    <td className="px-4 py-3 text-xs text-slate-500 max-w-44 truncate">
                      {j.source_url ?? j.source_file_name ?? '-'}
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={j.status} /></td>
                    <td className="px-4 py-3 text-center text-sm">
                      {j.processed_rows ?? 0}/{j.total_rows ?? 0}
                    </td>
                    <td className={`px-4 py-3 text-center text-sm ${(j.failed_rows ?? 0) > 0 ? 'text-red-600 font-semibold' : 'text-slate-400'}`}>
                      {j.failed_rows ?? 0}
                    </td>
                    <td className="px-4 py-3 text-center text-sm">{j.retry_count}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{formatDate(j.created_at, true)}</td>
                    <td className="px-4 py-3">
                      {j.status === 'failed' && (
                        <button className="btn btn-secondary btn-xs" onClick={() => doRetry(j.id)}>
                          재시도
                        </button>
                      )}
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
