import SlotCard from './SlotCard'

const PARKING_LAYOUT = [
  { label: 'Row 1', slots: ['P1', 'P2', 'P3', 'P4'] },
  'PATH',
  { label: 'Row 2', slots: ['P8', 'P7', 'P6', 'P5'] },
  'PATH',
  { label: 'Row 3', slots: ['P9', 'P10', 'P11'] },
]

export default function ParkingGrid({ slots }) {
  const slotMap = Object.fromEntries(slots.map(s => [s.slot_number, s]))
  const available = slots.filter(s => s.status === 'available').length
  const occupied  = slots.filter(s => s.status === 'occupied').length
  const reserved  = slots.filter(s => s.status === 'reserved').length

  return (
    <div>
      <div className="flex gap-4 mb-6 text-sm flex-wrap">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
          <span className="text-gray-300">Available <b className="text-green-400">{available}</b></span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
          <span className="text-gray-300">Occupied <b className="text-red-400">{occupied}</b></span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-500 inline-block" />
          <span className="text-gray-300">Reserved <b className="text-yellow-400">{reserved}</b></span>
        </span>
      </div>

      <div className="flex flex-col gap-3">
        {PARKING_LAYOUT.map((row, index) => {
          if (row === 'PATH') {
            return (
              <div key={index} className="flex items-center my-1">
                <div className="flex-1 h-9 bg-gray-800/80 rounded-lg border border-gray-700/50 flex items-center justify-center">
                  <span className="text-xs text-gray-500 font-medium tracking-widest uppercase">— Pathway —</span>
                </div>
              </div>
            )
          }
          return (
            <div key={index}>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{row.label}</span>
                <div className="flex-1 h-px bg-gray-800" />
              </div>
              <div className="flex flex-wrap justify-center gap-4">
                {row.slots.map(slotId => {
                  const slot = slotMap[slotId]
                  return slot ? <SlotCard key={slotId} slot={slot} /> : null
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
