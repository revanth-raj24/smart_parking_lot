import { useState, useEffect, useCallback, useRef } from 'react'
import AdminNavbar from '../components/AdminNavbar'
import ParkingGrid from '../components/ParkingGrid'
import {
  adminGetStats, adminGetUsers, adminUpdateUser, adminDeleteUser,
  adminGetUserDetail, adminCreditWallet,
  adminGetSessions, adminCloseSession,
  adminGetOccupiedSlots, adminOverrideSlot,
  adminGetLatestCaptures, adminGetCaptures, adminGateControl,
  adminGetTransactions,
  adminSimulateEntry, adminSimulateExit,
  getSlots,
} from '../api/admin'
import { usePolling } from '../hooks/usePolling'
import toast from 'react-hot-toast'
import {
  Users, ParkingCircle, Activity, DoorOpen, DoorClosed,
  Pencil, Trash2, CheckCircle, XCircle, BarChart3,
  ArrowDownCircle, RefreshCw, Shield, FlaskConical,
  Upload, Loader2, ArrowRightCircle, ArrowLeftCircle,
  Camera, X, Car, Search, Clock, Wallet, ExternalLink, Image,
} from 'lucide-react'

const TABS = [
  { id: 'overview',     label: 'Overview',     icon: BarChart3 },
  { id: 'slots',        label: 'Slots',        icon: ParkingCircle },
  { id: 'users',        label: 'Users',        icon: Users },
  { id: 'sessions',     label: 'Sessions',     icon: Activity },
  { id: 'transactions', label: 'Transactions', icon: ArrowDownCircle },
  { id: 'camera',       label: 'Camera',       icon: Image },
  { id: 'testing',      label: 'Testing',      icon: FlaskConical },
]

function imgUrl(path) {
  if (!path) return null
  const fname = path.includes('/') ? path.split('/').pop() : path
  return `/images/${fname}`
}

function liveDuration(entryTime) {
  const mins = Math.floor((Date.now() - new Date(entryTime)) / 60000)
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

// ── Captured Image Card ───────────────────────────────────────────────────────
function CapturedImageCard({ label, imageName, captureTime, plate }) {
  const url = imageName ? `/images/${imageName}` : null
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-300 text-sm flex items-center gap-2">
          <Camera size={14} className="text-green-400" /> {label}
        </h3>
        {captureTime && <span className="text-xs text-gray-500">{new Date(captureTime).toLocaleString()}</span>}
      </div>
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" className="block">
          <img src={url} alt={label} className="w-full h-52 object-cover rounded-lg hover:opacity-90 transition-opacity" />
        </a>
      ) : (
        <div className="h-52 bg-gray-900 rounded-lg flex flex-col items-center justify-center gap-2 text-gray-700">
          <Camera size={36} />
          <p className="text-sm">No captures yet</p>
        </div>
      )}
      {plate && <p className="mt-2 text-xs text-gray-400">Plate: <span className="font-mono font-semibold text-white">{plate}</span></p>}
      {url && (
        <a href={url} target="_blank" rel="noreferrer" className="mt-1.5 text-xs text-green-500 hover:text-green-400 flex items-center gap-1">
          <ExternalLink size={11} /> View full image
        </a>
      )}
    </div>
  )
}

