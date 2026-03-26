import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { toast } from '@/components/ui/Toast'
import { formatDate, formatAmount, truncateId, getErrorMessage } from '@/lib/utils'
import { ORDER_ITEM_STATUS_STYLES, ADMIN_ONLY_TRANSITIONS } from '@/lib/constants'
import type { Order, OrderItem, OrderItemStatus } from '@/types/order'

export default function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'ADMIN'

  const [order, setOrder] = useState<Order | null>(null)
  const [items, setItems] = useState<OrderItem[]>([])
  const [loading, setLoading] = useState(true)

  // 상태 전이 modal
  const [transModal, setTransModal] = useState<{ item: OrderItem; toStatus: OrderItemStatus } | null>(null)
  const [transReason, setTransReason] = useState('')
  const [transLoading, setTransLoading] = useState(false)

  // 정산 메모 modal
  const [settlementModal, setSettlementModal] = useState<OrderItem | null>(null)
  const [settlementNote, setSettlementNote] = useState('')

  const load = useCallback(async () => {
    if (!orderId) return
    setLoading(true)
    try {
      const [oRes, iRes] = await Promise.all([
        api.get(`/orders/${orderId}`),
        api.get('/order-items', { params: { order_id: orderId, page_size: 100 } }),
      ])
      const od = oRes.data as { data?: Order } | Order
      const id = iRes.data as { data?: OrderItem[]; items?: OrderItem[] }
      setOrder(('data' in od && od.data) ? od.data : od as Order)
      setItems(id.data ?? id.items ?? [])
    } catch {
      toast('주문 로드 실패', 'error')
    } finally {
      setLoading(false)
    }
  }, [orderId])

  useEffect(() => { load() }, [load])

  const doTransition = async () => {
    if (!transModal) return
    setTransLoading(true)
    try {
      await api.post(`/order-items/${transModal.item.id}/status`, {
        to_status: transModal.toStatus,
        reason: transReason || undefined,
      })
      const label = ORDER_ITEM_STATUS_STYLES[transModal.toStatus]?.label ?? transModal.toStatus
      toast(`"${label}"로 상태가 변경되었습니다`)
      setTransModal(null)
      setTransReason('')
      await load()
    } catch (err) {
      toast(getErrorMessage(err), 'error')
    } finally {
      setTransLoading(false)
    }
  }

  const doSettlementNote = async () => {
    if (!settlementModal) return
    try {
      await api.patch(`/order-items/${settlementModal.id}/settlement`, {
        settlement_note: settlementNote,
      })
      toast('정산 메모가 저장되었습니다')
      setSettlementModal(null)
      await load()
    } catch (err) {
      toast(getErrorMessage(err), 'error')
    }
  }

  if (loading) return <FullPageSpinner />
  if (!order)  return <div className="p-6 text-red-600">주문을 찾을 수 없습니다</div>

  const infoRows = [
    { label: '상태',          value: <StatusBadge status={order.status} /> },
    { label: '대행사',        value: order.agency_name_snapshot ?? '미지정' },
    { label: '영업담당',      value: order.sales_rep_name ?? '-' },
    { label: '견적담당',      value: order.estimator_name ?? '-' },
    { label: '소스 타입',     value: order.source_type },
    { label: '주문 그룹키',   value: order.order_group_key ?? '-' },
    { label: 'OrderItem 수',  value: `${items.length}건` },
    { label: '생성일',        value: formatDate(order.created_at, true) },
  ]

  return (
    <div>
      {/* 헤더 */}
      <div className="flex items-center gap-3 mb-6">
        <button className="btn btn-secondary btn-sm" onClick={() => navigate('/orders')}>
          ← 목록
        </button>
        <div>
          <h1 className="text-xl font-bold text-slate-900">주문 상세</h1>
          <p className="font-mono text-xs text-slate-400 mt-0.5">{orderId}</p>
        </div>
      </div>

      {/* 주문 정보 */}
      <div className="card mb-5">
        <div className="grid grid-cols-4 gap-4">
          {infoRows.map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs text-slate-400 font-semibold uppercase tracking-wide mb-1">{label}</p>
              <div className="text-sm text-slate-800 font-medium">{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* OrderItem 목록 */}
      <h2 className="text-base font-bold text-slate-800 mb-3">
        OrderItem 목록 ({items.length}건)
      </h2>
      <div className="table-wrap">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-slate-50">
              {['상품코드', '플레이스', '키워드', '기간', '수량', '금액', '상태', '전이 가능', '정산메모', '이력'].map((h) => (
                <th key={h} className="px-3 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide border-b border-slate-200">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center py-10 text-slate-400">
                  OrderItem이 없습니다
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr
                  key={item.id}
                  className={`hover:bg-slate-50 border-b border-slate-100 last:border-0 ${item.is_deleted ? 'opacity-40' : ''}`}
                >
                  <td className="px-3 py-3">
                    <span className="bg-indigo-50 text-indigo-700 rounded px-1.5 py-0.5 text-xs font-semibold">
                      {item.product_type_code ?? '-'}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <p className="text-sm font-medium">{item.place_name_snapshot ?? '-'}</p>
                    {item.naver_place_id_snapshot && (
                      <p className="text-xs text-slate-400">{item.naver_place_id_snapshot}</p>
                    )}
                  </td>
                  <td className="px-3 py-3 text-sm">{item.main_keyword ?? '-'}</td>
                  <td className="px-3 py-3 text-xs text-slate-500">
                    {item.start_date ? `${item.start_date} ~ ${item.end_date ?? ''}` : '-'}
                  </td>
                  <td className="px-3 py-3 text-center text-sm">{item.total_qty ?? '-'}</td>
                  <td className="px-3 py-3 text-sm font-semibold">{formatAmount(item.total_amount)}</td>
                  <td className="px-3 py-3"><StatusBadge status={item.status} /></td>

                  {/* 전이 버튼 */}
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(item.available_transitions ?? []).length === 0 ? (
                        <span className="text-xs text-slate-400">없음</span>
                      ) : (
                        (item.available_transitions ?? []).map((to) => {
                          const adminOnlyList = ADMIN_ONLY_TRANSITIONS[item.status] ?? []
                          const adminOnly = adminOnlyList.includes(to)
                          const disabled = adminOnly && !isAdmin
                          const s = ORDER_ITEM_STATUS_STYLES[to]
                          return (
                            <button
                              key={to}
                              className={`btn btn-xs ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                              style={disabled ? undefined : { background: s?.bg.replace('bg-', ''), color: s?.text.replace('text-', '') }}
                              disabled={disabled}
                              title={disabled ? 'ADMIN 전용 전이' : `→ ${s?.label ?? to}`}
                              onClick={() => {
                                setTransModal({ item, toStatus: to })
                                setTransReason('')
                              }}
                            >
                              → {s?.label ?? to}{adminOnly ? ' 🔒' : ''}
                            </button>
                          )
                        })
                      )}
                    </div>
                  </td>

                  {/* 정산 메모 */}
                  <td className="px-3 py-3">
                    {['settlement_ready', 'closed'].includes(item.status) ? (
                      <button
                        className="btn btn-secondary btn-xs"
                        onClick={() => {
                          setSettlementModal(item)
                          setSettlementNote(item.settlement_note ?? '')
                        }}
                      >
                        {item.settlement_note ? '✏️ 수정' : '+ 메모'}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-400 truncate max-w-24 block">
                        {item.settlement_note ?? '-'}
                      </span>
                    )}
                  </td>

                  {/* 이력 */}
                  <td className="px-3 py-3">
                    <button
                      className="btn btn-secondary btn-xs"
                      onClick={() => navigate(`/order-items/${item.id}/history`)}
                    >
                      이력
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 상태 전이 모달 */}
      {transModal && (
        <ConfirmModal
          title="상태 전이 확인"
          message={`"${ORDER_ITEM_STATUS_STYLES[transModal.item.status]?.label}" → "${ORDER_ITEM_STATUS_STYLES[transModal.toStatus]?.label}"로 변경하시겠습니까?`}
          confirmLabel="변경"
          loading={transLoading}
          onConfirm={doTransition}
          onCancel={() => setTransModal(null)}
        >
          <div className="mb-3">
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">사유 (선택)</label>
            <input
              type="text"
              className="input"
              value={transReason}
              onChange={(e) => setTransReason(e.target.value)}
              placeholder="상태 변경 사유를 입력하세요"
            />
          </div>
        </ConfirmModal>
      )}

      {/* 정산 메모 모달 */}
      {settlementModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setSettlementModal(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-slate-900 mb-2">정산 메모 수정</h3>
            <p className="text-sm text-slate-500 mb-4">
              현재 상태: <StatusBadge status={settlementModal.status} />
            </p>
            <textarea
              className="input resize-none"
              rows={4}
              value={settlementNote}
              onChange={(e) => setSettlementNote(e.target.value)}
              placeholder="정산 관련 메모를 입력하세요"
            />
            <div className="flex gap-2 justify-end mt-4">
              <button className="btn btn-secondary" onClick={() => setSettlementModal(null)}>취소</button>
              <button className="btn btn-primary" onClick={doSettlementNote}>저장</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
