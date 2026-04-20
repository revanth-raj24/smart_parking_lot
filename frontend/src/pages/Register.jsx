import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { register } from '../api/auth'
import toast from 'react-hot-toast'
import { ParkingCircle, UserPlus } from 'lucide-react'

export default function Register() {
  const { saveAuth } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', phone: '' })
  const [loading, setLoading] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await register(form)
      saveAuth(data.access_token, data.user)
      toast.success('Account created! Welcome 🎉')
      navigate('/dashboard', { replace: true })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <ParkingCircle className="text-green-400" size={40} />
            <span className="text-3xl font-bold text-white">SmartPark</span>
          </div>
          <p className="text-gray-400">Create your account</p>
        </div>

        <div className="card">
          <h2 className="text-xl font-semibold mb-6 text-gray-100">Register</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {[
              { label: 'Full Name', key: 'name', type: 'text', placeholder: 'John Doe' },
              { label: 'Email', key: 'email', type: 'email', placeholder: 'you@example.com' },
              { label: 'Phone', key: 'phone', type: 'tel', placeholder: '+91 9876543210' },
              { label: 'Password', key: 'password', type: 'password', placeholder: '••••••••' },
            ].map(({ label, key, type, placeholder }) => (
              <div key={key}>
                <label className="block text-sm text-gray-400 mb-1">{label}</label>
                <input
                  type={type}
                  className="input"
                  placeholder={placeholder}
                  value={form[key]}
                  onChange={set(key)}
                  required={key !== 'phone'}
                />
              </div>
            ))}
            <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" disabled={loading}>
              <UserPlus size={16} />
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>
          <p className="mt-4 text-center text-sm text-gray-400">
            Already registered?{' '}
            <Link to="/login" className="text-green-400 hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