// ── Overview Tab ──────────────────────────────────────────────────────────────
function OverviewTab({ stats, captures }) {
  const [gateLoading, setGateLoading] = useState({})

  const sendGate = async (gate, action) => {
    const key = `${gate}-${action}`
    setGateLoading(g => ({ ...g, [key]: true }))
    try {
      const { data } = await adminGateControl({ gate, action })
      toast.success(`${gate} gate ${action} sent (${data.status})`)
    } catch (err) {
      toast.error(`Gate command failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setGateLoading(g => ({ ...g, [key]: false }))
    }
  }

  const statCards = stats ? [
    { label: 'Total Users',     value: stats.users,                             color: 'text-blue-400' },
    { label: 'Active Sessions', value: stats.active_sessions,                   color: 'text-green-400' },
    { label: 'Available Slots', value: stats.slots?.available ?? '—',           color: 'text-green-400' },
    { label: 'Occupied Slots',  value: stats.slots?.occupied  ?? '—',           color: 'text-red-400' },
    { label: 'Total Revenue',   value: `₹${stats.total_revenue?.toFixed(2) ?? '0.00'}`, color: 'text-yellow-400' },
  ] : []

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {statCards.map(({ label, value, color }) => (
          <div key={label} className="card text-center">
            <p className="text-gray-400 text-xs mb-1">{label}</p>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="card">
        <h2 className="font-semibold text-gray-200 mb-4 flex items-center gap-2">
          <Shield size={16} className="text-green-400" /> Gate Control
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { gate: 'entry', action: 'open',  label: 'Open Entry',  Icon: DoorOpen,   cls: 'btn-primary' },
            { gate: 'entry', action: 'close', label: 'Close Entry', Icon: DoorClosed, cls: 'btn-danger' },
            { gate: 'exit',  action: 'open',  label: 'Open Exit',   Icon: DoorOpen,   cls: 'btn-primary' },
            { gate: 'exit',  action: 'close', label: 'Close Exit',  Icon: DoorClosed, cls: 'btn-danger' },
          ].map(({ gate, action, label, Icon, cls }) => (
            <button key={`${gate}-${action}`} className={`${cls} flex items-center justify-center gap-2 text-sm`}
              onClick={() => sendGate(gate, action)} disabled={!!gateLoading[`${gate}-${action}`]}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <h2 className="font-semibold text-gray-300 text-sm mb-3 flex items-center gap-2">
          <Camera size={14} className="text-green-400" /> Last Captured Images
          <span className="text-xs text-gray-600 font-normal">(auto-updates)</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <CapturedImageCard label="Entry Camera — Last Capture" imageName={captures?.entry_image} captureTime={captures?.entry_time} plate={captures?.entry_plate} />
          <CapturedImageCard label="Exit Camera — Last Capture"  imageName={captures?.exit_image}  captureTime={captures?.exit_time}  plate={captures?.exit_plate} />
        </div>
      </div>
    </div>
  )
}

// ── Occupied Vehicles Table ───────────────────────────────────────────────────
function OccupiedVehiclesTable() {
  const [occupied, setOccupied] = useState([])
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)

  const fetch = useCallback(() => {
    setLoading(true)
    adminGetOccupiedSlots().then(r => setOccupied(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetch() }, [fetch, tick])

  if (loading) return <div className="flex justify-center py-6"><Loader2 size={20} className="animate-spin text-green-400" /></div>
  if (occupied.length === 0) return <div className="text-center py-6 text-gray-600 text-sm">No vehicles currently parked</div>

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-300 text-sm flex items-center gap-2">
          <Car size={14} className="text-green-400" /> Currently Occupied ({occupied.length})
        </h3>
        <button onClick={() => setTick(t => t + 1)} className="btn-ghost text-xs flex items-center gap-1">
          <RefreshCw size={11} /> Refresh
        </button>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-800">
            {['Slot', 'Floor', 'Plate', 'Type', 'User', 'Email', 'Phone', 'Entry', 'Duration'].map(h => (
              <th key={h} className="pb-2 pr-4 font-medium whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {occupied.map(o => (
            <tr key={o.session_id} className="border-b border-gray-800/50 hover:bg-gray-800/30 text-xs">
              <td className="py-2 pr-4"><span className="font-mono font-bold text-green-400 bg-green-900/20 px-2 py-0.5 rounded">{o.slot_number}</span></td>
              <td className="py-2 pr-4 text-gray-400">{o.floor}</td>
              <td className="py-2 pr-4 font-mono font-semibold text-white">{o.license_plate}</td>
              <td className="py-2 pr-4 text-gray-400 capitalize">{o.vehicle_type}</td>
              <td className="py-2 pr-4 text-gray-300">{o.user_name ?? '—'}</td>
              <td className="py-2 pr-4 text-gray-400">{o.user_email ?? '—'}</td>
              <td className="py-2 pr-4 text-gray-400">{o.user_phone ?? '—'}</td>
              <td className="py-2 pr-4 text-gray-400 whitespace-nowrap">{new Date(o.entry_time).toLocaleTimeString()}</td>
              <td className="py-2 pr-4 text-yellow-400 flex items-center gap-1"><Clock size={11} /> {liveDuration(o.entry_time)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Slots Tab ─────────────────────────────────────────────────────────────────
function SlotsTab({ slots, onRefresh }) {
  const [loading, setLoading] = useState(false)

  const override = async (slotId, status) => {
    setLoading(true)
    try {
      await adminOverrideSlot({ slot_id: slotId, status })
      toast.success(`Slot updated to ${status}`)
      onRefresh()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Override failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <ParkingGrid slots={slots} />
      <div className="card"><OccupiedVehiclesTable /></div>
      <div className="card">
        <h3 className="font-medium text-gray-300 mb-3 text-sm">Manual Override</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800">
                {['Slot', 'Current Status', 'Set To'].map(h => <th key={h} className="pb-2 pr-4 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {slots.map(slot => (
                <tr key={slot.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 pr-4 font-mono font-semibold text-white">{slot.slot_number}</td>
                  <td className="py-2 pr-4"><span className={`px-2 py-0.5 rounded-full text-xs badge-${slot.status}`}>{slot.status}</span></td>
                  <td className="py-2">
                    <div className="flex gap-1 flex-wrap">
                      {['available', 'occupied', 'reserved', 'maintenance'].map(s => (
                        <button key={s} disabled={loading || slot.status === s} onClick={() => override(slot.id, s)}
                          className={`px-2 py-0.5 rounded text-xs transition-colors disabled:opacity-30 ${slot.status === s ? 'bg-green-800 text-green-300' : 'bg-gray-700 hover:bg-gray-600 text-gray-300'}`}>
                          {s}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── User Detail Modal ─────────────────────────────────────────────────────────
function UserDetailModal({ user, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [creditAmt, setCreditAmt] = useState('')
  const [crediting, setCrediting] = useState(false)

  useEffect(() => {
    adminGetUserDetail(user.id).then(r => setDetail(r.data)).catch(() => toast.error('Failed to load user details')).finally(() => setLoading(false))
  }, [user.id])

  const handleCredit = async () => {
    const amount = parseFloat(creditAmt)
    if (!amount || amount <= 0) { toast.error('Enter a valid amount'); return }
    setCrediting(true)
    try {
      const { data } = await adminCreditWallet(user.id, amount)
      toast.success(`₹${amount.toFixed(2)} credited. New balance: ₹${data.new_balance.toFixed(2)}`)
      setDetail(d => d ? { ...d, wallet_balance: data.new_balance } : d)
      setCreditAmt('')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Credit failed')
    } finally {
      setCrediting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div>
            <h2 className="text-lg font-bold text-white">{user.name}</h2>
            <p className="text-sm text-gray-400">{user.email}</p>
          </div>
          <div className="flex items-center gap-2">
            {user.is_admin && <span className="text-xs font-bold text-yellow-400 bg-yellow-900/30 px-2 py-1 rounded">ADMIN</span>}
            <span className={`text-xs px-2 py-1 rounded ${user.is_active ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>{user.is_active ? 'Active' : 'Inactive'}</span>
            <button onClick={onClose} className="p-1 text-gray-400 hover:text-white transition-colors ml-2"><X size={18} /></button>
          </div>
        </div>

        {loading
          ? <div className="flex justify-center p-10"><Loader2 size={24} className="animate-spin text-green-400" /></div>
          : detail && (
            <div className="p-5 space-y-5">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Wallet',          val: detail.wallet_balance != null ? `₹${detail.wallet_balance.toFixed(2)}` : '—', color: 'text-green-400' },
                  { label: 'Total Sessions',  val: detail.total_sessions,  color: 'text-blue-400' },
                  { label: 'Active Now',      val: detail.active_sessions, color: 'text-yellow-400' },
                  { label: 'Joined',          val: new Date(detail.created_at).toLocaleDateString(), color: 'text-gray-300' },
                ].map(({ label, val, color }) => (
                  <div key={label} className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-500 mb-1">{label}</p>
                    <p className={`text-lg font-bold ${color}`}>{val}</p>
                  </div>
                ))}
              </div>

              <div className="bg-gray-800/30 rounded-lg p-4 text-sm grid grid-cols-2 gap-y-2 gap-x-4">
                <div><span className="text-gray-500">ID: </span><span className="text-gray-300">#{detail.id}</span></div>
                <div><span className="text-gray-500">Phone: </span><span className="text-gray-300">{detail.phone || '—'}</span></div>
                <div><span className="text-gray-500">Status: </span><span className={detail.is_active ? 'text-green-400' : 'text-red-400'}>{detail.is_active ? 'Active' : 'Inactive'}</span></div>
                <div><span className="text-gray-500">Role: </span><span className={detail.is_admin ? 'text-yellow-400' : 'text-gray-300'}>{detail.is_admin ? 'Admin' : 'User'}</span></div>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-1.5"><Wallet size={13} className="text-green-400" /> Add Wallet Funds</h4>
                <div className="flex gap-2">
                  <input type="number" min="1" max="50000" step="0.01" placeholder="₹ Amount" className="input flex-1 text-sm" value={creditAmt} onChange={e => setCreditAmt(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleCredit()} />
                  <button className="btn-primary text-sm px-5" onClick={handleCredit} disabled={crediting}>
                    {crediting ? <Loader2 size={14} className="animate-spin" /> : 'Credit'}
                  </button>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-1.5"><Car size={13} className="text-green-400" /> Vehicles ({detail.vehicles.length})</h4>
                {detail.vehicles.length === 0
                  ? <p className="text-sm text-gray-600">No vehicles registered</p>
                  : (
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-gray-500 border-b border-gray-800">
                          {['ID', 'Plate', 'Type', 'Active', 'Added'].map(h => <th key={h} className="pb-2 pr-4 font-medium">{h}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {detail.vehicles.map(v => (
                          <tr key={v.id} className="border-b border-gray-800/50">
                            <td className="py-1.5 pr-4 text-gray-500">{v.id}</td>
                            <td className="py-1.5 pr-4 font-mono font-bold text-white">{v.license_plate}</td>
                            <td className="py-1.5 pr-4 text-gray-400 capitalize">{v.vehicle_type}</td>
                            <td className="py-1.5 pr-4">{v.is_active ? <CheckCircle size={13} className="text-green-400" /> : <XCircle size={13} className="text-red-400" />}</td>
                            <td className="py-1.5 pr-4 text-gray-500">{new Date(v.created_at).toLocaleDateString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                }
              </div>
            </div>
          )
        }
      </div>
    </div>
  )
}

// ── Users Tab ─────────────────────────────────────────────────────────────────
function UsersTab() {
  const [users, setUsers] = useState([])
  const [editId, setEditId] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [selectedUser, setSelectedUser] = useState(null)

  useEffect(() => { adminGetUsers().then(r => setUsers(r.data)) }, [])

  const save = async (id) => {
    try {
      const { data } = await adminUpdateUser(id, editForm)
      setUsers(u => u.map(x => x.id === id ? data : x))
      setEditId(null)
      toast.success('User updated')
    } catch (err) { toast.error(err.response?.data?.detail || 'Update failed') }
  }

  const remove = async (id) => {
    if (!confirm('Delete this user? This cannot be undone.')) return
    try {
      await adminDeleteUser(id)
      setUsers(u => u.filter(x => x.id !== id))
      toast.success('User deleted')
    } catch (err) { toast.error(err.response?.data?.detail || 'Delete failed') }
  }

  return (
    <>
      {selectedUser && <UserDetailModal user={selectedUser} onClose={() => setSelectedUser(null)} />}
      <div className="card overflow-x-auto">
        <p className="text-xs text-gray-500 mb-3">Click a row to view full details, vehicles, and manage wallet.</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-800">
              {['ID', 'Name', 'Email', 'Phone', 'Active', 'Admin', 'Actions'].map(h => <th key={h} className="pb-3 pr-4 font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer" onClick={() => editId !== u.id && setSelectedUser(u)}>
                <td className="py-2.5 pr-4 text-gray-400">{u.id}</td>
                <td className="py-2.5 pr-4">
                  {editId === u.id
                    ? <input className="input py-1 text-xs w-28" value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} onClick={e => e.stopPropagation()} />
                    : <span className="text-gray-200">{u.name}</span>}
                </td>
                <td className="py-2.5 pr-4 text-gray-400 text-xs">{u.email}</td>
                <td className="py-2.5 pr-4">
                  {editId === u.id
                    ? <input className="input py-1 text-xs w-28" value={editForm.phone || ''} onChange={e => setEditForm({ ...editForm, phone: e.target.value })} onClick={e => e.stopPropagation()} />
                    : <span className="text-gray-400">{u.phone || '—'}</span>}
                </td>
                <td className="py-2.5 pr-4" onClick={e => e.stopPropagation()}>
                  {editId === u.id
                    ? <input type="checkbox" checked={editForm.is_active} onChange={e => setEditForm({ ...editForm, is_active: e.target.checked })} />
                    : u.is_active ? <CheckCircle size={15} className="text-green-400" /> : <XCircle size={15} className="text-red-400" />}
                </td>
                <td className="py-2.5 pr-4">{u.is_admin ? <span className="text-yellow-400 text-xs font-semibold">ADMIN</span> : <span className="text-gray-600 text-xs">user</span>}</td>
                <td className="py-2.5" onClick={e => e.stopPropagation()}>
                  {editId === u.id ? (
                    <div className="flex gap-1">
                      <button className="btn-primary text-xs py-1 px-2" onClick={() => save(u.id)}>Save</button>
                      <button className="btn-ghost text-xs py-1 px-2" onClick={() => setEditId(null)}>Cancel</button>
                    </div>
                  ) : (
                    <div className="flex gap-1">
                      <button className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors" onClick={() => { setEditId(u.id); setEditForm({ name: u.name, phone: u.phone, is_active: u.is_active }) }}>
                        <Pencil size={13} />
                      </button>
                      {!u.is_admin && (
                        <button className="p-1.5 rounded hover:bg-red-900/30 text-gray-400 hover:text-red-400 transition-colors" onClick={() => remove(u.id)}>
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ── Sessions Tab ──────────────────────────────────────────────────────────────
const STATUS_FILTERS = [{ key: 'all', label: 'All' }, { key: 'active', label: 'Active' }, { key: 'completed', label: 'Completed' }, { key: 'denied', label: 'Denied' }]
const STATUS_COLOR = { active: 'text-green-400', completed: 'text-blue-400', denied: 'text-red-400' }

function SessionsTab() {
  const [sessions, setSessions] = useState([])
  const [statusFilter, setStatusFilter] = useState('all')
  const [plateSearch, setPlateSearch] = useState('')
  const [closing, setClosing] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchSessions = useCallback(() => {
    setLoading(true)
    const params = { limit: 200 }
    if (statusFilter !== 'all') params.status = statusFilter
    if (plateSearch.trim()) params.plate = plateSearch.trim()
    adminGetSessions(params).then(r => setSessions(r.data)).catch(() => toast.error('Failed to load sessions')).finally(() => setLoading(false))
  }, [statusFilter, plateSearch])

  useEffect(() => { fetchSessions() }, [fetchSessions])

  const handleClose = async (sessionId, e) => {
    e.stopPropagation()
    if (!confirm('Force-close this session? Cost will be waived (₹0).')) return
    setClosing(sessionId)
    try {
      await adminCloseSession(sessionId)
      toast.success(`Session #${sessionId} closed`)
      fetchSessions()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Close failed')
    } finally { setClosing(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-1 bg-gray-900 p-1 rounded-lg border border-gray-800">
          {STATUS_FILTERS.map(f => (
            <button key={f.key} onClick={() => setStatusFilter(f.key)}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${statusFilter === f.key ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}`}>
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
            <input className="input pl-7 text-xs w-40" placeholder="Search plate…" value={plateSearch} onChange={e => setPlateSearch(e.target.value)} />
          </div>
          <button onClick={fetchSessions} className="btn-ghost text-xs flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
        </div>
      </div>

      <div className="card overflow-x-auto">
        {loading
          ? <div className="flex justify-center py-8"><Loader2 size={20} className="animate-spin text-green-400" /></div>
          : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-800">
                  {['ID', 'Plate', 'Slot', 'Entry', 'Exit', 'Duration', 'Cost', 'Status', 'Deny Reason', 'Image', 'Actions'].map(h => (
                    <th key={h} className="pb-3 pr-3 font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.length === 0
                  ? <tr><td colSpan={11} className="py-8 text-center text-gray-600 text-sm">No sessions found</td></tr>
                  : sessions.map(s => (
                    <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 text-xs">
                      <td className="py-2.5 pr-3 text-gray-500">{s.id}</td>
                      <td className="py-2.5 pr-3 font-mono font-semibold text-white">{s.license_plate_raw}</td>
                      <td className="py-2.5 pr-3">{s.slot_number ? <span className="font-mono text-green-400 font-semibold">{s.slot_number}</span> : <span className="text-gray-600">—</span>}</td>
                      <td className="py-2.5 pr-3 text-gray-400 whitespace-nowrap">{new Date(s.entry_time).toLocaleString()}</td>
                      <td className="py-2.5 pr-3 text-gray-400 whitespace-nowrap">{s.exit_time ? new Date(s.exit_time).toLocaleString() : '—'}</td>
                      <td className="py-2.5 pr-3 text-gray-400">{s.duration_minutes != null ? `${Math.round(s.duration_minutes)}m` : '—'}</td>
                      <td className="py-2.5 pr-3 text-gray-200">{s.cost != null ? `₹${s.cost.toFixed(2)}` : '—'}</td>
                      <td className={`py-2.5 pr-3 font-semibold capitalize ${STATUS_COLOR[s.status] || 'text-gray-400'}`}>{s.status}</td>
                      <td className="py-2.5 pr-3 text-gray-500 max-w-[160px] truncate" title={s.deny_reason || ''}>{s.deny_reason || '—'}</td>
                      <td className="py-2.5 pr-3">
                        {imgUrl(s.entry_image_path)
                          ? <a href={imgUrl(s.entry_image_path)} target="_blank" rel="noreferrer"><img src={imgUrl(s.entry_image_path)} alt="entry" className="w-14 h-9 object-cover rounded cursor-pointer hover:opacity-75 transition-opacity" /></a>
                          : '—'}
                      </td>
                      <td className="py-2.5 pr-3">
                        {s.status === 'active' && (
                          <button className="px-2 py-1 rounded text-xs bg-red-900/40 text-red-400 hover:bg-red-900/70 transition-colors disabled:opacity-40"
                            disabled={closing === s.id} onClick={e => handleClose(s.id, e)}>
                            {closing === s.id ? <Loader2 size={11} className="animate-spin" /> : 'Force Close'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                }
              </tbody>
            </table>
          )
        }
      </div>
    </div>
  )
}

// ── Transactions Tab ──────────────────────────────────────────────────────────
function TransactionsTab() {
  const [txns, setTxns] = useState([])
  useEffect(() => { adminGetTransactions({ limit: 200 }).then(r => setTxns(r.data)) }, [])
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-800">
            {['ID', 'User', 'Amount', 'Type', 'Status', 'Description', 'Date'].map(h => <th key={h} className="pb-3 pr-4 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {txns.map(t => (
            <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 text-xs">
              <td className="py-2.5 pr-4 text-gray-500">{t.id}</td>
              <td className="py-2.5 pr-4 text-gray-400">{t.user_id}</td>
              <td className={`py-2.5 pr-4 font-semibold ${t.transaction_type === 'credit' ? 'text-green-400' : 'text-red-400'}`}>
                {t.transaction_type === 'credit' ? '+' : '-'}₹{t.amount.toFixed(2)}
              </td>
              <td className="py-2.5 pr-4 capitalize text-gray-300">{t.transaction_type}</td>
              <td className="py-2.5 pr-4"><span className={`px-1.5 py-0.5 rounded text-xs ${t.status === 'success' ? 'bg-green-900 text-green-400' : 'bg-red-900 text-red-400'}`}>{t.status}</span></td>
              <td className="py-2.5 pr-4 text-gray-400 max-w-[200px] truncate">{t.description}</td>
              <td className="py-2.5 pr-4 text-gray-500 whitespace-nowrap">{new Date(t.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Camera Tab ────────────────────────────────────────────────────────────────
const CAPTURE_TYPES = [
  { key: 'all',   label: 'All' },
  { key: 'entry', label: 'Entry' },
  { key: 'exit',  label: 'Exit' },
]

function CameraTab() {
  const [captures, setCaptures] = useState([])
  const [loading, setLoading]   = useState(true)
  const [filter, setFilter]     = useState('all')
  const [lightbox, setLightbox] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    adminGetCaptures({ limit: 200 })
      .then(r => setCaptures(r.data))
      .catch(() => toast.error('Failed to load captures'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const visible = filter === 'all' ? captures : captures.filter(c => c.type === filter)

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex gap-1 bg-gray-900 p-1 rounded-lg border border-gray-800">
          {CAPTURE_TYPES.map(f => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${filter === f.key ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}`}>
              {f.label} {f.key !== 'all' && <span className="ml-1 opacity-60">{captures.filter(c => c.type === f.key).length}</span>}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">{visible.length} image{visible.length !== 1 ? 's' : ''}</span>
          <button onClick={load} className="btn-ghost text-xs flex items-center gap-1">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 size={24} className="animate-spin text-green-400" /></div>
      ) : visible.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-600 gap-3">
          <Camera size={40} />
          <p className="text-sm">No captures yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {visible.map((c, i) => (
            <div key={`${c.session_id}-${c.type}-${i}`}
              className="group relative rounded-xl overflow-hidden border border-gray-800 bg-gray-900 cursor-pointer hover:border-green-700 transition-colors"
              onClick={() => setLightbox(c)}>
              <img
                src={`/images/${c.image}`}
                alt={`${c.type} ${c.plate}`}
                className="w-full h-36 object-cover group-hover:opacity-90 transition-opacity"
                onError={e => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
              />
              <div className="hidden h-36 bg-gray-800 items-center justify-center text-gray-600"><Camera size={24} /></div>
              {/* Badge */}
              <span className={`absolute top-2 left-2 text-[10px] font-bold px-1.5 py-0.5 rounded ${c.type === 'entry' ? 'bg-green-700 text-green-100' : 'bg-blue-700 text-blue-100'}`}>
                {c.type.toUpperCase()}
              </span>
              {/* Info overlay */}
              <div className="p-2">
                <p className="font-mono font-bold text-white text-xs truncate">{c.plate}</p>
                <p className="text-gray-500 text-[10px] mt-0.5">{new Date(c.timestamp).toLocaleString()}</p>
                <p className="text-gray-600 text-[10px]">Session #{c.session_id}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {lightbox && (
        <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4" onClick={() => setLightbox(null)}>
          <div className="relative max-w-3xl w-full" onClick={e => e.stopPropagation()}>
            <button onClick={() => setLightbox(null)} className="absolute -top-10 right-0 text-gray-400 hover:text-white transition-colors">
              <X size={24} />
            </button>
            <img src={`/images/${lightbox.image}`} alt={lightbox.plate} className="w-full rounded-xl" />
            <div className="mt-3 flex items-center justify-between">
              <div>
                <span className={`text-xs font-bold px-2 py-1 rounded mr-2 ${lightbox.type === 'entry' ? 'bg-green-700 text-green-100' : 'bg-blue-700 text-blue-100'}`}>
                  {lightbox.type.toUpperCase()}
                </span>
                <span className="font-mono font-bold text-white text-lg">{lightbox.plate}</span>
              </div>
              <div className="text-right">
                <p className="text-gray-400 text-sm">{new Date(lightbox.timestamp).toLocaleString()}</p>
                <p className="text-gray-600 text-xs">Session #{lightbox.session_id}</p>
              </div>
            </div>
            <a href={`/images/${lightbox.image}`} target="_blank" rel="noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs text-green-500 hover:text-green-400">
              <ExternalLink size={11} /> Open full size
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Testing Tab ───────────────────────────────────────────────────────────────
function ResultCard({ result }) {
  if (!result) return null
  const allow = result.status === 'ALLOW'
  return (
    <div className={`rounded-lg border p-4 mt-4 space-y-2 text-sm ${allow ? 'border-green-700 bg-green-950/40' : 'border-red-700 bg-red-950/40'}`}>
      <div className="flex items-center gap-2 font-bold text-base">
        {allow ? <CheckCircle size={18} className="text-green-400" /> : <XCircle size={18} className="text-red-400" />}
        <span className={allow ? 'text-green-400' : 'text-red-400'}>{result.status}</span>
      </div>
      {result.license_plate && <p className="text-gray-300">Plate: <span className="font-mono font-semibold text-white">{result.license_plate}</span></p>}
      {result.message && <p className="text-gray-400">{result.message}</p>}
      {result.session_id && <p className="text-gray-500 text-xs">Session: #{result.session_id}</p>}
      {result.cost != null && <p className="text-gray-300">Cost: <span className="text-yellow-400 font-semibold">₹{result.cost?.toFixed(2)}</span></p>}
      {result.wallet_balance != null && <p className="text-gray-300">Wallet: <span className="text-blue-400 font-semibold">₹{result.wallet_balance?.toFixed(2)}</span></p>}
    </div>
  )
}

function SimulateCard({ title, icon: Icon, onSimulate, loading }) {
  const inputRef = useRef(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)

  return (
    <div className="card space-y-4">
      <h3 className="font-semibold text-gray-200 flex items-center gap-2"><Icon size={16} className="text-green-400" /> {title}</h3>
      <div onClick={() => inputRef.current?.click()} className="border-2 border-dashed border-gray-700 hover:border-green-600 rounded-lg p-6 text-center cursor-pointer transition-colors group">
        {preview
          ? <img src={preview} alt="preview" className="mx-auto max-h-48 rounded object-contain" />
          : <div className="space-y-2 text-gray-500 group-hover:text-gray-400"><Upload size={28} className="mx-auto" /><p className="text-sm">Click to upload a plate image</p></div>
        }
        <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) { setPreview(URL.createObjectURL(f)); setResult(null) } }} />
      </div>
      <div className="flex gap-2">
        <button onClick={async () => { const f = inputRef.current?.files?.[0]; if (!f) { toast.error('Select an image'); return } setResult(await onSimulate(f)) }} disabled={loading} className="btn-primary flex items-center gap-2 flex-1 justify-center">
          {loading ? <><Loader2 size={15} className="animate-spin" /> Processing…</> : <><Icon size={15} /> Trigger {title}</>}
        </button>
        {preview && <button onClick={() => { setPreview(null); setResult(null); inputRef.current.value = '' }} className="btn-ghost px-3 text-xs">Clear</button>}
      </div>
      <ResultCard result={result} />
    </div>
  )
}

function TestingTab() {
  const [entryLoading, setEntryLoading] = useState(false)
  const [exitLoading,  setExitLoading]  = useState(false)
  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-blue-950/50 border border-blue-800 px-4 py-3 text-sm text-blue-300 flex items-start gap-2">
        <FlaskConical size={15} className="mt-0.5 shrink-0" />
        <span>Testing mode — IR sensor and servo bypassed. Upload any plate image to run full OCR → DB → gate pipeline.</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SimulateCard title="Simulate Entry" icon={ArrowRightCircle} loading={entryLoading}
          onSimulate={f => { setEntryLoading(true); return adminSimulateEntry(f).then(r => r.data).catch(err => { toast.error(err.response?.data?.detail || 'Failed'); return null }).finally(() => setEntryLoading(false)) }} />
        <SimulateCard title="Simulate Exit" icon={ArrowLeftCircle} loading={exitLoading}
          onSimulate={f => { setExitLoading(true); return adminSimulateExit(f).then(r => r.data).catch(err => { toast.error(err.response?.data?.detail || 'Failed'); return null }).finally(() => setExitLoading(false)) }} />
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function AdminDashboard() {
  const [tab, setTab] = useState('overview')
  const [stats, setStats] = useState(null)
  const [slots, setSlots] = useState([])
  const [captures, setCaptures] = useState(null)

  const fetchBase = useCallback(async () => {
    const [statsRes, slotsRes, capturesRes] = await Promise.allSettled([
      adminGetStats(), getSlots(), adminGetLatestCaptures(),
    ])
    if (statsRes.status    === 'fulfilled') setStats(statsRes.value.data)
    if (slotsRes.status    === 'fulfilled') setSlots(slotsRes.value.data)
    if (capturesRes.status === 'fulfilled') setCaptures(capturesRes.value.data)
  }, [])

  usePolling(fetchBase, 10000)

  return (
    <div className="min-h-screen bg-gray-950">
      <AdminNavbar />
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield size={22} className="text-green-400" /> Admin Panel
          </h1>
          <button onClick={fetchBase} className="btn-ghost text-sm flex items-center gap-1.5">
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        <div className="flex gap-1 flex-wrap border-b border-gray-800 pb-0">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-colors rounded-t-lg border-b-2 -mb-px ${tab === id ? 'border-green-500 text-green-400 bg-green-500/10' : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800'}`}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        {tab === 'overview'     && <OverviewTab stats={stats} captures={captures} />}
        {tab === 'slots'        && <SlotsTab slots={slots} onRefresh={fetchBase} />}
        {tab === 'users'        && <UsersTab />}
        {tab === 'sessions'     && <SessionsTab />}
        {tab === 'transactions' && <TransactionsTab />}
        {tab === 'camera'       && <CameraTab />}
        {tab === 'testing'      && <TestingTab />}
      </main>
    </div>
  )
}
