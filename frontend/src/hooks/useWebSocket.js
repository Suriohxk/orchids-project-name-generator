import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket(url, { onMessage, reconnectDelay = 3000 } = {}) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const timerRef = useRef(null)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      if (timerRef.current) clearTimeout(timerRef.current)
    }

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        if (data.type !== 'ping') {
          onMessageRef.current?.(data)
        }
      } catch {
        // ignore non-JSON
      }
    }

    ws.onclose = () => {
      setConnected(false)
      timerRef.current = setTimeout(connect, reconnectDelay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [url, reconnectDelay])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [connect])

  return { connected }
}
