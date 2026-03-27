import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface TokenData {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export interface TokenStore {
  get(sessionId: string): Promise<TokenData | undefined>;
  set(sessionId: string, tokens: TokenData): Promise<void>;
  delete(sessionId: string): Promise<void>;
}

// ─── InMemoryTokenStore ──────────────────────────────────────────────────────

export class InMemoryTokenStore implements TokenStore {
  private readonly store = new Map<string, TokenData>();

  async get(sessionId: string): Promise<TokenData | undefined> {
    return this.store.get(sessionId);
  }

  async set(sessionId: string, tokens: TokenData): Promise<void> {
    this.store.set(sessionId, tokens);
  }

  async delete(sessionId: string): Promise<void> {
    this.store.delete(sessionId);
  }
}

// ─── FileTokenStore ──────────────────────────────────────────────────────────

/**
 * Persists token data to a JSON file on disk.
 * Suitable for single-instance production deployments where Redis is not
 * available. The file is read on every `get` and written atomically on every
 * `set`/`delete` to stay consistent across restarts.
 */
export class FileTokenStore implements TokenStore {
  private readonly filePath: string;

  constructor(filePath?: string) {
    if (filePath) {
      this.filePath = filePath;
    } else {
      const __dirname = path.dirname(fileURLToPath(import.meta.url));
      const rootDir = path.resolve(__dirname, "..", "..");
      this.filePath = path.join(rootDir, "data", "tokens.json");
    }

    // Ensure the parent directory exists
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  private readAll(): Record<string, TokenData> {
    if (!fs.existsSync(this.filePath)) {
      return {};
    }
    try {
      const raw = fs.readFileSync(this.filePath, "utf-8");
      return JSON.parse(raw) as Record<string, TokenData>;
    } catch {
      // Corrupt or empty file — start fresh
      return {};
    }
  }

  private writeAll(data: Record<string, TokenData>): void {
    // Atomic write: write to a temp file first, then rename
    const tmpPath = `${this.filePath}.tmp`;
    fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), "utf-8");
    fs.renameSync(tmpPath, this.filePath);
  }

  async get(sessionId: string): Promise<TokenData | undefined> {
    const all = this.readAll();
    return all[sessionId];
  }

  async set(sessionId: string, tokens: TokenData): Promise<void> {
    const all = this.readAll();
    all[sessionId] = tokens;
    this.writeAll(all);
  }

  async delete(sessionId: string): Promise<void> {
    const all = this.readAll();
    if (sessionId in all) {
      delete all[sessionId];
      this.writeAll(all);
    }
  }
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export type TokenStoreType = "memory" | "file";

/**
 * Creates the appropriate TokenStore implementation based on the requested
 * type. Reads from `TOKEN_STORE` env var when no argument is supplied.
 *
 * @param type - `'memory'` for development (default) or `'file'` for simple
 *               persistent storage.
 */
export function createTokenStore(type?: TokenStoreType): TokenStore {
  const resolved = type ?? (process.env.TOKEN_STORE as TokenStoreType | undefined) ?? "memory";

  switch (resolved) {
    case "file":
      return new FileTokenStore();
    case "memory":
      return new InMemoryTokenStore();
    default:
      console.warn(
        `Unknown TOKEN_STORE type "${String(resolved)}", falling back to in-memory store.`
      );
      return new InMemoryTokenStore();
  }
}
