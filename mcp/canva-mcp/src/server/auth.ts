import crypto from "node:crypto";

// Canva OAuth configuration
const CANVA_CLIENT_ID = process.env.CANVA_CLIENT_ID || "";
const CANVA_CLIENT_SECRET = process.env.CANVA_CLIENT_SECRET || "";
const CANVA_REDIRECT_URI = process.env.CANVA_REDIRECT_URI || "http://127.0.0.1:8001/auth/callback";
const CANVA_API_BASE = "https://api.canva.com/rest/v1";

// Store OAuth state and tokens in memory (use database in production)
export const authSessions = new Map<string, { accessToken: string; refreshToken: string; expiresAt: number }>();
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
