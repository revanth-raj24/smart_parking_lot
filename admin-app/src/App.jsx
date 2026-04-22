import { Routes, Route, Navigate } from 'react-router-dom'
import { useAdminAuth } from './context/AdminAuthContext'
import AdminLogin from './pages/AdminLogin'
import AdminDashboard from './pages/AdminDashboard'

function ProtectedRoute({ children }) {
  const { admin } = useAdminAuth()
  return admin ? children : <Navigate to="/login" replace />
}

function GuestRoute({ children }) {
  const { admin } = useAdminAuth()
  return !admin ? children : <Navigate to="/dashboard" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<GuestRoute><AdminLogin /></GuestRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute><AdminDashboard /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
