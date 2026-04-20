import api from './client'

export const register  = (data) => api.post('/auth/register', data)
export const login     = (data) => api.post('/auth/login', data)
export const getMe     = ()     => api.get('/auth/me')
export const updateMe  = (data) => api.patch('/auth/me', data)

export const addVehicle    = (data) => api.post('/auth/vehicles', data)
export const getVehicles   = ()     => api.get('/auth/vehicles')
export const deleteVehicle = (id)   => api.delete(`/auth/vehicles/${id}`)
