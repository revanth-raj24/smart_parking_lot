import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ParkingCircle, LayoutDashboard, Wallet, User, Shield, LogOut, CalendarDays } from 'lucide-react'

const userNav = [
  { to: '/dashboard',   label: 'Dashboard',   icon: LayoutDashboard },
  { to: '/my-bookings', label: 'My Bookings', icon: CalendarDays },
  { to: '/wallet',      label: 'Wallet',      icon: Wallet },
  { to: '/profile',     label: 'Profile',     icon: User },
]

export default function Navbar() {
  const { user, logout, isAdmin } = useAuth()
  const { pathname } = useLocation()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-gray-900 border-b border-gray-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Brand */}
        <Link to={isAdmin ? '/admin' : '/dashboard'} className="flex items-center gap-2">
          <ParkingCircle className="text-green-400" size={24} />
          <span className="font-bold text-white text-lg">SmartPark</span>
        </Link>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          {isAdmin ? (
            <Link
              to="/admin"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname === '/admin'
                  ? 'bg-green-500/20 text-green-400'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              <Shield size={15} /> Admin Panel
            </Link>
          ) : (
            userNav.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  pathname === to
                    ? 'bg-green-500/20 text-green-400'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                <Icon size={15} /> {label}
              </Link>
            ))
          )}

          {/* User info + logout */}
          <div className="ml-3 pl-3 border-l border-gray-700 flex items-center gap-2">
            <span className="text-xs text-gray-400 hidden sm:block">{user?.name}</span>
            <button onClick={handleLogout} className="text-gray-400 hover:text-red-400 transition-colors p-1.5 rounded-lg hover:bg-gray-800">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}
