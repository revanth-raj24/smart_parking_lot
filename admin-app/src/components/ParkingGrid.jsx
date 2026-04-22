import SlotCard from './SlotCard'

export default function ParkingGrid({ slots }) {
  const available = slots.filter(s => s.status === 'available').length
  const occupied  = slots.filter(s => s.status === 'occupied').length
  const reserved  = slots.filter(s => s.status === 'reserved').length

  return (
    <div>
      <div className="flex gap-4 mb-4 text-sm flex-wrap">
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
      <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        {slots.map(slot => <SlotCard key={slot.id} slot={slot} />)}
      </div>
    </div>
  )
}
