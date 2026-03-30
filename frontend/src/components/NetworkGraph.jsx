import React, { useEffect, useRef } from 'react'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import { scoreToColor } from '../utils/colors'

const OPTIONS = {
  physics: {
    stabilization: { enabled: true, iterations: 100 },
    barnesHut: {
      gravitationalConstant: -3000,
      springConstant: 0.04,
      springLength: 100,
      damping: 0.3,
    },
  },
  nodes: {
    shape: 'dot',
    size: 14,
    borderWidth: 2,
    font: { size: 11, color: '#cbd5e1', face: 'JetBrains Mono' },
    chosen: {
      node: (values) => {
        values.size += 6
        values.borderWidth += 2
      },
    },
  },
  edges: {
    width: 1,
    color: { color: '#334155', highlight: '#64748b', hover: '#64748b' },
    arrows: { to: { enabled: true, scaleFactor: 0.4 } },
    smooth: { type: 'dynamic' },
  },
  interaction: {
    hover: true,
    tooltipDelay: 100,
    hideEdgesOnDrag: true,
  },
  layout: { improvedLayout: false },
}

const LEGEND_ITEMS = [
  { bg: '#0f2d1a', border: '#22c55e', label: 'Benign' },
  { bg: '#713f12', border: '#eab308', label: 'Elevated' },
  { bg: '#7c2d12', border: '#f97316', label: 'Suspicious' },
  { bg: '#7f1d1d', border: '#ef4444', label: 'Critical' },
]

function GraphLegend() {
  return (
    <div className="absolute bottom-3 right-3 z-10 bg-dark-900/90 backdrop-blur border border-dark-600 rounded-lg px-3 py-2.5 flex flex-col gap-1.5 pointer-events-none">
      <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-0.5">Node Risk</span>
      {LEGEND_ITEMS.map(({ bg, border, label }) => (
        <div key={label} className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full flex-shrink-0"
            style={{ background: bg, border: `2px solid ${border}`, boxShadow: label === 'Critical' ? `0 0 5px ${border}` : 'none' }} />
          <span className="text-[11px] text-slate-400">{label}</span>
        </div>
      ))}
      <div className="border-t border-dark-700 mt-1 pt-1.5 flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <div className="w-5 h-0.5 rounded" style={{ background: '#7f1d1d' }} />
          <span className="text-[10px] text-slate-500">SYN scan edge</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-5 h-0.5 rounded" style={{ background: '#1e3a5f' }} />
          <span className="text-[10px] text-slate-500">Normal flow</span>
        </div>
      </div>
    </div>
  )
}

export default function NetworkGraph({ snapshot, onNodeClick }) {
  const containerRef = useRef(null)
  const networkRef = useRef(null)
  const nodesDs = useRef(new DataSet())
  const edgesDs = useRef(new DataSet())

  // Initialize network once
  useEffect(() => {
    if (!containerRef.current) return
    const net = new Network(
      containerRef.current,
      { nodes: nodesDs.current, edges: edgesDs.current },
      OPTIONS
    )
    net.on('click', ({ nodes }) => {
      if (nodes.length > 0) {
        onNodeClick?.(nodes[0])
      }
    })
    networkRef.current = net
    return () => net.destroy()
  }, []) // eslint-disable-line

  // Update data when snapshot changes
  useEffect(() => {
    if (!snapshot) return

    const newNodes = snapshot.nodes.map((n) => {
      const colors = scoreToColor(n.score)
      const size = 10 + Math.min(n.score * 20, 18)
      const suspicious = n.score >= 0.55
      return {
        id: n.id,
        label: suspicious ? n.id : (n.id.length > 12 ? n.id.slice(-8) : n.id),
        title: `IP: ${n.id}\nScore: ${(n.score * 100).toFixed(1)}%`,
        color: {
          background: colors.background,
          border: colors.border,
          highlight: { background: colors.background, border: '#f8fafc' },
        },
        font: { color: colors.font, size: suspicious ? 13 : 10 },
        size: suspicious ? size + 4 : size,
        borderWidth: suspicious ? 3 : 1.5,
        shadow: suspicious ? { enabled: true, color: colors.border, size: 12 } : false,
      }
    })

    const newEdges = snapshot.edges.map((e, i) => ({
      id: `${e.source}-${e.target}-${i}`,
      from: e.source,
      to: e.target,
      width: Math.min(1 + (e.features?.[0] || 0) * 0.5, 4),
      color: {
        color: e.features?.[4] > 0 ? '#7f1d1d' : '#1e3a5f',
        opacity: 0.7,
      },
    }))

    // Batch update
    const existingNodeIds = new Set(nodesDs.current.getIds())
    const existingEdgeIds = new Set(edgesDs.current.getIds())

    const nodesToAdd = newNodes.filter(n => !existingNodeIds.has(n.id))
    const nodesToUpdate = newNodes.filter(n => existingNodeIds.has(n.id))
    const nodeIdsToRemove = [...existingNodeIds].filter(id => !newNodes.find(n => n.id === id))

    const edgesToAdd = newEdges.filter(e => !existingEdgeIds.has(e.id))
    const edgesToUpdate = newEdges.filter(e => existingEdgeIds.has(e.id))
    const edgeIdsToRemove = [...existingEdgeIds].filter(id => !newEdges.find(e => e.id === id))

    nodesDs.current.remove(nodeIdsToRemove)
    nodesDs.current.add(nodesToAdd)
    nodesDs.current.update(nodesToUpdate)

    edgesDs.current.remove(edgeIdsToRemove)
    edgesDs.current.add(edgesToAdd)
    edgesDs.current.update(edgesToUpdate)
  }, [snapshot])

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" style={{ background: '#030712' }} />
      <GraphLegend />
    </div>
  )
}
