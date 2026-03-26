import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

const PAGE_TITLES: Record<string, string> = {
  '/':           '대시보드',
  '/orders':     '주문 관리',
  '/places':     'Place 검수',
  '/imports':    'Import 이력',
  '/settlement': '정산 현황',
  '/users':      '사용자 관리',
}

export function AppLayout() {
  const location = useLocation()
  const basePath = '/' + (location.pathname.split('/')[1] ?? '')
  const title = PAGE_TITLES[basePath] ?? '운영 콘솔'

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar />
      <div className="ml-60 flex flex-col min-h-screen">
        <Header title={title} />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
