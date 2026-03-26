import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { getErrorMessage } from '@/lib/utils'
import { Spinner } from '@/components/ui/Spinner'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-96">
        {/* 로고 */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-blue-500 rounded-2xl inline-flex items-center justify-center mb-4">
            <span className="text-white text-3xl font-extrabold">P</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">PlaceOpt</h1>
          <p className="text-sm text-slate-500 mt-1">내부 운영 콘솔</p>
        </div>

        {/* 폼 */}
        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                이메일
              </label>
              <input
                type="email"
                className="input"
                placeholder="admin@placeopt.internal"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                비밀번호
              </label>
              <input
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2.5 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary w-full justify-center py-2.5 text-base mt-2"
              disabled={loading}
            >
              {loading ? <Spinner size="sm" /> : '로그인'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
