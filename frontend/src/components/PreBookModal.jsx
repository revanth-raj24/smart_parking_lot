import { useState } from 'react'
import { X, CalendarDays } from 'lucide-react'
import toast from 'react-hot-toast'
import { createPreBooking } from '../api/prebook'

function today() {
  return new Date().toISOString().slice(0, 10)
}

export default function PreBookModal({ slot, onClose, onSuccess }) {
  const [date, setDate]           = useState(today())
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime]     = useState('11:00')
  const [loading, setLoading]     = useState(false)

  const handleSubmit = async () => {
    if (!date || !startTime || !endTime) {
      return toast.error('All fields are required')
    }
    if (startTime >= endTime) {
      return toast.error('Start time must be before end time')
    }

    setLoading(true)
    try {
      await createPreBooking({
        slot_id: slot.slot_number,
        date,
        start_time: startTime,
        end_time: endTime,
      })
      toast.success(`Slot ${slot.slot_number} pre-booked for ${date}`)
      onSuccess()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Pre-booking failed'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <CalendarDays className="text-blue-400" size={20} />
            <h3 className="font-semibold text-gray-100">Pre-Book Slot {slot.slot_number}</h3>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4">
          {/* Date */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Date</label>
            <input
              type="date"
              className="input"
              min={today()}
              value={date}
              onChange={e => setDate(e.target.value)}
            />
          </div>

          {/* Times */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Start Time</label>
              <input
                type="time"
                className="input"
                value={startTime}
                onChange={e => setStartTime(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">End Time</label>
              <input
                type="time"
                className="input"
                value={endTime}
                onChange={e => setEndTime(e.target.value)}
              />
            </div>
          </div>

          {/* Info note */}
          <div className="bg-blue-950/50 border border-blue-800 rounded-lg p-3 text-xs text-blue-300">
            Pre-booking reserves the time slot. Payment is charged when you actually park.
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-1">
            <button onClick={onClose} className="btn-ghost flex-1">Cancel</button>
            <button onClick={handleSubmit} disabled={loading} className="btn-primary flex-1">
              {loading ? 'Booking…' : 'Confirm Pre-Book'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
