import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Wallet from './pages/Wallet'
import Profile from './pages/Profile'
import MyBookings from './pages/MyBookings'

function PrivateRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function GuestRoute({ children }) {
  const { user } = useAuth()
  return !user ? children : <Navigate to="/dashboard" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      <Route path="/login"    element={<GuestRoute><Login /></GuestRoute>} />
      <Route path="/register" element={<GuestRoute><Register /></GuestRoute>} />

      <Route path="/dashboard"    element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/wallet"       element={<PrivateRoute><Wallet /></PrivateRoute>} />
      <Route path="/profile"      element={<PrivateRoute><Profile /></PrivateRoute>} />
      <Route path="/my-bookings"  element={<PrivateRoute><MyBookings /></PrivateRoute>} />

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
