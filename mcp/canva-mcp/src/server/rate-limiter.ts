// ─── Types ───────────────────────────────────────────────────────────────────

export interface RateLimiterOptions {
  /** Maximum number of requests allowed per window. Default: 60 */
  maxRequests?: number;
  /** Window size in milliseconds. Default: 60_000 (1 minute) */
  windowMs?: number;
}

// ─── RateLimitError ──────────────────────────────────────────────────────────

export class RateLimitError extends Error {
  public readonly retryAfterMs: number;

  constructor(retryAfterMs: number) {
    super(
      `Rate limit exceeded. Try again in ${Math.ceil(retryAfterMs / 1000)} seconds.`
    );
    this.name = "RateLimitError";
    this.retryAfterMs = retryAfterMs;
  }
}

// ─── SlidingWindowRateLimiter ────────────────────────────────────────────────

/**
 * A sliding-window rate limiter that tracks request timestamps per session.
 *
 * How it works:
 *   - Each call to `checkRateLimit` records a timestamp for the given session.
 *   - Before recording, all timestamps older than `windowMs` are pruned.
 *   - If the remaining count is >= `maxRequests`, the request is rejected.
 *
 * This is an in-memory implementation; it resets on process restart, which is
 * acceptable for a single-instance deployment.
 */
export class SlidingWindowRateLimiter {
  private readonly maxRequests: number;
  private readonly windowMs: number;
  private readonly windows: Map<string, number[]> = new Map();

  constructor(options: RateLimiterOptions = {}) {
    this.maxRequests =
      options.maxRequests ??
      (process.env.RATE_LIMIT_PER_MINUTE
        ? parseInt(process.env.RATE_LIMIT_PER_MINUTE, 10)
        : 60);
    this.windowMs = options.windowMs ?? 60_000;
  }

  /**
   * Check whether a request from `sessionId` is allowed.
   *
   * @returns `true` if the request is within the rate limit.
   * @throws {RateLimitError} if the limit has been exceeded.
   */
  checkRateLimit(sessionId: string): boolean {
    const now = Date.now();
    const cutoff = now - this.windowMs;

    let timestamps = this.windows.get(sessionId);

    if (!timestamps) {
      timestamps = [];
      this.windows.set(sessionId, timestamps);
    }

    // Prune expired entries (timestamps are in ascending order)
    while (timestamps.length > 0 && timestamps[0] <= cutoff) {
      timestamps.shift();
    }

    if (timestamps.length >= this.maxRequests) {
      // Calculate when the oldest request in the current window will expire
      const oldestInWindow = timestamps[0];
      const retryAfterMs = oldestInWindow + this.windowMs - now;
      throw new RateLimitError(retryAfterMs);
    }

    timestamps.push(now);
    return true;
  }

  /**
   * Remove all tracking data for a session (e.g. on disconnect).
   */
  clearSession(sessionId: string): void {
    this.windows.delete(sessionId);
  }

  /**
   * Remove all tracking data (useful for testing).
   */
  reset(): void {
    this.windows.clear();
  }
}

// ─── Factory ─────────────────────────────────────────────────────────────────

/**
 * Creates a rate limiter instance. Reads defaults from environment variables
 * (`RATE_LIMIT_PER_MINUTE`) when no options are provided.
 */
export function createRateLimiter(options?: RateLimiterOptions): SlidingWindowRateLimiter {
  return new SlidingWindowRateLimiter(options);
}
