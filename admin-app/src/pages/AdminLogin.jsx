import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAdminAuth } from '../context/AdminAuthContext'
import { adminLogin } from '../api/admin'
import toast from 'react-hot-toast'
import { Shield, LogIn, AlertTriangle } from 'lucide-react'

export default function AdminLogin() {
  const { saveAuth } = useAdminAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await adminLogin(form)

      if (!data.user.is_admin) {
        toast.error('Access denied. This portal is for administrators only.')
        return
      }

      saveAuth(data.access_token, data.user)
      toast.success(`Welcome, ${data.user.name}`)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div className="w-12 h-12 rounded-xl bg-green-900/40 border border-green-700 flex items-center justify-center">
              <Shield className="text-green-400" size={28} />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white mt-3">SmartPark Admin Portal</h1>
          <p className="text-gray-500 text-sm mt-1">Restricted access — authorized personnel only</p>
        </div>

        {/* Warning banner */}
        <div className="mb-4 flex items-start gap-2 bg-yellow-900/20 border border-yellow-700/50 rounded-lg px-4 py-3 text-sm text-yellow-400">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          <span>Unauthorized access attempts are logged and monitored.</span>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-5 text-gray-100">Administrator Sign In</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Admin Email</label>
              <input
                type="email"
                className="input"
                placeholder="admin@smartpark.com"
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
                required
                autoComplete="username"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Password</label>
              <input
                type="password"
                className="input"
                placeholder="••••••••"
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                required
                autoComplete="current-password"
              />
            </div>
            <button
              type="submit"
              className="btn-primary w-full flex items-center justify-center gap-2"
              disabled={loading}
            >
              <LogIn size={16} />
              {loading ? 'Authenticating…' : 'Sign In to Admin Portal'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-700 mt-4">
          Not an admin?{' '}
          <a href={import.meta.env.VITE_USER_APP_URL || 'http://localhost:5173'}
             className="text-gray-500 hover:text-gray-300 transition-colors">
            Go to user portal →
          </a>
        </p>
      </div>
    </div>
  )
}
