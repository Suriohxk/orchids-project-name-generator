import React from 'react'
import { X, Shield, AlertTriangle } from 'lucide-react'
import { scoreLabel, scoreToColor } from '../utils/colors'

const FEATURE_LABELS = [
  'Packets (log)',
  'Bytes (log)',
  'Src Port Diversity',
  'Dst Port Diversity',
  'Unique Destinations',
  'Unique Sources',
  'TCP Ratio',
  'UDP Ratio',
  'ICMP Ratio',
  'SYN Ratio',
  'Mean PPS',
  'Mean BPS (log)',
  'Is Private IP',
  'Degree',
]

export default function NodeDetail({ node, onClose }) {
  if (!node) return null

  const colors = scoreToColor(node.score)
  const label = scoreLabel(node.score)
  const isSuspicious = node.score >= 0.55

  return (
    <div className="card absolute bottom-4 left-4 w-72 z-10 shadow-2xl border-dark-500">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {isSuspicious
            ? <AlertTriangle size={15} style={{ color: colors.border }} />
            : <Shield size={15} className="text-green-400" />
          }
          <span className="font-mono text-sm font-semibold text-slate-100">{node.id}</span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-300"
        >
          <X size={14} />
        </button>
      </div>

      {/* Score gauge */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-slate-400">Anomaly Score</span>
          <span className="font-mono font-bold" style={{ color: colors.border }}>
            {(node.score * 100).toFixed(1)}%
          </span>
        </div>
        <div className="h-2 rounded-full bg-dark-700 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${node.score * 100}%`,
              background: colors.border,
              boxShadow: `0 0 6px ${colors.border}`,
            }}
          />
        </div>
        <div className="text-right text-xs mt-0.5" style={{ color: colors.border }}>
          {label}
        </div>
      </div>

      {/* Feature breakdown */}
      {node.features && (
        <div className="space-y-1">
          <p className="text-xs text-slate-500 mb-1.5">Feature Vector</p>
          {FEATURE_LABELS.map((label, i) => {
            const val = node.features[i] ?? 0
            const pct = Math.min(val, 1) * 100
            return (
              <div key={i} className="flex items-center gap-2">
                <span className="text-xs text-slate-500 w-36 truncate">{label}</span>
                <div className="flex-1 h-1.5 rounded bg-dark-700 overflow-hidden">
                  <div
                    className="h-full rounded transition-all"
                    style={{
                      width: `${pct}%`,
                      background: val > 0.7 ? '#ef4444' : val > 0.4 ? '#f97316' : '#22c55e',
                    }}
                  />
                </div>
                <span className="text-xs font-mono text-slate-400 w-10 text-right">
                  {val.toFixed(2)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
