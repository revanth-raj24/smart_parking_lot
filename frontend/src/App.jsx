import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Wallet from './pages/Wallet'
import Profile from './pages/Profile'
import AdminDashboard from './pages/AdminDashboard'

function PrivateRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function AdminRoute({ children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_admin) return <Navigate to="/dashboard" replace />
  return children
}

function GuestRoute({ children }) {
  const { user } = useAuth()
  return !user ? children : <Navigate to={user.is_admin ? '/admin' : '/dashboard'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      <Route path="/login"    element={<GuestRoute><Login /></GuestRoute>} />
      <Route path="/register" element={<GuestRoute><Register /></GuestRoute>} />

      <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/wallet"    element={<PrivateRoute><Wallet /></PrivateRoute>} />
      <Route path="/profile"   element={<PrivateRoute><Profile /></PrivateRoute>} />

      <Route path="/admin"     element={<AdminRoute><AdminDashboard /></AdminRoute>} />

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
