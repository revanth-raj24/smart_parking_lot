import axios from 'axios'

const adminApi = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

adminApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

adminApi.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_user')
      window.location.href = '/login'
    }
    if (err.response?.status === 403 && err.response?.data?.detail?.includes('Admin API')) {
      // Shouldn't happen — admin app is on correct origin — log and surface
      console.error('[AdminClient] Origin guard rejected request:', err.response.data.detail)
    }
    return Promise.reject(err)
  }
)

export default adminApi
