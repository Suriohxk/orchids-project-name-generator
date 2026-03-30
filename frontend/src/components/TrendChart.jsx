import React, { useState } from 'react'
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'
import { formatTs } from '../utils/colors'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-dark-800 border border-dark-600 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1.5">{formatTs(label)}</p>
      {payload.map(p => (
        <p key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full inline-block flex-shrink-0" style={{ background: p.color }} />
          <span className="text-slate-400">{p.name}:</span>
          <span className="font-mono font-semibold" style={{ color: p.color }}>
            {p.dataKey === 'latency' ? (p.value ?? 0).toFixed(1) + ' ms' : p.value}
          </span>
        </p>
      ))}
    </div>
  )
}

export default function TrendChart({ history }) {
  const [tab, setTab] = useState('traffic')

  if (!history?.length) {
    return (
      <div className="card h-full flex items-center justify-center text-slate-600 text-sm">
        Waiting for data…
      </div>
    )
  }

  return (
    <div className="card h-full flex flex-col overflow-hidden">
      <div className="flex items-center justify-between mb-2 flex-shrink-0">
        <h3 className="text-sm font-semibold text-slate-300">Activity Trend</h3>
        <div className="flex gap-1">
          {['traffic', 'latency'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                tab === t ? 'bg-dark-600 text-slate-200' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {t === 'traffic' ? 'Nodes/Alerts' : 'Latency'}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          {tab === 'traffic' ? (
            <AreaChart data={history} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <defs>
                <linearGradient id="gradNode" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradAlert" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="timestamp" tickFormatter={formatTs}
                tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} iconType="circle" iconSize={7} />
              <Area type="monotone" dataKey="nodeCount" name="Nodes" stroke="#22c55e"
                fill="url(#gradNode)" strokeWidth={1.5} dot={false} />
              <Area type="monotone" dataKey="alertCount" name="Alerts" stroke="#ef4444"
                fill="url(#gradAlert)" strokeWidth={1.5} dot={false} />
            </AreaChart>
          ) : (
            <LineChart data={history} margin={{ top: 4, right: 4, bottom: 0, left: -14 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="timestamp" tickFormatter={formatTs}
                tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false}
                tickFormatter={v => v.toFixed(0) + 'ms'} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} iconType="circle" iconSize={7} />
              <Line type="monotone" dataKey="latency" name="Inference latency" stroke="#818cf8"
                strokeWidth={1.5} dot={false} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
