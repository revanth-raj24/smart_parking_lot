import api from './client'

export const getSlots        = ()       => api.get('/parking/slots')
export const bookSlot        = (data)   => api.post('/parking/book-slot', data)
export const getMySessions   = ()       => api.get('/parking/my-sessions')
export const getActiveSession= ()       => api.get('/parking/active-session')
