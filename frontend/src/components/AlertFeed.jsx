import React from 'react'
import { AlertTriangle, ShieldAlert, X } from 'lucide-react'
import { scoreLabel, scoreToTailwind, formatTs } from '../utils/colors'

export default function AlertFeed({ alerts, onClear }) {
  if (alerts.length === 0) {
    return (
      <div className="card h-full flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
            <ShieldAlert size={15} className="text-red-400" />
            Alert Feed
          </h3>
          <span className="text-xs text-slate-500">No alerts</span>
        </div>
        <div className="flex-1 flex items-center justify-center text-slate-600 text-sm">
          All clear — no suspicious activity detected
        </div>
      </div>
    )
  }

  return (
    <div className="card h-full flex flex-col overflow-hidden">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <ShieldAlert size={15} className="text-red-400" />
          Alert Feed
          <span className="ml-1 px-1.5 py-0.5 rounded bg-red-950 text-red-400 text-xs font-mono">
            {alerts.length}
          </span>
        </h3>
        <button
          onClick={onClear}
          className="text-slate-500 hover:text-slate-300 transition-colors"
          title="Clear alerts"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
        {alerts.map((alert, idx) => (
          <AlertRow key={`${alert.node_ip}-${alert.timestamp}-${idx}`} alert={alert} />
        ))}
      </div>
    </div>
  )
}

function AlertRow({ alert }) {
  const badge = scoreToTailwind(alert.score)
  const label = scoreLabel(alert.score)
  const isCritical = alert.score >= 0.75

  return (
    <div className={`
      rounded-lg px-3 py-2 border text-xs flex flex-col gap-0.5
      ${isCritical
        ? 'bg-red-950/40 border-red-900/60'
        : 'bg-orange-950/30 border-orange-900/50'
      }
    `}>
      <div className="flex items-center justify-between">
        <span className="font-mono font-semibold text-slate-200">{alert.node_ip}</span>
        <span className={badge}>{label}</span>
      </div>
      <div className="flex items-center gap-1 text-slate-400">
        <AlertTriangle size={10} className={isCritical ? 'text-red-400' : 'text-orange-400'} />
        <span className="truncate">{alert.reason}</span>
      </div>
      <div className="flex items-center justify-between text-slate-500">
        <span>Score: <span className="font-mono text-slate-300">{(alert.score * 100).toFixed(1)}%</span></span>
        <span>{formatTs(alert.timestamp)}</span>
      </div>
    </div>
  )
}
