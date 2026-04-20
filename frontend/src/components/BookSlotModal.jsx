import { useState } from 'react'
import { bookSlot } from '../api/parking'
import { getVehicles } from '../api/auth'
import { useEffect } from 'react'
import toast from 'react-hot-toast'
import { X, ParkingCircle } from 'lucide-react'

export default function BookSlotModal({ slot, onClose, onSuccess }) {
  const [vehicles, setVehicles] = useState([])
  const [plate, setPlate] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getVehicles().then(r => {
      setVehicles(r.data)
      if (r.data.length > 0) setPlate(r.data[0].license_plate)
    })
  }, [])

  const handleBook = async () => {
    if (!plate.trim()) return toast.error('Select or enter a license plate')
    setLoading(true)
    try {
      await bookSlot({ slot_id: slot.id, license_plate: plate.trim().toUpperCase() })
      toast.success(`Slot ${slot.slot_number} reserved!`)
      onSuccess()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Booking failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ParkingCircle className="text-green-400" size={20} />
            <h3 className="font-semibold text-gray-100">Book Slot {slot.slot_number}</h3>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4">
          {vehicles.length > 0 ? (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Select Vehicle</label>
              <select
                className="input"
                value={plate}
                onChange={(e) => setPlate(e.target.value)}
              >
                {vehicles.map(v => (
                  <option key={v.id} value={v.license_plate}>
                    {v.license_plate} ({v.vehicle_type})
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-sm text-gray-400 mb-1">License Plate</label>
              <input
                className="input uppercase"
                placeholder="KA01AB1234"
                value={plate}
                onChange={(e) => setPlate(e.target.value.toUpperCase())}
              />
              <p className="text-xs text-yellow-500 mt-1">
                No vehicles registered. Add one in Profile first.
              </p>
            </div>
          )}

          <div className="bg-gray-800 rounded-lg p-3 text-sm text-gray-300 space-y-1">
            <div className="flex justify-between"><span>First hour:</span><span className="font-semibold text-white">₹60</span></div>
            <div className="flex justify-between"><span>Per additional hour:</span><span className="font-semibold text-white">₹30</span></div>
          </div>

          <div className="flex gap-3">
            <button onClick={onClose} className="btn-ghost flex-1">Cancel</button>
            <button onClick={handleBook} disabled={loading} className="btn-primary flex-1">
              {loading ? 'Booking…' : 'Confirm'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
