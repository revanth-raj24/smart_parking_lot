import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { login } from '../api/auth'
import toast from 'react-hot-toast'
import { ParkingCircle, LogIn } from 'lucide-react'

export default function Login() {
  const { saveAuth } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await login(form)
      saveAuth(data.access_token, data.user)
      toast.success(`Welcome back, ${data.user.name}!`)
      navigate(data.user.is_admin ? '/admin' : '/dashboard', { replace: true })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <ParkingCircle className="text-green-400" size={40} />
            <span className="text-3xl font-bold text-white">SmartPark</span>
          </div>
          <p className="text-gray-400">IoT-Powered Parking Management</p>
        </div>

        <div className="card">
          <h2 className="text-xl font-semibold mb-6 text-gray-100">Sign In</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Email</label>
              <input
                type="email"
                className="input"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Password</label>
              <input
                type="password"
                className="input"
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
            </div>
            <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" disabled={loading}>
              <LogIn size={16} />
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
          <p className="mt-4 text-center text-sm text-gray-400">
            No account?{' '}
            <Link to="/register" className="text-green-400 hover:underline">Register here</Link>
          </p>
        </div>

        <p className="text-center text-xs text-gray-600 mt-4">
          Admin: admin@smartpark.com / admin123
        </p>
      </div>
    </div>
  )
}
