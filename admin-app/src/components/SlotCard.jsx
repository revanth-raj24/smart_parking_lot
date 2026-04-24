import { Car, Lock, Wrench, CheckCircle } from 'lucide-react'

const STATUS_CONFIG = {
  available:   { label: 'Available',   bg: 'bg-green-900/40 border-green-700',   text: 'text-green-400',  icon: CheckCircle },
  occupied:    { label: 'Occupied',    bg: 'bg-red-900/40   border-red-800',     text: 'text-red-400',    icon: Car },
  reserved:    { label: 'Reserved',    bg: 'bg-yellow-900/40 border-yellow-800', text: 'text-yellow-400', icon: Lock },
  maintenance: { label: 'Maintenance', bg: 'bg-gray-800      border-gray-700',   text: 'text-gray-400',   icon: Wrench },
}

export default function SlotCard({ slot }) {
  const cfg = STATUS_CONFIG[slot.status] || STATUS_CONFIG.maintenance
  const Icon = cfg.icon
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-xl border-2 cursor-default transition-all duration-200 ${cfg.bg}`}
      style={{ width: '80px', height: '120px' }}
      title={`Slot ${slot.slot_number} — ${cfg.label}`}
    >
      <Icon size={28} className={cfg.text} />
      <span className="mt-2 text-sm font-bold text-gray-200">{slot.slot_number}</span>
      <span className={`mt-0.5 text-xs ${cfg.text}`}>{cfg.label}</span>
    </div>
  )
}
