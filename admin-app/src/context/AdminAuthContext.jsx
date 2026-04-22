import { createContext, useContext, useState, useCallback } from 'react'

const AdminAuthContext = createContext(null)

const STORAGE_KEY_TOKEN = 'admin_token'
const STORAGE_KEY_USER  = 'admin_user'

export function AdminAuthProvider({ children }) {
  const [admin, setAdmin] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY_USER)) } catch { return null }
  })

  const saveAuth = useCallback((token, userData) => {
    if (!userData.is_admin) {
      throw new Error('Non-admin user cannot authenticate with admin portal')
    }
    localStorage.setItem(STORAGE_KEY_TOKEN, token)
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(userData))
    setAdmin(userData)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY_TOKEN)
    localStorage.removeItem(STORAGE_KEY_USER)
    setAdmin(null)
  }, [])

  return (
    <AdminAuthContext.Provider value={{ admin, saveAuth, logout }}>
      {children}
    </AdminAuthContext.Provider>
  )
}

export const useAdminAuth = () => useContext(AdminAuthContext)
