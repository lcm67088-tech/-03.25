import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Pagination } from '@/components/ui/Pagination'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { toast } from '@/components/ui/Toast'
import { getErrorMessage } from '@/lib/utils'
import type { Place } from '@/types/place'

export default function PlacesPage() {
  const [places, setPlaces] = useState<Place[]>([])
  const [total, setTotal]   = useState(0)
  const [page, setPage]     = useState(1)
  const [loading, setLoading] = useState(false)
  const [reviewModal, setReviewModal] = useState<{ place: Place; action: 'confirm' | 'reject' } | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  const load = async (p = page) => {
    setLoading(true)
    try {
      const { data: resp } = await api.get<{ data: Place[]; meta: { total: number } }>('/places', { params: { page: p, page_size: 20 } })
      setPlaces(resp.data ?? [])
      setTotal(resp.meta?.total ?? 0)
    } catch {
      toast('Place 목록 로드 실패', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(page) }, [page]) // eslint-disable-line

  const doReview = async () => {
    if (!reviewModal) return
    const { place, action } = reviewModal
    try {
      if (action === 'confirm') {
        await api.post(`/places/${place.id}/review/confirm`)
        toast('Place가 승인되었습니다')
      } else {
        await api.post(`/places/${place.id}/review/reject`, { reason: rejectReason })
        toast('Place가 반려되었습니다')
      }
      setReviewModal(null)
      load(page)
    } catch (err) {
      toast(getErrorMessage(err), 'error')
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Place 검수</h1>
        <p>총 {total}건</p>
      </div>

      <div className="table-wrap">
        {loading ? (
          <FullPageSpinner />
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-slate-50">
                {['업체명', 'Naver ID', '카테고리', '주소', '검수 상태', ''].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide border-b border-slate-200">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {places.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-slate-400">Place가 없습니다</td>
                </tr>
              ) : (
                places.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50 border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3 font-medium text-sm">{p.confirmed_name ?? '-'}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.naver_place_id ?? '-'}</td>
                    <td className="px-4 py-3 text-sm">{p.confirmed_category ?? '-'}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{p.confirmed_address ?? '-'}</td>
                    <td className="px-4 py-3"><StatusBadge status={p.review_status} /></td>
                    <td className="px-4 py-3">
                      {p.review_status === 'pending_review' && (
                        <div className="flex gap-2">
                          <button
                            className="btn btn-success btn-xs"
                            onClick={() => setReviewModal({ place: p, action: 'confirm' })}
                          >
                            ✓ 승인
                          </button>
                          <button
                            className="btn btn-danger btn-xs"
                            onClick={() => { setReviewModal({ place: p, action: 'reject' }); setRejectReason('') }}
                          >
                            ✕ 반려
                          </button>
                        </div>
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

      {reviewModal && (
        <ConfirmModal
          title={reviewModal.action === 'confirm' ? 'Place 승인' : 'Place 반려'}
          message={`"${reviewModal.place.confirmed_name ?? reviewModal.place.naver_place_id}"를 ${reviewModal.action === 'confirm' ? '승인' : '반려'}하시겠습니까?`}
          confirmLabel={reviewModal.action === 'confirm' ? '승인' : '반려'}
          danger={reviewModal.action === 'reject'}
          onConfirm={doReview}
          onCancel={() => setReviewModal(null)}
        >
          {reviewModal.action === 'reject' && (
            <div className="mb-3">
              <input
                type="text"
                className="input"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="반려 사유를 입력하세요"
              />
            </div>
          )}
        </ConfirmModal>
      )}
    </div>
  )
}
