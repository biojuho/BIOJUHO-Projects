import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STDIO_ENTRY = "dist/server/stdio.js";

let nextPort = 19100;

async function withCanvaClient(envOverrides, callback) {
  const port = String(nextPort++);
  const env = {
    ...process.env,
    PORT: port,
    CANVA_REDIRECT_URI: `http://127.0.0.1:${port}/auth/callback`,
    CANVA_MCP_SESSION_ID: "test-session",
    CANVA_MCP_QUIET_AUTH_ERRORS: "true",
    ...envOverrides,
  };
  const transport = new StdioClientTransport({
    command: "node",
    args: [STDIO_ENTRY],
    cwd: ROOT_DIR,
    env,
  });
  const client = new Client({ name: "canva-mcp-stdio-test", version: "1.0.0" });
  await client.connect(transport);

  try {
    return await callback(client, env);
  } finally {
    await client.close();
  }
}

test("stdio server exposes auth helper tools and creates an OAuth URL", async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "canva-mcp-auth-"));
  const tokenPath = path.join(tmpDir, "tokens.json");

  try {
    const result = await withCanvaClient(
      { TOKEN_STORE: "file", TOKEN_STORE_PATH: tokenPath },
      async (client) => {
        const tools = await client.listTools();
        const status = await client.callTool({ name: "auth-status", arguments: {} });
        const auth = await client.callTool({ name: "authenticate", arguments: {} });
        const authText = auth.content?.[0]?.text ?? "";

        return {
          toolNames: tools.tools.map((tool) => tool.name),
          authenticated: status.structuredContent?.authenticated,
          callbackAvailable: status.structuredContent?.callback?.available,
          authText,
        };
      }
    );

    assert.equal(result.toolNames.includes("auth-status"), true);
    assert.equal(result.toolNames.includes("authenticate"), true);
    assert.equal(result.toolNames.includes("search-designs"), true);
    assert.equal(result.authenticated, false);
    assert.equal(result.callbackAvailable, true);
    assert.match(result.authText, /https:\/\/www\.canva\.com\/api\/oauth\/authorize/);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test("stdio server continues when the OAuth callback port is already in use", async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "canva-mcp-port-"));
  const tokenPath = path.join(tmpDir, "tokens.json");

  try {
    const status = await withCanvaClient(
      {
        PORT: "19199",
        CANVA_REDIRECT_URI: "http://127.0.0.1:19199/auth/callback",
        TOKEN_STORE: "file",
        TOKEN_STORE_PATH: tokenPath,
      },
      async (firstClient) => {
        const firstStatus = await firstClient.callTool({ name: "auth-status", arguments: {} });
        assert.equal(firstStatus.structuredContent?.callback?.available, true);

        return withCanvaClient(
          {
            PORT: "19199",
            CANVA_REDIRECT_URI: "http://127.0.0.1:19199/auth/callback",
            TOKEN_STORE: "file",
            TOKEN_STORE_PATH: tokenPath,
          },
          async (secondClient) => secondClient.callTool({ name: "auth-status", arguments: {} })
        );
      }
    );

    assert.equal(status.structuredContent?.authenticated, false);
    assert.equal(status.structuredContent?.callback?.available, false);
    assert.match(status.structuredContent?.callback?.status ?? "", /^unavailable:/);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test("file token store survives stdio process restart", async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "canva-mcp-token-"));
  const tokenPath = path.join(tmpDir, "tokens.json");

  try {
    fs.writeFileSync(
      tokenPath,
      JSON.stringify(
        {
          "test-session": {
            accessToken: "realistic_access_token_for_status_only",
            refreshToken: "realistic_refresh_token_for_status_only",
            expiresAt: Date.now() + 60 * 60 * 1000,
          },
        },
        null,
        2
      )
    );

    const status = await withCanvaClient(
      { TOKEN_STORE: "file", TOKEN_STORE_PATH: tokenPath },
      async (client) => client.callTool({ name: "auth-status", arguments: {} })
    );

    assert.equal(status.structuredContent?.authenticated, true);
    assert.equal(typeof status.structuredContent?.expiresAt, "number");
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test("stdio OAuth callback shares pending state with the MCP tool process", async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "canva-mcp-callback-"));
  const tokenPath = path.join(tmpDir, "tokens.json");

  try {
    const result = await withCanvaClient(
      { TOKEN_STORE: "file", TOKEN_STORE_PATH: tokenPath },
      async (client, env) => {
        const auth = await client.callTool({ name: "authenticate", arguments: {} });
        const authText = auth.content?.[0]?.text ?? "";
        const authUrl = authText.match(/https:\/\/www\.canva\.com\/api\/oauth\/authorize\?\S+/)?.[0];
        assert.ok(authUrl);

        const state = new URL(authUrl).searchParams.get("state");
        assert.ok(state);

        const response = await fetch(
          `${env.CANVA_REDIRECT_URI}?code=fake-code-for-test&state=${state}`
        );
        const body = await response.text();

        return {
          callbackStatus: response.status,
          invalidState: body.includes("Invalid or expired state parameter"),
          authError: body.includes("Authentication Error"),
        };
      }
    );

    assert.equal(result.callbackStatus, 500);
    assert.equal(result.invalidState, false);
    assert.equal(result.authError, true);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
