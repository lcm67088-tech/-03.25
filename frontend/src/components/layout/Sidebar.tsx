import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'

interface NavItem {
  to: string
  icon: string
  label: string
  adminOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/',           icon: '📊', label: '대시보드' },
  { to: '/orders',     icon: '📋', label: '주문 관리' },
  { to: '/places',     icon: '📍', label: 'Place 검수' },
  { to: '/imports',    icon: '📥', label: 'Import 이력' },
  { to: '/settlement', icon: '💰', label: '정산 현황',   adminOnly: true },
  { to: '/users',      icon: '👥', label: '사용자 관리', adminOnly: true },
]

export function Sidebar() {
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'ADMIN'

  return (
    <aside className="fixed top-0 left-0 w-60 min-h-screen bg-slate-800 flex flex-col z-10">
      {/* 로고 */}
      <div className="px-4 py-5 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-blue-500 rounded-lg flex items-center justify-center">
            <span className="text-white font-extrabold text-lg">P</span>
          </div>
          <div>
            <p className="text-slate-100 font-bold text-sm leading-tight">PlaceOpt</p>
            <p className="text-slate-400 text-xs">운영 콘솔</p>
          </div>
        </div>
      </div>

      {/* 네비게이션 */}
      <nav className="flex-1 py-3">
        {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 mx-2 px-4 py-2.5 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-blue-500 text-white'
                  : 'text-slate-400 hover:bg-slate-700 hover:text-slate-100'
              )
            }
          >
            <span className="text-base">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* 유저 정보 */}
      <div className="px-4 py-4 border-t border-slate-700">
        <p className="text-xs text-slate-500 mb-1">
          {isAdmin ? '🔴 ADMIN' : '🟢 OPERATOR'}
        </p>
        <p className="text-sm text-slate-300 truncate">{user?.email}</p>
      </div>
    </aside>
  )
}
