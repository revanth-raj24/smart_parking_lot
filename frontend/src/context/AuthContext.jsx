import { createContext, useContext, useState, useCallback } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('user'))
      // Admin tokens must never live in the user app — clear on load if found
      if (stored?.is_admin) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        return null
      }
      return stored
    } catch { return null }
  })

  const saveAuth = useCallback((token, userData) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(userData))
    setUser(userData)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, setUser, saveAuth, logout, isAdmin: user?.is_admin }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
