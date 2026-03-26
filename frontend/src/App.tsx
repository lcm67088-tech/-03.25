import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { AppLayout } from '@/components/layout/AppLayout'
import { ToastContainer } from '@/components/ui/Toast'

// Pages (lazy는 추후 적용 가능)
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import OrdersPage from '@/pages/orders/OrdersPage'
import OrderDetailPage from '@/pages/orders/OrderDetailPage'
import OrderItemHistoryPage from '@/pages/orders/OrderItemHistoryPage'
import PlacesPage from '@/pages/places/PlacesPage'
import ImportsPage from '@/pages/imports/ImportsPage'
import SettlementPage from '@/pages/settlement/SettlementPage'
import UsersPage from '@/pages/users/UsersPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (user?.role !== 'ADMIN') {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-red-700 font-medium">
          ⛔ ADMIN 권한이 필요합니다.
        </div>
      </div>
    )
  }
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 공개 */}
        <Route path="/login" element={<LoginPage />} />

        {/* 인증 필요 */}
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="orders/:orderId" element={<OrderDetailPage />} />
          <Route path="order-items/:itemId/history" element={<OrderItemHistoryPage />} />
          <Route path="places" element={<PlacesPage />} />
          <Route path="imports" element={<ImportsPage />} />
          <Route
            path="settlement"
            element={
              <RequireAdmin>
                <SettlementPage />
              </RequireAdmin>
            }
          />
          <Route
            path="users"
            element={
              <RequireAdmin>
                <UsersPage />
              </RequireAdmin>
            }
          />
        </Route>

        {/* fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ToastContainer />
    </BrowserRouter>
  )
}
