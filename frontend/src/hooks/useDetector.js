import { useState, useEffect, useCallback, useRef } from 'react'
import { useWebSocket } from './useWebSocket'

const WS_URL = typeof window !== 'undefined'
  ? `ws://${window.location.host}/ws/live`
  : 'ws://localhost:8000/ws/live'

export function useDetector() {
  const [snapshot, setSnapshot] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [history, setHistory] = useState([])  // [{timestamp, alertCount, nodeCount}]
  const historyRef = useRef([])

  const onMessage = useCallback((data) => {
    if (data.nodes !== undefined) {
      setSnapshot(data)

      // Accumulate history
      const entry = {
        timestamp: data.timestamp,
        alertCount: (data.alerts || []).length,
        nodeCount: data.nodes.length,
        edgeCount: data.edges.length,
        latency: data.latency_ms || 0,
      }
      historyRef.current = [...historyRef.current.slice(-59), entry]
      setHistory([...historyRef.current])

      if (data.alerts?.length > 0) {
        setAlerts(prev => {
          const combined = [...data.alerts, ...prev]
          return combined.slice(0, 100)
        })
      }
    }
  }, [])

  const { connected } = useWebSocket(WS_URL, { onMessage })

  // Poll metrics independently
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch('/api/status')
        if (res.ok) {
          const d = await res.json()
          setMetrics(d.metrics)
        }
      } catch { /* ignore */ }
    }
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 10000)
    return () => clearInterval(interval)
  }, [])

  const updateThreshold = useCallback(async (value) => {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_threshold: value }),
    })
  }, [])

  const clearAlerts = useCallback(() => setAlerts([]), [])

  return { snapshot, alerts, metrics, history, connected, updateThreshold, clearAlerts }
}
