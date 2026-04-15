import { useState, useEffect, useCallback, useRef } from 'react'

export function useFetch(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const abortControllerRef = useRef(null)
  const requestIdRef = useRef(0)

  const runFetch = useCallback(async () => {
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId

    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)

    try {
      const response = await fetch(url, {
        cache: 'no-store',
        signal: controller.signal,
      })

      if (response.ok === false) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      const payload = await response.json()
      if (requestId !== requestIdRef.current || controller.signal.aborted) {
        return false
      }

      setData(payload)
      setError(null)
      return true
    } catch (e) {
      if (controller.signal.aborted || e.name === 'AbortError') {
        return false
      }

      if (requestId === requestIdRef.current) {
        setError(e.message)
      }
      return false
    } finally {
      if (requestId === requestIdRef.current && !controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [url])

  useEffect(() => {
    void runFetch()

    return () => {
      requestIdRef.current += 1
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [runFetch])

  return { data, loading, error, refetch: runFetch }
}
