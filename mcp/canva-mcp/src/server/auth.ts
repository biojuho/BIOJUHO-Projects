import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Canva OAuth configuration
const CANVA_CLIENT_ID = process.env.CANVA_CLIENT_ID || "";
const CANVA_CLIENT_SECRET = process.env.CANVA_CLIENT_SECRET || "";
const CANVA_REDIRECT_URI = process.env.CANVA_REDIRECT_URI || "http://localhost:8001/auth/callback";
const CANVA_API_BASE = "https://api.canva.com/rest/v1";
const MOCK_TOKEN_PREFIX = "mock_canva_";

export function getCanvaRedirectUri(): string {
  return CANVA_REDIRECT_URI;
}

export function isMockToken(value: string): boolean {
  return value.trim().toLowerCase().startsWith(MOCK_TOKEN_PREFIX);
}

function isUsableSession(
  session: { accessToken: string; refreshToken: string; expiresAt: number } | undefined
): session is { accessToken: string; refreshToken: string; expiresAt: number } {
  if (!session) {
    return false;
  }
  if (
    !session.accessToken ||
    !session.refreshToken ||
    !session.expiresAt ||
    isMockToken(session.accessToken) ||
    isMockToken(session.refreshToken)
  ) {
    return false;
  }
  return true;
}

class PersistentAuthSessions {
  private filePath: string;
  private memoryMap = new Map<string, { accessToken: string; refreshToken: string; expiresAt: number }>();
  private useFileStore: boolean;

  constructor() {
    this.useFileStore = process.env.TOKEN_STORE === "file";
    const __dirname = path.dirname(fileURLToPath(import.meta.url));
    const rootDir = path.resolve(__dirname, "..", "..");
    this.filePath = process.env.TOKEN_STORE_PATH || path.join(rootDir, "data", "tokens.json");

    if (this.useFileStore) {
      // Ensure the parent directory exists
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      this.loadFromFile();
    }
  }

  private loadFromFile() {
    if (!fs.existsSync(this.filePath)) {
      this.memoryMap.clear();
      return;
    }
    try {
      const raw = fs.readFileSync(this.filePath, "utf-8");
      const data = JSON.parse(raw);
      this.memoryMap.clear();
      for (const [key, val] of Object.entries(data)) {
        const session = val as any;
        if (isUsableSession(session)) {
          this.memoryMap.set(key, session);
        }
      }
    } catch (e) {
      console.error("Failed to load tokens from file:", e);
    }
  }

  private saveToFile() {
    if (!this.useFileStore) return;
    try {
      const data: Record<string, any> = {};
      for (const [key, val] of this.memoryMap.entries()) {
        data[key] = val;
      }
      const tmpPath = `${this.filePath}.tmp`;
      fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), "utf-8");
      fs.renameSync(tmpPath, this.filePath);
    } catch (e) {
      console.error("Failed to save tokens to file:", e);
    }
  }

  has(key: string): boolean {
    if (this.useFileStore) {
      this.loadFromFile();
    }
    const session = this.memoryMap.get(key);
    if (!isUsableSession(session)) {
      if (session) {
        this.memoryMap.delete(key);
        this.saveToFile();
      }
      return false;
    }
    return true;
  }

  get(key: string) {
    if (this.useFileStore) {
      this.loadFromFile();
    }
    const session = this.memoryMap.get(key);
    if (!isUsableSession(session)) {
      if (session) {
        this.memoryMap.delete(key);
        this.saveToFile();
      }
      return undefined;
    }
    return session;
  }

  set(key: string, value: { accessToken: string; refreshToken: string; expiresAt: number }) {
    this.memoryMap.set(key, value);
    if (this.useFileStore) {
      this.saveToFile();
    }
    return this;
  }

  delete(key: string): boolean {
    const result = this.memoryMap.delete(key);
    if (this.useFileStore) {
      this.saveToFile();
    }
    return result;
  }
}

// Store OAuth state and tokens in memory (or file if TOKEN_STORE=file)
export const authSessions = new PersistentAuthSessions();
export const pendingAuthStates = new Map<string, { sessionId: string; createdAt: number; codeVerifier: string }>();


// OAuth helper functions with PKCE
export function generateCodeVerifier(): string {
  return crypto.randomBytes(32).toString("base64url");
}

export function generateCodeChallenge(verifier: string): string {
  return crypto.createHash("sha256").update(verifier).digest("base64url");
}

export function generateAuthUrl(state: string, codeVerifier: string): string {
  const codeChallenge = generateCodeChallenge(codeVerifier);
  const scopes = [
    "asset:read",
    "asset:write",
    "comment:read",
    "comment:write",
    "design:content:read",
    "design:content:write",
    "design:meta:read",
    "folder:read",
    "folder:write",
    "profile:read",
  ];

  const params = new URLSearchParams({
    client_id: CANVA_CLIENT_ID,
    response_type: "code",
    redirect_uri: CANVA_REDIRECT_URI,
    state: state,
    scope: scopes.join(" "),
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
  });

  return `https://www.canva.com/api/oauth/authorize?${params.toString()}`;
}

export async function exchangeCodeForToken(code: string, codeVerifier: string): Promise<{
  access_token: string;
  refresh_token: string;
  expires_in: number;
}> {
  const response = await fetch("https://api.canva.com/rest/v1/oauth/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code: code,
      redirect_uri: CANVA_REDIRECT_URI,
      code_verifier: codeVerifier,
      client_id: CANVA_CLIENT_ID,
      client_secret: CANVA_CLIENT_SECRET,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to exchange code for token: ${response.statusText} - ${error}`);
  }

  return response.json();
}

export async function refreshAccessToken(refreshToken: string): Promise<{
  access_token: string;
  expires_in: number;
}> {
  const response = await fetch("https://api.canva.com/rest/v1/oauth/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: CANVA_CLIENT_ID,
      client_secret: CANVA_CLIENT_SECRET,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to refresh token: ${response.statusText} - ${error}`);
  }

  return response.json();
}

export async function getValidAccessToken(sessionId: string): Promise<string> {
  const session = authSessions.get(sessionId);

  if (!session) {
    throw new Error("Not authenticated. Please authenticate with Canva first.");
  }

  // Check if token is expired (with 5 minute buffer)
  if (Date.now() >= session.expiresAt - 5 * 60 * 1000) {
    // Refresh the token
    const tokenData = await refreshAccessToken(session.refreshToken);
    session.accessToken = tokenData.access_token;
    session.expiresAt = Date.now() + tokenData.expires_in * 1000;
    authSessions.set(sessionId, session);
  }

  return session.accessToken;
}

export async function canvaApiRequest(
  sessionId: string,
  endpoint: string,
  method: string = "GET",
  body?: any,
  accessTokenOverride?: string
): Promise<any> {
  const accessToken = accessTokenOverride || await getValidAccessToken(sessionId);

  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };

  if (body && method !== "GET") {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${CANVA_API_BASE}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Canva API error: ${response.status} ${error}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}
