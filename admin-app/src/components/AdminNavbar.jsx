import { useAdminAuth } from '../context/AdminAuthContext'
import { Shield, LogOut, ParkingCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function AdminNavbar() {
  const { admin, logout } = useAdminAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-gray-900 border-b border-gray-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-2">
          <ParkingCircle className="text-green-400" size={24} />
          <span className="font-bold text-white text-lg">SmartPark</span>
          <span className="hidden sm:inline-flex items-center gap-1 ml-2 bg-green-900/40 border border-green-700 text-green-400 text-xs font-semibold px-2 py-0.5 rounded-full">
            <Shield size={11} /> Admin Portal
          </span>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {admin && (
            <div className="hidden sm:flex items-center gap-2 text-sm">
              <div className="w-7 h-7 rounded-full bg-green-600 flex items-center justify-center text-black font-bold text-xs">
                {admin.name?.charAt(0).toUpperCase()}
              </div>
              <span className="text-gray-300">{admin.name}</span>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-gray-400 hover:text-red-400 transition-colors p-1.5 rounded-lg hover:bg-gray-800 text-sm"
          >
            <LogOut size={15} />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </div>
    </nav>
  )
}
