import { useState, useEffect, useCallback } from 'react'
import Navbar from '../components/Navbar'
import ParkingGrid from '../components/ParkingGrid'
import CameraFeed from '../components/CameraFeed'
import {
  adminGetStats, adminGetUsers, adminUpdateUser, adminDeleteUser,
  adminGetSessions, adminOverrideSlot, adminGateControl, adminGetTransactions,
} from '../api/admin'
import { getSlots } from '../api/parking'
import { usePolling } from '../hooks/usePolling'
import toast from 'react-hot-toast'
import {
  Users, ParkingCircle, Activity, DoorOpen, DoorClosed,
  Pencil, Trash2, CheckCircle, XCircle, BarChart3,
  ArrowDownCircle, ArrowUpCircle, RefreshCw, Shield
} from 'lucide-react'

// ── Tabs ─────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'overview',     label: 'Overview',     icon: BarChart3 },
  { id: 'slots',        label: 'Slots',        icon: ParkingCircle },
  { id: 'users',        label: 'Users',        icon: Users },
  { id: 'sessions',     label: 'Sessions',     icon: Activity },
  { id: 'transactions', label: 'Transactions', icon: ArrowDownCircle },
]

// ── Overview Tab ─────────────────────────────────────────────────────────────
function OverviewTab({ stats, entryCam, exitCam }) {
  const [gateLoading, setGateLoading] = useState({})

  const sendGate = async (gate, action) => {
    const key = `${gate}-${action}`
    setGateLoading(g => ({ ...g, [key]: true }))
    try {
      const { data } = await adminGateControl({ gate, action })
      toast.success(`${gate} gate ${action} command sent (${data.status})`)
    } catch (err) {
      toast.error(`Gate command failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setGateLoading(g => ({ ...g, [key]: false }))
    }
  }

  const statCards = stats ? [
    { label: 'Total Users',     value: stats.users,                  color: 'text-blue-400' },
    { label: 'Active Sessions', value: stats.active_sessions,        color: 'text-green-400' },
    { label: 'Available Slots', value: stats.slots?.available ?? '—', color: 'text-green-400' },
    { label: 'Occupied Slots',  value: stats.slots?.occupied  ?? '—', color: 'text-red-400' },
    { label: 'Total Revenue',   value: `₹${stats.total_revenue?.toFixed(2) ?? '0.00'}`, color: 'text-yellow-400' },
  ] : []

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {statCards.map(({ label, value, color }) => (
          <div key={label} className="card text-center">
            <p className="text-gray-400 text-xs mb-1">{label}</p>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Gate controls */}
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
            <button
              key={`${gate}-${action}`}
              className={`${cls} flex items-center justify-center gap-2 text-sm`}
              onClick={() => sendGate(gate, action)}
              disabled={!!gateLoading[`${gate}-${action}`]}
            >
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>
      </div>

      {/* Live feeds */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <CameraFeed label="Entry Camera" url={entryCam} />
        <CameraFeed label="Exit Camera"  url={exitCam} />
      </div>
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
      <ParkingGrid slots={slots} selectable={false} />
      <div className="card">
        <h3 className="font-medium text-gray-300 mb-3 text-sm">Manual Override</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800">
                {['Slot', 'Current Status', 'Set To'].map(h => (
                  <th key={h} className="pb-2 pr-4 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {slots.map(slot => (
                <tr key={slot.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 pr-4 font-mono font-semibold text-white">{slot.slot_number}</td>
                  <td className="py-2 pr-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs badge-${slot.status}`}>{slot.status}</span>
                  </td>
                  <td className="py-2">
                    <div className="flex gap-1 flex-wrap">
                      {['available', 'occupied', 'reserved', 'maintenance'].map(s => (
                        <button
                          key={s}
                          disabled={loading || slot.status === s}
                          onClick={() => override(slot.id, s)}
                          className={`px-2 py-0.5 rounded text-xs transition-colors disabled:opacity-30
                            ${slot.status === s ? 'bg-green-800 text-green-300' : 'bg-gray-700 hover:bg-gray-600 text-gray-300'}`}
                        >
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

// ── Users Tab ─────────────────────────────────────────────────────────────────
function UsersTab() {
  const [users, setUsers] = useState([])
  const [editId, setEditId] = useState(null)
  const [editForm, setEditForm] = useState({})

  useEffect(() => {
    adminGetUsers().then(r => setUsers(r.data))
  }, [])

  const save = async (id) => {
    try {
      const { data } = await adminUpdateUser(id, editForm)
      setUsers(u => u.map(x => x.id === id ? data : x))
      setEditId(null)
      toast.success('User updated')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Update failed')
    }
  }

  const remove = async (id) => {
    if (!confirm('Delete this user? This cannot be undone.')) return
    try {
      await adminDeleteUser(id)
      setUsers(u => u.filter(x => x.id !== id))
      toast.success('User deleted')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Delete failed')
    }
  }

  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-800">
            {['ID', 'Name', 'Email', 'Phone', 'Active', 'Admin', 'Actions'].map(h => (
              <th key={h} className="pb-3 pr-4 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users.map(u => (
            <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-800/20">
              <td className="py-2.5 pr-4 text-gray-400">{u.id}</td>
              <td className="py-2.5 pr-4">
                {editId === u.id
                  ? <input className="input py-1 text-xs w-28" value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} />
                  : <span className="text-gray-200">{u.name}</span>
                }
              </td>
              <td className="py-2.5 pr-4 text-gray-400 text-xs">{u.email}</td>
              <td className="py-2.5 pr-4">
                {editId === u.id
                  ? <input className="input py-1 text-xs w-28" value={editForm.phone || ''} onChange={e => setEditForm({ ...editForm, phone: e.target.value })} />
                  : <span className="text-gray-400">{u.phone || '—'}</span>
                }
              </td>
              <td className="py-2.5 pr-4">
                {editId === u.id
                  ? <input type="checkbox" checked={editForm.is_active} onChange={e => setEditForm({ ...editForm, is_active: e.target.checked })} />
                  : u.is_active
                    ? <CheckCircle size={15} className="text-green-400" />
                    : <XCircle size={15} className="text-red-400" />
                }
              </td>
              <td className="py-2.5 pr-4">
                {u.is_admin ? <span className="text-yellow-400 text-xs font-semibold">ADMIN</span> : <span className="text-gray-600 text-xs">user</span>}
              </td>
              <td className="py-2.5">
                {editId === u.id ? (
                  <div className="flex gap-1">
                    <button className="btn-primary text-xs py-1 px-2" onClick={() => save(u.id)}>Save</button>
                    <button className="btn-ghost text-xs py-1 px-2" onClick={() => setEditId(null)}>Cancel</button>
                  </div>
                ) : (
                  <div className="flex gap-1">
                    <button className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
                      onClick={() => { setEditId(u.id); setEditForm({ name: u.name, phone: u.phone, is_active: u.is_active }) }}>
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
  )
}

// ── Sessions Tab ──────────────────────────────────────────────────────────────
function SessionsTab() {
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    adminGetSessions({ limit: 100 }).then(r => setSessions(r.data))
  }, [])

  const statusColor = { active: 'text-green-400', completed: 'text-blue-400', denied: 'text-red-400' }

  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-800">
            {['ID', 'Plate', 'Slot', 'Entry', 'Exit', 'Duration', 'Cost', 'Status', 'Image'].map(h => (
              <th key={h} className="pb-3 pr-3 font-medium whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sessions.map(s => (
            <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 text-xs">
              <td className="py-2.5 pr-3 text-gray-500">{s.id}</td>
              <td className="py-2.5 pr-3 font-mono font-semibold text-white">{s.license_plate_raw}</td>
              <td className="py-2.5 pr-3 text-gray-300">{s.slot_id ?? '—'}</td>
              <td className="py-2.5 pr-3 text-gray-400 whitespace-nowrap">{new Date(s.entry_time).toLocaleString()}</td>
              <td className="py-2.5 pr-3 text-gray-400 whitespace-nowrap">{s.exit_time ? new Date(s.exit_time).toLocaleString() : '—'}</td>
              <td className="py-2.5 pr-3 text-gray-400">{s.duration_minutes ? `${Math.round(s.duration_minutes)}m` : '—'}</td>
              <td className="py-2.5 pr-3 text-gray-200">{s.cost != null ? `₹${s.cost.toFixed(2)}` : '—'}</td>
              <td className={`py-2.5 pr-3 font-semibold capitalize ${statusColor[s.status] || 'text-gray-400'}`}>{s.status}</td>
              <td className="py-2.5 pr-3">
                {s.entry_image_path
                  ? <a href={`/images/${s.entry_image_path.split('/').pop()}`} target="_blank" rel="noreferrer"
                       className="text-green-400 hover:underline">View</a>
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Transactions Tab ──────────────────────────────────────────────────────────
function TransactionsTab() {
  const [txns, setTxns] = useState([])

  useEffect(() => {
    adminGetTransactions({ limit: 200 }).then(r => setTxns(r.data))
  }, [])

  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-800">
            {['ID', 'User', 'Amount', 'Type', 'Status', 'Description', 'Date'].map(h => (
              <th key={h} className="pb-3 pr-4 font-medium">{h}</th>
            ))}
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
              <td className="py-2.5 pr-4">
                <span className={`px-1.5 py-0.5 rounded text-xs ${t.status === 'success' ? 'bg-green-900 text-green-400' : 'bg-red-900 text-red-400'}`}>
                  {t.status}
                </span>
              </td>
              <td className="py-2.5 pr-4 text-gray-400 max-w-[200px] truncate">{t.description}</td>
              <td className="py-2.5 pr-4 text-gray-500 whitespace-nowrap">{new Date(t.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main Admin Dashboard ──────────────────────────────────────────────────────
export default function AdminDashboard() {
  const [tab, setTab] = useState('overview')
  const [stats, setStats] = useState(null)
  const [slots, setSlots] = useState([])

  const fetchBase = useCallback(async () => {
    const [statsRes, slotsRes] = await Promise.allSettled([adminGetStats(), getSlots()])
    if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
    if (slotsRes.status === 'fulfilled') setSlots(slotsRes.value.data)
  }, [])

  usePolling(fetchBase, 10000)

  const ENTRY_CAM = import.meta.env.VITE_ENTRY_CAM_URL || ''
  const EXIT_CAM  = import.meta.env.VITE_EXIT_CAM_URL  || ''

  return (
    <div className="min-h-screen bg-gray-950">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield size={22} className="text-green-400" /> Admin Panel
          </h1>
          <button onClick={fetchBase} className="btn-ghost text-sm flex items-center gap-1.5">
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 flex-wrap border-b border-gray-800 pb-0">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-colors rounded-t-lg border-b-2 -mb-px ${
                tab === id
                  ? 'border-green-500 text-green-400 bg-green-500/10'
                  : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === 'overview'     && <OverviewTab stats={stats} entryCam={ENTRY_CAM} exitCam={EXIT_CAM} />}
        {tab === 'slots'        && <SlotsTab slots={slots} onRefresh={fetchBase} />}
        {tab === 'users'        && <UsersTab />}
        {tab === 'sessions'     && <SessionsTab />}
        {tab === 'transactions' && <TransactionsTab />}
      </main>
    </div>
  )
}
