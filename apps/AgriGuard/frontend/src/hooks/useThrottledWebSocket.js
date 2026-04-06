import { useState, useEffect, useRef, useCallback, useDeferredValue } from 'react';

/**
 * useThrottledWebSocket — WebSocket messages throttled to prevent React re-render storms.
 *
 * At 100x scale (10,000 messages/sec), unthrottled setState calls would freeze the UI.
 * This hook buffers incoming messages and flushes them at a controlled rate.
 *
 * @param {string} url - WebSocket URL
 * @param {Object} options
 * @param {number} options.throttleMs - Flush interval in ms (default: 150)
 * @param {number} options.maxItems - Max items to keep in state (default: 200)
 * @param {function} options.onAlert - Callback for alert messages
 * @returns {{ data: Array, connected: boolean, rawCount: number }}
 */
export function useThrottledWebSocket(url, options = {}) {
  const { throttleMs = 150, maxItems = 200, onAlert } = options;
  const [data, setData] = useState([]);
  const [connected, setConnected] = useState(false);
  const bufferRef = useRef([]);
  const timerRef = useRef(null);
  const wsRef = useRef(null);
  // M-14 fix: ref로 최신 onAlert을 추적하여 stale closure 방지
  const onAlertRef = useRef(onAlert);
  onAlertRef.current = onAlert;

  // Use React 19 useDeferredValue to deprioritize chart updates
  const deferredData = useDeferredValue(data);

  const flush = useCallback(() => {
    if (bufferRef.current.length === 0) return;
    setData((prev) => {
      const merged = [...prev, ...bufferRef.current];
      bufferRef.current = [];
      // Keep only the most recent maxItems
      return merged.slice(-maxItems);
    });
  }, [maxItems]);

  useEffect(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === 'history') {
        // Initial history load — set directly
        setData(msg.data.slice(-maxItems));
        return;
      }

      // Alert callback (immediate, not throttled)
      if (onAlertRef.current && msg.alerts && msg.alerts.length > 0) {
        onAlertRef.current(msg.alerts[0]);
      }

      // Buffer the reading
      bufferRef.current.push(msg);

      // Schedule flush if not already scheduled
      if (!timerRef.current) {
        timerRef.current = setTimeout(() => {
          flush();
          timerRef.current = null;
        }, throttleMs);
      }
    };

    return () => {
      ws.close();
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, throttleMs, maxItems]);

  return {
    data: deferredData,
    connected,
    rawCount: data.length,
    wsRef,
  };
}

export default useThrottledWebSocket;
