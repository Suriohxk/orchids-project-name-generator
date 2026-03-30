import React from 'react'
import { Skull, ChevronRight } from 'lucide-react'
import { scoreLabel, scoreToTailwind } from '../utils/colors'

export default function HighRiskTable({ snapshot, onNodeClick }) {
  const highRisk = (snapshot?.nodes ?? [])
    .filter(n => n.score >= 0.35)
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)

  if (!highRisk.length) {
    return (
      <div className="card flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <Skull size={14} className="text-slate-500" />
          Risk Table
        </h3>
        <div className="text-xs text-slate-600 text-center py-3">No elevated-risk nodes</div>
      </div>
    )
  }

  return (
    <div className="card flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
        <Skull size={14} className="text-orange-400" />
        Top Risk Nodes
        <span className="ml-auto text-xs text-slate-500 font-normal">click to inspect</span>
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-dark-700">
              <th className="text-left py-1 pr-2 font-medium">IP Address</th>
              <th className="text-right py-1 pr-2 font-medium">Score</th>
              <th className="text-right py-1 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {highRisk.map((node) => (
              <tr
                key={node.id}
                className="border-b border-dark-700/50 cursor-pointer hover:bg-dark-700/30 transition-colors"
                onClick={() => onNodeClick?.(node.id)}
              >
                <td className="py-1.5 pr-2">
                  <div className="flex items-center gap-1.5">
                    <div
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{
                        background: node.score >= 0.75 ? '#7f1d1d' : node.score >= 0.55 ? '#7c2d12' : '#713f12',
                        border: `1.5px solid ${node.score >= 0.75 ? '#ef4444' : node.score >= 0.55 ? '#f97316' : '#eab308'}`,
                      }}
                    />
                    <span className="font-mono text-slate-200 truncate max-w-[110px]">{node.id}</span>
                  </div>
                </td>
                <td className="py-1.5 pr-2 text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    <div className="w-14 h-1.5 rounded bg-dark-700 overflow-hidden">
                      <div
                        className="h-full rounded transition-all"
                        style={{
                          width: `${node.score * 100}%`,
                          background: node.score >= 0.75 ? '#ef4444' : node.score >= 0.55 ? '#f97316' : '#eab308',
                        }}
                      />
                    </div>
                    <span className="font-mono text-slate-300 w-9 text-right">{(node.score * 100).toFixed(0)}%</span>
                  </div>
                </td>
                <td className="py-1.5 text-right">
                  <span className={scoreToTailwind(node.score)}>{scoreLabel(node.score)}</span>
                </td>
                <td className="py-1.5 pl-1">
                  <ChevronRight size={10} className="text-slate-600" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
