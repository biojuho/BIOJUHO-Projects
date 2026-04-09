import { useState, useEffect, useRef, useCallback, useDeferredValue, useEffectEvent } from 'react';

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
  const reconnectTimerRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  // M-14 fix: ref로 최신 onAlert을 추적하여 stale closure 방지
  const emitAlert = useEffectEvent((alert) => {
    onAlert?.(alert);
  });

  // Use React 19 useDeferredValue to deprioritize chart updates
  const deferredData = useDeferredValue(data);
  const maxBufferedItems = Math.max(maxItems * 4, maxItems);

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
    let disposed = false;

    const scheduleReconnect = () => {
      if (disposed || reconnectTimerRef.current) return;

      const delay = Math.min(1000 * (2 ** reconnectAttemptRef.current), 10000);
      reconnectAttemptRef.current += 1;

      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delay);
    };

    const connect = () => {
      if (disposed) return;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptRef.current = 0;
        setConnected(true);
      };
      ws.onerror = () => setConnected(false);
      ws.onclose = () => {
        setConnected(false);
        if (!disposed) {
          scheduleReconnect();
        }
      };

      ws.onmessage = (event) => {
        let msg;
        try {
          msg = JSON.parse(event.data);
        } catch {
          return;
        }

        if (msg.type === 'history') {
          // Initial history load — set directly
          setData(Array.isArray(msg.data) ? msg.data.slice(-maxItems) : []);
          bufferRef.current = [];
          return;
        }

        // Alert callback (immediate, not throttled)
        if (msg.alerts && msg.alerts.length > 0) {
          emitAlert(msg.alerts[0]);
        }

        // Buffer the reading
        bufferRef.current.push(msg);
        if (bufferRef.current.length > maxBufferedItems) {
          bufferRef.current = bufferRef.current.slice(-maxBufferedItems);
        }

        // Schedule flush if not already scheduled
        if (!timerRef.current) {
          timerRef.current = setTimeout(() => {
            flush();
            timerRef.current = null;
          }, throttleMs);
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [flush, maxBufferedItems, maxItems, throttleMs, url]);

  return {
    data: deferredData,
    connected,
    rawCount: data.length,
    wsRef,
  };
}

export default useThrottledWebSocket;
