import React, { useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'

export default function ThresholdSlider({ value = 0.55, onChange }) {
  const [local, setLocal] = useState(value)

  const handleChange = (e) => {
    const v = parseFloat(e.target.value)
    setLocal(v)
  }

  const handleCommit = (e) => {
    const v = parseFloat(e.target.value)
    onChange?.(v)
  }

  return (
    <div className="flex items-center gap-3 card py-2.5">
      <SlidersHorizontal size={14} className="text-slate-400 flex-shrink-0" />
      <span className="text-xs text-slate-400">Alert Threshold</span>
      <input
        type="range"
        min="0.1"
        max="0.9"
        step="0.05"
        value={local}
        onChange={handleChange}
        onMouseUp={handleCommit}
        onTouchEnd={handleCommit}
        className="flex-1 accent-green-500 h-1 cursor-pointer"
      />
      <span className="font-mono text-sm font-semibold text-green-400 w-10 text-right">
        {(local * 100).toFixed(0)}%
      </span>
    </div>
  )
}
