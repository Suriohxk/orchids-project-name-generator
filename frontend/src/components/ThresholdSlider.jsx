import React, { useState, useEffect } from 'react'
import { SlidersHorizontal } from 'lucide-react'

export default function ThresholdSlider({ value = 0.55, onChange }) {
  const [local, setLocal] = useState(value)

  // Keep in sync when parent changes (e.g. on initial load from backend)
  useEffect(() => { setLocal(value) }, [value])

  const handleChange = (e) => {
    setLocal(parseFloat(e.target.value))
  }

  const handleCommit = (e) => {
    const v = parseFloat(e.target.value)
    setLocal(v)
    onChange?.(v)
  }

  const color = local >= 0.75 ? 'text-red-400' : local >= 0.55 ? 'text-orange-400' : 'text-green-400'
  const accentClass = local >= 0.75 ? 'accent-red-500' : local >= 0.55 ? 'accent-orange-500' : 'accent-green-500'

  return (
    <div className="card flex flex-col gap-2 justify-center">
      <div className="flex items-center gap-2">
        <SlidersHorizontal size={13} className="text-slate-400 flex-shrink-0" />
        <span className="text-xs text-slate-400 flex-1">Alert Threshold</span>
        <span className={`font-mono text-sm font-bold ${color}`}>
          {(local * 100).toFixed(0)}%
        </span>
      </div>
      <input
        type="range"
        min="0.1"
        max="0.9"
        step="0.05"
        value={local}
        onChange={handleChange}
        onMouseUp={handleCommit}
        onTouchEnd={handleCommit}
        className={`w-full ${accentClass} h-1 cursor-pointer`}
      />
      <div className="flex justify-between text-[10px] text-slate-600 font-mono">
        <span>Sensitive</span>
        <span>Strict</span>
      </div>
    </div>
  )
}
