import React from 'react'
import { Activity, Network, AlertTriangle, Clock, Cpu } from 'lucide-react'
import { formatNumber } from '../utils/colors'

function Stat({ icon: Icon, label, value, color = 'text-slate-200' }) {
  return (
    <div className="stat-card min-w-[100px]">
      <div className="flex items-center gap-1.5 text-slate-500 text-xs">
        <Icon size={12} />
        <span>{label}</span>
      </div>
      <div className={`font-mono font-semibold text-lg ${color}`}>
        {value ?? '—'}
      </div>
    </div>
  )
}

export default function MetricsBar({ snapshot, metrics, connected }) {
  const nodeCount = snapshot?.nodes?.length ?? 0
  const edgeCount = snapshot?.edges?.length ?? 0
  const alertCount = snapshot?.alerts?.length ?? 0
  const latency = snapshot?.latency_ms ? snapshot.latency_ms.toFixed(1) + ' ms' : '—'
  const totalAlerts = metrics?.total_alerts ?? 0
  const totalSnaps = metrics?.total_snapshots ?? 0
  const avgLatency = metrics?.avg_latency_ms ? metrics.avg_latency_ms.toFixed(0) + ' ms' : '—'

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Connection badge */}
      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold
        ${connected
          ? 'bg-green-950 border-green-800 text-green-400'
          : 'bg-red-950 border-red-800 text-red-400'
        }`}>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
        {connected ? 'LIVE' : 'OFFLINE'}
      </div>

      <Stat icon={Network} label="Nodes" value={formatNumber(nodeCount)} />
      <Stat icon={Activity} label="Edges" value={formatNumber(edgeCount)} />
      <Stat
        icon={AlertTriangle}
        label="Alerts"
        value={alertCount > 0 ? String(alertCount) : '0'}
        color={alertCount > 0 ? 'text-red-400' : 'text-slate-200'}
      />
      <Stat icon={Clock} label="Latency" value={latency} />
      <Stat icon={Cpu} label="Snapshots" value={formatNumber(totalSnaps)} />
    </div>
  )
}
