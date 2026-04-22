import api from './client'

export const adminGetUsers        = (params) => api.get('/admin/users', { params })
export const adminGetUserDetail   = (id)     => api.get(`/admin/users/${id}/detail`)
export const adminUpdateUser      = (id, data) => api.patch(`/admin/users/${id}`, data)
export const adminDeleteUser      = (id)     => api.delete(`/admin/users/${id}`)
export const adminCreditWallet    = (id, amount) => api.post(`/admin/users/${id}/wallet/credit`, { amount })

export const adminGetSessions     = (params) => api.get('/admin/sessions', { params })
export const adminCloseSession    = (id)     => api.patch(`/admin/sessions/${id}/close`)

export const adminGetOccupiedSlots = ()      => api.get('/admin/slots/occupied')
export const adminOverrideSlot    = (data)   => api.post('/admin/override', data)

export const adminGetLatestCaptures = ()     => api.get('/admin/latest-captures')
export const adminGateControl     = (data)   => api.post('/admin/gate-control', data)
export const adminGetTransactions = (params) => api.get('/admin/transactions', { params })
export const adminGetStats        = ()       => api.get('/admin/stats')

export const adminSimulateEntry = (file) => {
  const form = new FormData()
  form.append('image', file)
  return api.post('/admin/simulate-entry', form)
}

export const adminSimulateExit = (file) => {
  const form = new FormData()
  form.append('image', file)
  return api.post('/admin/simulate-exit', form)
}
