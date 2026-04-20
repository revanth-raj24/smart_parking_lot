import api from './client'

export const getBalance      = ()       => api.get('/wallet/balance')
export const addFunds        = (amount) => api.post('/wallet/add', { amount })
export const getTransactions = ()       => api.get('/wallet/transactions')
