import { useState, useEffect } from 'react'
import { Camera, RefreshCw, AlertTriangle } from 'lucide-react'

export default function CameraFeed({ label, url }) {
  const [imgSrc, setImgSrc] = useState('')
  const [error, setError] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!url) return
    setError(false)
    setImgSrc(`${url}?t=${Date.now()}`)
  }, [url, refreshKey])

  const refresh = () => setRefreshKey(k => k + 1)

  // Auto-refresh every 5s
  useEffect(() => {
    if (!url) return
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [url])

  return (
    <div className="card h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Camera size={16} className="text-green-400" />
          <span className="font-medium text-gray-200 text-sm">{label}</span>
        </div>
        <button onClick={refresh} className="text-gray-500 hover:text-green-400 transition-colors p-1 rounded">
          <RefreshCw size={14} />
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center bg-black rounded-lg overflow-hidden min-h-[180px]">
        {!url ? (
          <div className="text-center text-gray-600 p-4">
            <Camera size={32} className="mx-auto mb-2 opacity-40" />
            <p className="text-xs">Camera URL not configured</p>
          </div>
        ) : error ? (
          <div className="text-center text-gray-600 p-4">
            <AlertTriangle size={32} className="mx-auto mb-2 text-yellow-600" />
            <p className="text-xs">Camera offline</p>
            <button onClick={refresh} className="mt-2 text-xs text-green-400 hover:underline">Retry</button>
          </div>
        ) : (
          <img
            src={imgSrc}
            alt={label}
            className="w-full h-full object-cover"
            onError={() => setError(true)}
            onLoad={() => setError(false)}
          />
        )}
      </div>

      <div className="mt-2 flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${error || !url ? 'bg-red-500' : 'bg-green-500 animate-pulse'}`} />
        <span className="text-xs text-gray-500">{error || !url ? 'Offline' : 'Live'}</span>
      </div>
    </div>
  )
}
