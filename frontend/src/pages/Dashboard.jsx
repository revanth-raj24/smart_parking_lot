import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import ParkingGrid from '../components/ParkingGrid'
import CameraFeed from '../components/CameraFeed'
import BookSlotModal from '../components/BookSlotModal'
import { getSlots, getActiveSession } from '../api/parking'
import { getBalance } from '../api/wallet'
import { usePolling } from '../hooks/usePolling'
import { useAuth } from '../context/AuthContext'
import { Clock, IndianRupee, Car, RefreshCw } from 'lucide-react'

function ActiveSessionBanner({ session }) {
  const [elapsed, setElapsed] = useState('')

  useEffect(() => {
    if (!session) return
    const update = () => {
      const diff = (Date.now() - new Date(session.entry_time).getTime()) / 1000
      const h = Math.floor(diff / 3600)
      const m = Math.floor((diff % 3600) / 60)
      const s = Math.floor(diff % 60)
      setElapsed(`${h}h ${m}m ${s}s`)
    }
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [session])

  if (!session) return null

  return (
    <div className="bg-green-900/30 border border-green-700 rounded-xl p-4 flex flex-wrap gap-4 items-center">
      <div className="flex items-center gap-2 text-green-400">
        <Car size={18} />
        <span className="font-semibold">{session.license_plate_raw}</span>
      </div>
      <div className="flex items-center gap-1.5 text-gray-300 text-sm">
        <Clock size={14} className="text-green-400" />
        Parked for <b className="text-white ml-1">{elapsed}</b>
      </div>
      {session.slot_id && (
        <span className="text-sm text-gray-300">
          Slot: <b className="text-white">P{session.slot_id}</b>
        </span>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [slots, setSlots] = useState([])
  const [balance, setBalance] = useState(null)
  const [activeSession, setActiveSession] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [lastRefresh, setLastRefresh] = useState(new Date())

  const fetchAll = async () => {
    const [slotsRes, balRes, sessionRes] = await Promise.allSettled([
      getSlots(),
      getBalance(),
      getActiveSession(),
    ])
    if (slotsRes.status === 'fulfilled')   setSlots(slotsRes.value.data)
    if (balRes.status === 'fulfilled')     setBalance(balRes.value.data.balance)
    if (sessionRes.status === 'fulfilled') setActiveSession(sessionRes.value.data)
    setLastRefresh(new Date())
  }

  usePolling(fetchAll, 5000)

  const ENTRY_CAM = import.meta.env.VITE_ENTRY_CAM_URL || ''
  const EXIT_CAM  = import.meta.env.VITE_EXIT_CAM_URL  || ''

  return (
    <div className="min-h-screen bg-gray-950">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Welcome, {user?.name}</h1>
            <p className="text-gray-400 text-sm mt-0.5">
              Live parking status · refreshes every 5s
            </p>
          </div>
          <div className="flex items-center gap-4">
            {balance !== null && (
              <div className="flex items-center gap-1.5 bg-gray-900 border border-gray-700 px-3 py-2 rounded-lg">
                <IndianRupee size={14} className="text-green-400" />
                <span className="font-semibold text-white">{balance.toFixed(2)}</span>
                <span className="text-gray-400 text-xs">wallet</span>
              </div>
            )}
            <div className="flex items-center gap-1 text-gray-500 text-xs">
              <RefreshCw size={11} className="animate-spin" />
              {lastRefresh.toLocaleTimeString()}
            </div>
          </div>
        </div>

        {/* Active session banner */}
        <ActiveSessionBanner session={activeSession} />

        {/* Parking grid */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-100 mb-4">
            Parking Slots
            <span className="ml-2 text-sm font-normal text-gray-400">(click an available slot to book)</span>
          </h2>
          <ParkingGrid
            slots={slots}
            selectable
            onBook={(slot) => setSelectedSlot(slot)}
          />
        </div>

        {/* Bottom row: controls + cameras */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Stats */}
          <div className="card space-y-3">
            <h2 className="text-base font-semibold text-gray-200 mb-2">Parking Stats</h2>
            {[
              { label: 'Total Slots',  value: slots.length,                                         color: 'text-blue-400' },
              { label: 'Available',    value: slots.filter(s => s.status === 'available').length,   color: 'text-green-400' },
              { label: 'Occupied',     value: slots.filter(s => s.status === 'occupied').length,    color: 'text-red-400' },
              { label: 'Reserved',     value: slots.filter(s => s.status === 'reserved').length,    color: 'text-yellow-400' },
            ].map(({ label, value, color }) => (
              <div key={label} className="flex justify-between items-center py-2 border-b border-gray-800 last:border-0">
                <span className="text-gray-400 text-sm">{label}</span>
                <span className={`font-bold text-lg ${color}`}>{value}</span>
              </div>
            ))}
          </div>

          {/* Camera feeds */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <CameraFeed label="Entry Camera" url={ENTRY_CAM} />
            <CameraFeed label="Exit Camera"  url={EXIT_CAM} />
          </div>
        </div>
      </main>

      {selectedSlot && (
        <BookSlotModal
          slot={selectedSlot}
          onClose={() => setSelectedSlot(null)}
          onSuccess={() => { setSelectedSlot(null); fetchAll() }}
        />
      )}
    </div>
  )
}
