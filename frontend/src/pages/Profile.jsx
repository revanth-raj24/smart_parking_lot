import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { updateMe, getVehicles, addVehicle, deleteVehicle } from '../api/auth'
import { getMySessions } from '../api/parking'
import toast from 'react-hot-toast'
import { User, Car, Trash2, Plus, Clock, CheckCircle, XCircle } from 'lucide-react'

function SessionRow({ s }) {
  const statusColor = { active: 'text-green-400', completed: 'text-blue-400', denied: 'text-red-400' }
  return (
    <div className="flex flex-wrap gap-2 justify-between items-start py-3 border-b border-gray-800 last:border-0 text-sm">
      <div className="space-y-0.5">
        <p className="text-gray-200 font-medium">{s.license_plate_raw}</p>
        <p className="text-gray-500 text-xs flex items-center gap-1">
          <Clock size={10} /> {new Date(s.entry_time).toLocaleString()}
        </p>
      </div>
      <div className="text-right space-y-0.5">
        <p className={`font-semibold capitalize ${statusColor[s.status] || 'text-gray-400'}`}>{s.status}</p>
        {s.cost != null && <p className="text-gray-400 text-xs">₹{s.cost.toFixed(2)}</p>}
        {s.duration_minutes != null && (
          <p className="text-gray-500 text-xs">{Math.round(s.duration_minutes)} min</p>
        )}
      </div>
    </div>
  )
}

export default function Profile() {
  const { user, setUser } = useAuth()
  const [form, setForm] = useState({ name: user?.name || '', phone: user?.phone || '' })
  const [saving, setSaving] = useState(false)
  const [vehicles, setVehicles] = useState([])
  const [newPlate, setNewPlate] = useState('')
  const [newType, setNewType] = useState('car')
  const [addingVehicle, setAddingVehicle] = useState(false)
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    getVehicles().then(r => setVehicles(r.data))
    getMySessions().then(r => setSessions(r.data))
  }, [])

  const saveProfile = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await updateMe(form)
      setUser(data)
      localStorage.setItem('user', JSON.stringify(data))
      toast.success('Profile updated')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Update failed')
    } finally {
      setSaving(false)
    }
  }

  const handleAddVehicle = async () => {
    if (!newPlate.trim()) return toast.error('Enter license plate')
    setAddingVehicle(true)
    try {
      const { data } = await addVehicle({ license_plate: newPlate.trim().toUpperCase(), vehicle_type: newType })
      setVehicles(v => [...v, data])
      setNewPlate('')
      toast.success('Vehicle added')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add vehicle')
    } finally {
      setAddingVehicle(false)
    }
  }

  const handleDeleteVehicle = async (id) => {
    if (!confirm('Remove this vehicle?')) return
    try {
      await deleteVehicle(id)
      setVehicles(v => v.filter(x => x.id !== id))
      toast.success('Vehicle removed')
    } catch {
      toast.error('Failed to remove vehicle')
    }
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <Navbar />
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        <h1 className="text-2xl font-bold text-white">Profile</h1>

        {/* Profile form */}
        <div className="card">
          <h2 className="font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <User size={16} className="text-green-400" /> Account Details
          </h2>
          <form onSubmit={saveProfile} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Full Name</label>
                <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Phone</label>
                <input className="input" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Email</label>
              <input className="input opacity-60 cursor-not-allowed" value={user?.email} disabled />
            </div>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </form>
        </div>

        {/* Vehicles */}
        <div className="card">
          <h2 className="font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <Car size={16} className="text-green-400" /> Registered Vehicles
          </h2>

          {vehicles.length === 0 ? (
            <p className="text-gray-500 text-sm mb-4">No vehicles registered yet</p>
          ) : (
            <div className="space-y-2 mb-4">
              {vehicles.map(v => (
                <div key={v.id} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
                  <div>
                    <p className="font-mono font-semibold text-white">{v.license_plate}</p>
                    <p className="text-xs text-gray-400 capitalize">{v.vehicle_type}</p>
                  </div>
                  <button
                    onClick={() => handleDeleteVehicle(v.id)}
                    className="text-gray-500 hover:text-red-400 transition-colors p-1.5 rounded-lg hover:bg-red-900/20"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <input
              className="input flex-1 uppercase font-mono"
              placeholder="KA01AB1234"
              value={newPlate}
              onChange={e => setNewPlate(e.target.value.toUpperCase())}
            />
            <select className="input w-28" value={newType} onChange={e => setNewType(e.target.value)}>
              <option value="car">Car</option>
              <option value="bike">Bike</option>
              <option value="suv">SUV</option>
              <option value="truck">Truck</option>
            </select>
            <button className="btn-primary px-4 flex items-center gap-1" onClick={handleAddVehicle} disabled={addingVehicle}>
              <Plus size={15} /> Add
            </button>
          </div>
        </div>

        {/* Parking history */}
        <div className="card">
          <h2 className="font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <Clock size={16} className="text-green-400" /> Parking History
          </h2>
          {sessions.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-6">No parking sessions yet</p>
          ) : (
            sessions.map(s => <SessionRow key={s.id} s={s} />)
          )}
        </div>
      </main>
    </div>
  )
}
