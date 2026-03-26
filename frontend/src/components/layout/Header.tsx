import { useAuthStore } from '@/stores/authStore'

interface HeaderProps {
  title: string
}

export function Header({ title }: HeaderProps) {
  const logout = useAuthStore((s) => s.logout)

  return (
    <header className="sticky top-0 z-10 h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <button
        onClick={logout}
        className="text-sm px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
      >
        로그아웃
      </button>
    </header>
  )
}
