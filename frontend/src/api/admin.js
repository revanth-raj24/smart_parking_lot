import api from './client'

export const adminGetUsers       = (params) => api.get('/admin/users', { params })
export const adminUpdateUser     = (id, data) => api.patch(`/admin/users/${id}`, data)
export const adminDeleteUser     = (id)   => api.delete(`/admin/users/${id}`)
export const adminGetSessions    = (params) => api.get('/admin/sessions', { params })
export const adminOverrideSlot   = (data) => api.post('/admin/override', data)
export const adminGateControl    = (data) => api.post('/admin/gate-control', data)
export const adminGetTransactions= (params) => api.get('/admin/transactions', { params })
export const adminGetStats       = ()     => api.get('/admin/stats')
