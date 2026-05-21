import { useCallback, useEffect, useRef, useState } from 'react';
import client, { buildApiUrl } from '../services/api';

const TERMINAL_STATUSES = new Set(['succeeded', 'failed']);

function isTerminal(job) {
  return TERMINAL_STATUSES.has(job?.status);
}

function jobError(job) {
  return new Error(job?.error || job?.message || 'Job failed');
}

export function useJobProgress({ intervalMs = 1500, onSuccess, onError } = {}) {
  const [job, setJob] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const promiseRef = useRef(null);
  const callbacksRef = useRef({ onSuccess, onError });

  useEffect(() => {
    callbacksRef.current = { onSuccess, onError };
  }, [onError, onSuccess]);

  const clearJob = useCallback(() => {
    setJob(null);
    setJobId(null);
    setIsRunning(false);
    promiseRef.current = null;
  }, []);

  const watchJob = useCallback((nextJob) => {
    if (!nextJob?.id) {
      return Promise.reject(new Error('Job id is required'));
    }

    setJob(nextJob);

    if (isTerminal(nextJob)) {
      setJobId(null);
      setIsRunning(false);
      if (nextJob.status === 'succeeded') {
        return Promise.resolve(nextJob.result || {});
      }
      return Promise.reject(jobError(nextJob));
    }

    setJobId(nextJob.id);
    setIsRunning(true);

    return new Promise((resolve, reject) => {
      promiseRef.current = { jobId: nextJob.id, resolve, reject };
    });
  }, []);

  useEffect(() => {
    if (!jobId) return undefined;

    let isCancelled = false;
    let pollingTimer;
    let eventSource;
    let isPolling = false;

    const settleSuccess = (snapshot) => {
      setIsRunning(false);
      setJobId(null);
      callbacksRef.current.onSuccess?.(snapshot.result || {}, snapshot);

      const pending = promiseRef.current;
      if (pending?.jobId === jobId) {
        pending.resolve(snapshot.result || {});
        promiseRef.current = null;
      }
    };

    const settleError = (error, snapshot) => {
      setIsRunning(false);
      setJobId(null);
      callbacksRef.current.onError?.(error, snapshot);

      const pending = promiseRef.current;
      if (pending?.jobId === jobId) {
        pending.reject(error);
        promiseRef.current = null;
      }
    };

    const handleSnapshot = (snapshot) => {
      if (isCancelled) return;

      setJob(snapshot);
      if (snapshot.status === 'succeeded') {
        eventSource?.close();
        settleSuccess(snapshot);
        return;
      }

      if (snapshot.status === 'failed') {
        eventSource?.close();
        settleError(jobError(snapshot), snapshot);
      }
    };

    const startPolling = () => {
      if (isPolling || isCancelled) return;
      isPolling = true;

      const poll = async () => {
        try {
          const response = await client.get(`/jobs/${jobId}`, { timeout: 10_000 });
          handleSnapshot(response.data);

          if (!isCancelled && !isTerminal(response.data)) {
            pollingTimer = window.setTimeout(poll, intervalMs);
          }
        } catch (error) {
          if (!isCancelled) {
            settleError(error);
          }
        }
      };

      poll();
    };

    if (typeof EventSource !== 'undefined') {
      try {
        eventSource = new EventSource(buildApiUrl(`/jobs/${jobId}/events`));
        eventSource.onmessage = (event) => {
          handleSnapshot(JSON.parse(event.data));
        };
        eventSource.onerror = () => {
          eventSource?.close();
          startPolling();
        };
      } catch {
        startPolling();
      }
    } else {
      startPolling();
    }

    return () => {
      isCancelled = true;
      eventSource?.close();
      window.clearTimeout(pollingTimer);
    };
  }, [intervalMs, jobId]);

  return {
    job,
    isRunning,
    watchJob,
    clearJob,
  };
}
