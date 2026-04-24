import api from './client'

export const createPreBooking = (data) => api.post('/prebook', data)
export const getMyPreBookings  = ()     => api.get('/prebook/my')
export const cancelPreBooking  = (id)   => api.delete(`/prebook/${id}`)
