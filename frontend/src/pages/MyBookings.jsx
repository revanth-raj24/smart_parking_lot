import { useState, useEffect, useCallback } from 'react'
import Navbar from '../components/Navbar'
import { getMyPreBookings, cancelPreBooking } from '../api/prebook'
import toast from 'react-hot-toast'
import { CalendarDays, RefreshCw, Loader2, X } from 'lucide-react'

const STATUS_STYLE = {
  active:    'bg-green-900/40 text-green-400 border border-green-800/60',
  cancelled: 'bg-red-900/40  text-red-400  border border-red-800/60',
}

export default function MyBookings() {
  const [bookings, setBookings] = useState([])
  const [loading, setLoading]   = useState(true)
  const [cancelling, setCancelling] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    getMyPreBookings()
      .then(r => setBookings(r.data))
      .catch(() => toast.error('Failed to load bookings'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleCancel = async (id) => {
    if (!confirm('Cancel this pre-booking?')) return
    setCancelling(id)
    try {
      await cancelPreBooking(id)
      toast.success('Booking cancelled')
      setBookings(bs => bs.map(b => b.id === id ? { ...b, status: 'cancelled' } : b))
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Cancel failed')
    } finally {
      setCancelling(null)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CalendarDays className="text-blue-400" size={22} />
            <h1 className="text-2xl font-bold text-white">My Pre-Bookings</h1>
          </div>
          <button onClick={load} className="btn-ghost text-sm flex items-center gap-1.5">
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        <div className="card">
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 size={24} className="animate-spin text-blue-400" />
            </div>
          ) : bookings.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-600 gap-3">
              <CalendarDays size={40} />
              <p className="text-sm font-medium">No pre-bookings yet</p>
              <p className="text-xs">Switch to Pre-Book mode on the dashboard to reserve a slot.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-800">
                    {['#', 'Slot', 'Date', 'Start', 'End', 'Status', 'Created', ''].map(h => (
                      <th key={h} className="pb-3 pr-4 font-medium whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {bookings.map(b => (
                    <tr key={b.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 text-xs">
                      <td className="py-3 pr-4 text-gray-500">{b.id}</td>
                      <td className="py-3 pr-4">
                        <span className="font-mono font-bold text-green-400 bg-green-900/20 px-2 py-0.5 rounded">
                          {b.slot_id}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-gray-300 whitespace-nowrap">{b.booking_date}</td>
                      <td className="py-3 pr-4 text-gray-300">{b.start_time}</td>
                      <td className="py-3 pr-4 text-gray-300">{b.end_time}</td>
                      <td className="py-3 pr-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase whitespace-nowrap ${STATUS_STYLE[b.status] || 'bg-gray-800 text-gray-400'}`}>
                          {b.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-gray-500 whitespace-nowrap">
                        {new Date(b.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3">
                        {b.status === 'active' && (
                          <button
                            disabled={cancelling === b.id}
                            onClick={() => handleCancel(b.id)}
                            className="flex items-center gap-1 px-2 py-1 rounded text-[10px] bg-red-900/40 text-red-400 hover:bg-red-900/70 transition-colors disabled:opacity-40"
                          >
                            {cancelling === b.id
                              ? <Loader2 size={10} className="animate-spin" />
                              : <X size={10} />
                            }
                            Cancel
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
