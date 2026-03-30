import React, { useState, useCallback } from 'react'
import { Brain, Radio } from 'lucide-react'
import { useDetector } from './hooks/useDetector'
import NetworkGraph from './components/NetworkGraph'
import AlertFeed from './components/AlertFeed'
import MetricsBar from './components/MetricsBar'
import TrendChart from './components/TrendChart'
import NodeDetail from './components/NodeDetail'
import ThresholdSlider from './components/ThresholdSlider'
import HighRiskTable from './components/HighRiskTable'

export default function App() {
  const { snapshot, alerts, metrics, history, connected, updateThreshold, clearAlerts } = useDetector()
  const [selectedNode, setSelectedNode] = useState(null)
  const [threshold, setThreshold] = useState(0.35)

  const handleNodeClick = useCallback((nodeId) => {
    const node = snapshot?.nodes?.find(n => n.id === nodeId)
    if (node) setSelectedNode(node)
  }, [snapshot])

  const handleThresholdChange = (val) => {
    setThreshold(val)
    updateThreshold(val)
  }

  return (
    <div className="min-h-screen bg-dark-900 flex flex-col">
      {/* Header */}
      <header className="border-b border-dark-700 px-6 py-3 flex items-center justify-between bg-dark-800 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Brain size={20} className="text-green-400" />
            <span className="font-semibold text-slate-100 text-lg tracking-tight">
              GNN Botnet Detector
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded bg-dark-700 border border-dark-600 text-xs text-slate-400">
            <Radio size={11} className={connected ? 'text-green-400' : 'text-red-400'} />
            GraphSAGE · Real-time
          </div>
        </div>
        <div className="text-xs text-slate-500 font-mono hidden md:block">
          {new Date().toLocaleDateString()} · Network Threat Intelligence
        </div>
      </header>

      {/* Metrics bar */}
      <div className="px-6 py-3 border-b border-dark-700 bg-dark-800/50 flex-shrink-0">
        <MetricsBar snapshot={snapshot} metrics={metrics} connected={connected} />
      </div>

      {/* Main content */}
      <div className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4 min-h-0">

        {/* Left column: graph + threshold + trend */}
        <div className="flex flex-col gap-4 min-h-0">

          {/* Graph */}
          <div className="flex-1 card p-0 overflow-hidden relative min-h-[380px]">
            <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-400 bg-dark-900/80 backdrop-blur px-2 py-1 rounded border border-dark-700">
                Network Graph · {snapshot?.nodes?.length ?? 0} nodes · {snapshot?.edges?.length ?? 0} edges
              </span>
              {snapshot?.alerts?.length > 0 && (
                <span className="text-xs font-semibold text-red-400 bg-red-950/80 backdrop-blur px-2 py-1 rounded border border-red-900 animate-pulse">
                  ⚠ {snapshot.alerts.length} ALERT{snapshot.alerts.length > 1 ? 'S' : ''}
                </span>
              )}
            </div>
            <NetworkGraph snapshot={snapshot} onNodeClick={handleNodeClick} />
            {selectedNode && (
              <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} />
            )}
          </div>

          {/* Bottom row: threshold + trend */}
          <div className="grid grid-cols-1 sm:grid-cols-[200px_1fr] gap-4" style={{ height: 160 }}>
            <ThresholdSlider value={threshold} onChange={handleThresholdChange} />
            <TrendChart history={history} />
          </div>
        </div>

        {/* Right column: alert feed + high-risk table */}
        <div className="flex flex-col gap-4 min-h-[400px] lg:min-h-0">
          <div className="flex-1 min-h-0 overflow-hidden">
            <AlertFeed alerts={alerts} onClear={clearAlerts} />
          </div>
          <HighRiskTable snapshot={snapshot} onNodeClick={handleNodeClick} />
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-dark-700 px-6 py-2 text-xs text-slate-600 flex items-center justify-between flex-shrink-0">
        <span>GraphSAGE · PyTorch Geometric · Scapy · Sliding-Window Inference</span>
        <span>Proof-of-concept — not for production use</span>
      </footer>
    </div>
  )
}
