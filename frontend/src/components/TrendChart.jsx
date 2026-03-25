import React from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'
import { formatTs } from '../utils/colors'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-dark-800 border border-dark-600 rounded-lg px-3 py-2 text-xs">
      <p className="text-slate-400 mb-1">{formatTs(label)}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <span className="font-mono font-semibold">{p.value}</span>
        </p>
      ))}
    </div>
  )
}

export default function TrendChart({ history }) {
  if (!history?.length) {
    return (
      <div className="card h-full flex items-center justify-center text-slate-600 text-sm">
        Waiting for data…
      </div>
    )
  }

  return (
    <div className="card h-full flex flex-col">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">Activity Trend</h3>
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
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
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatTs}
              tick={{ fill: '#475569', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: '#475569', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 11, color: '#94a3b8' }}
              iconType="circle"
              iconSize={8}
            />
            <Area
              type="monotone"
              dataKey="nodeCount"
              name="Nodes"
              stroke="#22c55e"
              fill="url(#gradNode)"
              strokeWidth={1.5}
              dot={false}
            />
            <Area
              type="monotone"
              dataKey="alertCount"
              name="Alerts"
              stroke="#ef4444"
              fill="url(#gradAlert)"
              strokeWidth={1.5}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
