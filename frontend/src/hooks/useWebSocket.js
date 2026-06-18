import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * OmniRoute Analytics — WebSocket Hook
 * Manages persistent WebSocket connection with auto-reconnect.
 */
export default function useWebSocket(url = 'ws://localhost:8000/ws/live') {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const [initialState, setInitialState] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const reconnectAttempts = useRef(0)
  const MAX_RECONNECT = 10

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        setIsConnected(true)
        reconnectAttempts.current = 0
        console.log('[WS] Connected to', url)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'initial_state') {
            setInitialState(data)
          } else {
            setLastMessage(data)
          }
        } catch (e) {
          console.error('[WS] Parse error:', e)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        console.log('[WS] Disconnected')
        // Auto-reconnect with exponential backoff
        if (reconnectAttempts.current < MAX_RECONNECT) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          reconnectTimer.current = setTimeout(() => {
            reconnectAttempts.current++
            connect()
          }, delay)
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
      }

      wsRef.current = ws
    } catch (err) {
      console.error('[WS] Connection failed:', err)
    }
  }, [url])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const sendMessage = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  return { isConnected, lastMessage, initialState, sendMessage }
}
