/**
 * Polls GET /health so the UI can say *why* nothing is happening instead of looking idle.
 *
 * status:
 *   'checking'   – first request in flight
 *   'online'     – backend reachable and an LLM key is configured for the selected provider
 *   'no-llm-key' – backend reachable, but live analyses will fail (no key for LLM_PROVIDER)
 *   'offline'    – backend unreachable
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { getHealth } from '../utils/api'

const ONLINE_INTERVAL_MS = 15000
const OFFLINE_INTERVAL_MS = 5000

export function useBackendStatus() {
  const [status, setStatus] = useState('checking')
  const [health, setHealth] = useState(null)
  const timer = useRef(null)
  const tickRef = useRef(null)

  useEffect(() => {
    let cancelled = false

    const tick = async () => {
      clearTimeout(timer.current)
      let next = 'offline'
      let data = null
      try {
        data = await getHealth()
        next = data?.llm_configured === false ? 'no-llm-key' : 'online'
      } catch {
        data = null
      }
      if (cancelled) return
      setHealth(data)
      setStatus(next)
      timer.current = setTimeout(tick, next === 'offline' ? OFFLINE_INTERVAL_MS : ONLINE_INTERVAL_MS)
    }

    tickRef.current = tick
    tick()
    return () => {
      cancelled = true
      clearTimeout(timer.current)
    }
  }, [])

  const recheck = useCallback(() => tickRef.current?.(), [])

  return { status, health, recheck }
}
