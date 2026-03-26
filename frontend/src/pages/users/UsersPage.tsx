import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { FullPageSpinner } from '@/components/ui/Spinner'
import { formatDate, getErrorMessage } from '@/lib/utils'
import { toast } from '@/components/ui/Toast'
import type { User, UserRole, CreateUserRequest } from '@/types/user'

const EMPTY_FORM: CreateUserRequest = { email: '', name: '', password: '', role: 'OPERATOR' }

export default function UsersPage() {
  const [users, setUsers]           = useState<User[]>([])
  const [loading, setLoading]       = useState(true)
  const [showModal, setShowModal]   = useState(false)
  const [form, setForm]             = useState<CreateUserRequest>(EMPTY_FORM)
  const [formLoading, setFormLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const { data: resp } = await api.get('/users')
      const d = resp as { data?: User[]; items?: User[] } | User[]
      if (Array.isArray(d)) setUsers(d)
      else setUsers(d.data ?? d.items ?? [])
    } catch {
      toast('사용자 목록 로드 실패', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, []) // eslint-disable-line

  const doCreate = async () => {
    setFormLoading(true)
    try {
      await api.post('/users', form)
      toast('사용자가 생성되었습니다')
      setShowModal(false)
      setForm(EMPTY_FORM)
      load()
    } catch (err) {
      toast(getErrorMessage(err), 'error')
    } finally {
      setFormLoading(false)
    }
  }

  const FIELD_DEFS = [
    { label: '이메일',   key: 'email'    as keyof CreateUserRequest, type: 'email'    },
    { label: '이름',     key: 'name'     as keyof CreateUserRequest, type: 'text'     },
    { label: '비밀번호', key: 'password' as keyof CreateUserRequest, type: 'password' },
  ]

  return (
    <div>
      <div className="flex justify-between items-start mb-6">
        <div className="page-header mb-0">
          <h1>사용자 관리</h1>
          <p>ADMIN 전용</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          + 사용자 추가
        </button>
      </div>

      <div className="table-wrap">
        {loading ? (
          <FullPageSpinner />
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-slate-50">
                {['이름', '이메일', '역할', '활성', '마지막 로그인', '생성일'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide border-b border-slate-200">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50 border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3 font-medium text-sm">{u.name}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${u.role === 'ADMIN' ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-sm font-semibold ${u.is_active ? 'text-green-600' : 'text-red-500'}`}>
                      {u.is_active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{formatDate(u.last_login_at, true)}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{formatDate(u.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 사용자 추가 모달 */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-slate-900 mb-5">사용자 추가</h3>
            <div className="space-y-4">
              {FIELD_DEFS.map(({ label, key, type }) => (
                <div key={key}>
                  <label className="block text-sm font-semibold text-slate-700 mb-1.5">{label}</label>
                  <input
                    type={type}
                    className="input"
                    value={form[key] as string}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  />
                </div>
              ))}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">역할</label>
                <select
                  className="input"
                  value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as UserRole }))}
                >
                  <option value="OPERATOR">OPERATOR</option>
                  <option value="ADMIN">ADMIN</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2 justify-end mt-6">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>취소</button>
              <button
                className="btn btn-primary"
                onClick={doCreate}
                disabled={formLoading}
              >
                {formLoading ? '생성중…' : '생성'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
