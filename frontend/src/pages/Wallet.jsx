import { useState, useEffect, useCallback } from 'react'
import Navbar from '../components/Navbar'
import { getBalance, addFunds, getTransactions } from '../api/wallet'
import toast from 'react-hot-toast'
import { IndianRupee, PlusCircle, ArrowDownCircle, ArrowUpCircle, Clock } from 'lucide-react'

const QUICK_AMOUNTS = [100, 200, 500, 1000]

function TransactionRow({ txn }) {
  const isCredit = txn.transaction_type === 'credit'
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-800 last:border-0">
      <div className="flex items-center gap-3">
        {isCredit
          ? <ArrowUpCircle size={18} className="text-green-400 shrink-0" />
          : <ArrowDownCircle size={18} className="text-red-400 shrink-0" />
        }
        <div>
          <p className="text-sm text-gray-200">{txn.description || '—'}</p>
          <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
            <Clock size={10} />
            {new Date(txn.created_at).toLocaleString()}
          </p>
        </div>
      </div>
      <span className={`font-semibold text-sm ${isCredit ? 'text-green-400' : 'text-red-400'}`}>
        {isCredit ? '+' : '-'}₹{txn.amount.toFixed(2)}
      </span>
    </div>
  )
}

export default function Wallet() {
  const [balance, setBalance] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)

  const fetchData = useCallback(async () => {
    const [balRes, txnRes] = await Promise.allSettled([getBalance(), getTransactions()])
    if (balRes.status === 'fulfilled') setBalance(balRes.value.data.balance)
    if (txnRes.status === 'fulfilled') setTransactions(txnRes.value.data)
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  const handleTopUp = async (amt) => {
    const value = parseFloat(amt || amount)
    if (!value || value <= 0) return toast.error('Enter a valid amount')
    setLoading(true)
    try {
      const { data } = await addFunds(value)
      setBalance(data.new_balance)
      toast.success(data.message)
      setAmount('')
      fetchData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Top-up failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <Navbar />
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        <h1 className="text-2xl font-bold text-white">My Wallet</h1>

        {/* Balance card */}
        <div className="card bg-gradient-to-br from-green-900/40 to-gray-900 border-green-800">
          <p className="text-gray-400 text-sm mb-1">Available Balance</p>
          <div className="flex items-end gap-2">
            <IndianRupee size={28} className="text-green-400 mb-0.5" />
            <span className="text-5xl font-bold text-white">
              {balance !== null ? balance.toFixed(2) : '—'}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-2">Automatically deducted on exit</p>
        </div>

        {/* Top-up */}
        <div className="card">
          <h2 className="font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <PlusCircle size={16} className="text-green-400" /> Add Funds
          </h2>

          {/* Quick amounts */}
          <div className="flex gap-2 flex-wrap mb-4">
            {QUICK_AMOUNTS.map(a => (
              <button
                key={a}
                className="btn-ghost text-sm px-4"
                onClick={() => handleTopUp(a)}
                disabled={loading}
              >
                +₹{a}
              </button>
            ))}
          </div>

          {/* Custom amount */}
          <div className="flex gap-3">
            <div className="relative flex-1">
              <IndianRupee size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="number"
                className="input pl-8"
                placeholder="Custom amount"
                value={amount}
                min={1}
                max={10000}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <button
              className="btn-primary px-6"
              onClick={() => handleTopUp()}
              disabled={loading || !amount}
            >
              {loading ? 'Adding…' : 'Add'}
            </button>
          </div>

          <p className="text-xs text-yellow-500 mt-2">
            Demo mode — no real payment processed
          </p>

          <div className="mt-6 flex flex-col items-center gap-2">
            <p className="text-sm text-gray-400">Or pay via UPI</p>
            <img src="/qrcode.jpeg" alt="UPI QR Code" className="w-56 h-56 rounded-xl object-contain" />
            <p className="text-xs text-gray-500">UPI ID: mohanrmohan2345@oksbi</p>
          </div>
        </div>

        {/* Transaction history */}
        <div className="card">
          <h2 className="font-semibold text-gray-200 mb-4">Transaction History</h2>
          {transactions.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-8">No transactions yet</p>
          ) : (
            transactions.map(txn => <TransactionRow key={txn.id} txn={txn} />)
          )}
        </div>
      </main>
    </div>
  )
}
