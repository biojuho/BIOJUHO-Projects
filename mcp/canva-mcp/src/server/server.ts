import {
  createServer,
  type IncomingMessage,
  type ServerResponse,
} from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import {
  CallToolRequestSchema,
  ListResourceTemplatesRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
  type CallToolRequest,
  type ListResourceTemplatesRequest,
  type ListResourcesRequest,
  type ListToolsRequest,
  type ReadResourceRequest,
} from "@modelcontextprotocol/sdk/types.js";

// ─── Refactored module imports ──────────────────────────────────────────────
import {
  uploadAssetFromUrlParser,
  searchDesignsParser,
  getDesignParser,
  getDesignPagesParser,
  getDesignContentParser,
  createFolderParser,
  moveItemToFolderParser,
  listFolderItemsParser,
  commentOnDesignParser,
  listCommentsParser,
  listRepliesParser,
  replyToCommentParser,
  generateDesignParser,
  createDesignFromCandidateParser,
  startEditingTransactionParser,
  performEditingOperationsParser,
  commitEditingTransactionParser,
  cancelEditingTransactionParser,
  getDesignThumbnailParser,
  getAssetsParser,
} from "./schemas.js";

import {
  authSessions,
  pendingAuthStates,
  generateCodeVerifier,
  generateAuthUrl,
  exchangeCodeForToken,
  getValidAccessToken,
  canvaApiRequest,
} from "./auth.js";

import {
  tools,
  resources,
  resourceTemplates,
  widgetsById,
  widgetsByUri,
  widgetMeta,
} from "./tools.js";

// ─── MCP Server factory ────────────────────────────────────────────────────

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "..", "..");
const ASSETS_DIR = path.resolve(ROOT_DIR, "assets");

function createCanvaServer(sessionId: string): Server {
  const server = new Server(
    {
      name: "canva-mcp",
      version: "1.0.0",
    },
    {
      capabilities: {
        resources: {},
        tools: {},
      },
    }
  );

  server.setRequestHandler(
    ListResourcesRequestSchema,
    async (_request: ListResourcesRequest) => ({
      resources,
    })
  );

  server.setRequestHandler(
    ReadResourceRequestSchema,
    async (request: ReadResourceRequest) => {
      const widget = widgetsByUri.get(request.params.uri);

      if (!widget) {
        throw new Error(`Unknown resource: ${request.params.uri}`);
      }

      return {
        contents: [
          {
            uri: widget.templateUri,
            mimeType: "text/html+skybridge",
            text: widget.html,
            _meta: widgetMeta(widget),
          },
        ],
      };
    }
  );

  server.setRequestHandler(
    ListResourceTemplatesRequestSchema,
    async (_request: ListResourceTemplatesRequest) => ({
      resourceTemplates,
    })
  );

  server.setRequestHandler(
    ListToolsRequestSchema,
    async (_request: ListToolsRequest) => ({
      tools,
    })
  );

  server.setRequestHandler(
    CallToolRequestSchema,
    async (request: CallToolRequest) => {
      const toolName = request.params.name;

      // Check authentication for all tools
      // First check if we have session tokens
      let accessToken: string | null = null;

      if (authSessions.has(sessionId)) {
        accessToken = await getValidAccessToken(sessionId);
      } else {
        // Fallback: Check for Authorization header stored in session (from HTTP request)
        // This allows tokens from user profile to be passed via headers
        const storedAuthHeader = sessionAuthHeaders.get(sessionId);
        if (storedAuthHeader && storedAuthHeader.startsWith("Bearer ")) {
          accessToken = storedAuthHeader.substring(7);
          // Store in session for future use (without refresh token - will need re-auth when expired)
          authSessions.set(sessionId, {
            accessToken: accessToken,
            refreshToken: "", // We don't have refresh token from header
            expiresAt: Date.now() + 3600000, // Assume 1 hour expiration
          });
        }
      }

      if (!accessToken) {
        const state = crypto.randomBytes(16).toString("hex");
        const codeVerifier = generateCodeVerifier();
        pendingAuthStates.set(state, { sessionId, createdAt: Date.now(), codeVerifier });
        const authUrl = generateAuthUrl(state, codeVerifier);

        return {
          content: [
            {
              type: "text",
              text: `Please authenticate with Canva to use this feature. Visit: ${authUrl}`,
            },
          ],
        };
      }

      switch (toolName) {
        case "upload-asset-from-url": {
          const args = uploadAssetFromUrlParser.parse(request.params.arguments ?? {});
          const data = await canvaApiRequest(sessionId, "/url-asset-uploads", "POST", {
            name: args.name,
            url: args.url,
          }, accessToken);
          return {
            content: [{ type: "text", text: `Successfully started asset upload job. Job ID: ${data.job.id}` }],
            structuredContent: data,
          };
        }

        case "search-designs": {
          const args = searchDesignsParser.parse(request.params.arguments ?? {});
          const widget = widgetsById.get("search-designs")!;
          const params = new URLSearchParams();
          if (args.query) {
            params.append("query", args.query);
            params.append("sort_by", "relevance");
          } else if (args.sortBy) {
            params.append("sort_by", args.sortBy);
          }
          if (args.ownershipFilter) params.append("ownership", args.ownershipFilter);
          if (args.continuation) params.append("continuation", args.continuation);
          const data = await canvaApiRequest(sessionId, `/designs?${params.toString()}`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Found ${data.items?.length || 0} designs.` }],
            structuredContent: { query: args.query, designs: data.items || [], continuation: data.continuation },
            _meta: widgetMeta(widget),
          };
        }

        case "get-design": {
          const args = getDesignParser.parse(request.params.arguments ?? {});
          const data = await canvaApiRequest(sessionId, `/designs/${args.designId}`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Retrieved design: ${data.design.title}` }],
            structuredContent: data.design,
          };
        }

        case "get-design-pages": {
          const args = getDesignPagesParser.parse(request.params.arguments ?? {});
          const params = new URLSearchParams();
          if (args.offset !== undefined) params.append("offset", args.offset.toString());
          if (args.limit !== undefined) params.append("limit", args.limit.toString());
          const data = await canvaApiRequest(sessionId, `/designs/${args.designId}/pages?${params.toString()}`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Retrieved ${data.items?.length || 0} pages.` }],
            structuredContent: data,
          };
        }

        case "get-design-content": {
          const args = getDesignContentParser.parse(request.params.arguments ?? {});
          const data = await canvaApiRequest(sessionId, `/designs/${args.designId}/content`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Retrieved design content.` }],
            structuredContent: data,
          };
        }

        case "create-folder": {
          const args = createFolderParser.parse(request.params.arguments ?? {});
          const body: any = { name: args.name };
          if (args.parentFolderId) body.parent_folder_id = args.parentFolderId;
          const data = await canvaApiRequest(sessionId, "/folders", "POST", body, accessToken);
          return {
            content: [{ type: "text", text: `Successfully created folder: ${args.name}` }],
            structuredContent: data,
          };
        }

        case "move-item-to-folder": {
          const args = moveItemToFolderParser.parse(request.params.arguments ?? {});
          await canvaApiRequest(sessionId, `/folders/${args.folderId}/items`, "POST", { item_id: args.itemId }, accessToken);
          return {
            content: [{ type: "text", text: `Successfully moved item to folder.` }],
          };
        }

        case "list-folder-items": {
          const args = listFolderItemsParser.parse(request.params.arguments ?? {});
          const params = new URLSearchParams();
          if (args.itemType) params.append("item_type", args.itemType);
          if (args.continuation) params.append("continuation", args.continuation);
          const data = await canvaApiRequest(sessionId, `/folders/${args.folderId}/items?${params.toString()}`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Found ${data.items?.length || 0} items in folder.` }],
            structuredContent: data,
          };
        }

        case "comment-on-design": {
          const args = commentOnDesignParser.parse(request.params.arguments ?? {});
          const data = await canvaApiRequest(sessionId, `/designs/${args.designId}/comments`, "POST", { message_plaintext: args.message }, accessToken);
          return {
            content: [{ type: "text", text: `Successfully added comment.` }],
            structuredContent: data,
          };
        }

        case "list-comments": {
          const args = listCommentsParser.parse(request.params.arguments ?? {});
          const params = new URLSearchParams();
          if (args.commentResolution) params.append("comment_resolution", args.commentResolution);
          if (args.continuation) params.append("continuation", args.continuation);
          const data = await canvaApiRequest(sessionId, `/designs/${args.designId}/comments?${params.toString()}`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Found ${data.items?.length || 0} comments.` }],
            structuredContent: data,
          };
        }

        case "list-replies": {
          const args = listRepliesParser.parse(request.params.arguments ?? {});
          const params = new URLSearchParams();
          if (args.continuation) params.append("continuation", args.continuation);
          const data = await canvaApiRequest(sessionId, `/designs/${args.designId}/comments/${args.threadId}/replies?${params.toString()}`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Found ${data.items?.length || 0} replies.` }],
            structuredContent: data,
          };
        }

        case "reply-to-comment": {
          const args = replyToCommentParser.parse(request.params.arguments ?? {});
          const data = await canvaApiRequest(sessionId, `/designs/${args.designId}/comments/${args.threadId}/replies`, "POST", { message_plaintext: args.message }, accessToken);
          return {
            content: [{ type: "text", text: `Successfully added reply.` }],
            structuredContent: data,
          };
        }

        case "generate-design": {
          const args = generateDesignParser.parse(request.params.arguments ?? {});
          const widget = widgetsById.get("design-generator")!;
          const body: any = { query: args.query };
          if (args.assetIds) body.asset_ids = args.assetIds;
          const data = await canvaApiRequest(sessionId, "/designs/generate", "POST", body, accessToken);
          return {
            content: [{ type: "text", text: `Generated ${data.candidates?.length || 0} design candidates.` }],
            structuredContent: data,
            _meta: widgetMeta(widget),
          };
        }

        case "create-design-from-candidate": {
          const args = createDesignFromCandidateParser.parse(request.params.arguments ?? {});
          const data = await canvaApiRequest(sessionId, `/designs/generate/${args.jobId}/candidates/${args.candidateId}`, "POST", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Successfully created design from candidate.` }],
            structuredContent: data,
          };
        }

        case "start-editing-transaction": {
          const args = startEditingTransactionParser.parse(request.params.arguments ?? {});
          const widget = widgetsById.get("design-editor")!;
          const data = await canvaApiRequest(sessionId, `/designs/${args.designId}/edit`, "POST", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Started editing transaction. Transaction ID: ${data.transaction_id}` }],
            structuredContent: data,
            _meta: widgetMeta(widget),
          };
        }

        case "perform-editing-operations": {
          const args = performEditingOperationsParser.parse(request.params.arguments ?? {});
          const data = await canvaApiRequest(sessionId, `/designs/edit/${args.transactionId}/operations`, "POST", { operations: args.operations }, accessToken);
          return {
            content: [{ type: "text", text: `Successfully performed editing operations.` }],
            structuredContent: data,
          };
        }

        case "commit-editing-transaction": {
          const args = commitEditingTransactionParser.parse(request.params.arguments ?? {});
          await canvaApiRequest(sessionId, `/designs/edit/${args.transactionId}/commit`, "POST", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Successfully committed changes to design.` }],
          };
        }

        case "cancel-editing-transaction": {
          const args = cancelEditingTransactionParser.parse(request.params.arguments ?? {});
          await canvaApiRequest(sessionId, `/designs/edit/${args.transactionId}/cancel`, "POST", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Successfully cancelled editing transaction.` }],
          };
        }

        case "get-design-thumbnail": {
          const args = getDesignThumbnailParser.parse(request.params.arguments ?? {});
          const data = await canvaApiRequest(sessionId, `/designs/edit/${args.transactionId}/pages/${args.pageIndex}/thumbnail`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Retrieved thumbnail for page ${args.pageIndex}.` }],
            structuredContent: data,
          };
        }

        case "get-assets": {
          const args = getAssetsParser.parse(request.params.arguments ?? {});
          const params = new URLSearchParams();
          args.assetIds.forEach(id => params.append("asset_ids", id));
          const data = await canvaApiRequest(sessionId, `/assets?${params.toString()}`, "GET", undefined, accessToken);
          return {
            content: [{ type: "text", text: `Retrieved ${data.items?.length || 0} assets.` }],
            structuredContent: data,
          };
        }

        default:
          throw new Error(`Unknown tool: ${toolName}`);
      }
    }
  );

  return server;
}

// ─── Session management ─────────────────────────────────────────────────────

type SessionRecord = {
  server: Server;
  transport: SSEServerTransport;
  authHeader?: string; // Store Authorization header from HTTP requests
};

const sessions = new Map<string, SessionRecord>();
// Map to store auth headers by sessionId (for looking up during tool calls)
const sessionAuthHeaders = new Map<string, string>();
// Map from transport.sessionId to actualSessionId (used in createCanvaServer closure)
const transportToSessionId = new Map<string, string>();

const ssePath = "/mcp";
const postPath = "/mcp/messages";
const authCallbackPath = "/auth/callback";

// ─── HTTP request handlers ──────────────────────────────────────────────────

async function handleSseRequest(res: ServerResponse, sessionId?: string, authHeader?: string) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  const actualSessionId = sessionId || crypto.randomBytes(16).toString("hex");
  const server = createCanvaServer(actualSessionId);
  const transport = new SSEServerTransport(postPath, res);

  // Store mapping from transport.sessionId to actualSessionId
  transportToSessionId.set(transport.sessionId, actualSessionId);

  // Store auth header if provided (use actualSessionId which matches the closure in createCanvaServer)
  if (authHeader) {
    sessionAuthHeaders.set(actualSessionId, authHeader);
  }

  sessions.set(transport.sessionId, { server, transport, authHeader });

  transport.onclose = async () => {
    const mappedSessionId = transportToSessionId.get(transport.sessionId);
    if (mappedSessionId) {
      sessionAuthHeaders.delete(mappedSessionId);
      transportToSessionId.delete(transport.sessionId);
    }
    sessions.delete(transport.sessionId);
    await server.close();
  };

  transport.onerror = (error) => {
    console.error("SSE transport error", error);
  };

  try {
    await server.connect(transport);
  } catch (error) {
    sessions.delete(transport.sessionId);
    console.error("Failed to start SSE session", error);
    if (!res.headersSent) {
      res.writeHead(500).end("Failed to establish SSE connection");
    }
  }
}

async function handlePostMessage(
  req: IncomingMessage,
  res: ServerResponse,
  url: URL
) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "content-type, authorization");
  const sessionId = url.searchParams.get("sessionId");

  if (!sessionId) {
    res.writeHead(400).end("Missing sessionId query parameter");
    return;
  }

  const session = sessions.get(sessionId);

  if (!session) {
    res.writeHead(404).end("Unknown session");
    return;
  }

  // Extract Authorization header from HTTP request and store in session
  const authHeader = req.headers.authorization || req.headers.Authorization;
  if (authHeader) {
    const authHeaderStr = typeof authHeader === "string" ? authHeader : authHeader[0];
    session.authHeader = authHeaderStr;
    // Map transport.sessionId to actualSessionId and store authHeader with actualSessionId
    const actualSessionId = transportToSessionId.get(sessionId);
    if (actualSessionId) {
      sessionAuthHeaders.set(actualSessionId, authHeaderStr);
    } else {
      // Fallback: also store with transport.sessionId in case mapping doesn't exist yet
      sessionAuthHeaders.set(sessionId, authHeaderStr);
    }
  }

  try {
    await session.transport.handlePostMessage(req, res);
  } catch (error) {
    console.error("Failed to process message", error);
    if (!res.headersSent) {
      res.writeHead(500).end("Failed to process message");
    }
  }
}

async function handleAuthCallback(req: IncomingMessage, res: ServerResponse, url: URL) {
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const error = url.searchParams.get("error");

  if (error) {
    res.writeHead(400, { "Content-Type": "text/html" }).end(`
      <html>
        <body>
          <h1>Authentication Failed</h1>
          <p>Error: ${error}</p>
          <p>Please try again.</p>
        </body>
      </html>
    `);
    return;
  }

  if (!code || !state) {
    res.writeHead(400).end("Missing code or state parameter");
    return;
  }

  const pendingAuth = pendingAuthStates.get(state);

  if (!pendingAuth) {
    res.writeHead(400).end("Invalid or expired state parameter");
    return;
  }

  // Clean up old states (older than 10 minutes)
  const now = Date.now();
  for (const [key, value] of pendingAuthStates.entries()) {
    if (now - value.createdAt > 10 * 60 * 1000) {
      pendingAuthStates.delete(key);
    }
  }

  try {
    const tokenData = await exchangeCodeForToken(code, pendingAuth.codeVerifier);

    authSessions.set(pendingAuth.sessionId, {
      accessToken: tokenData.access_token,
      refreshToken: tokenData.refresh_token,
      expiresAt: Date.now() + tokenData.expires_in * 1000,
    });

    pendingAuthStates.delete(state);

    res.writeHead(200, { "Content-Type": "text/html" }).end(`
      <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
          <div style="background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); text-align: center; max-width: 400px;">
            <h1 style="color: #667eea; margin-bottom: 1rem;">Successfully Connected to Canva!</h1>
            <p style="color: #555;">You can now close this window and return to your chat.</p>
            <script>
              setTimeout(() => window.close(), 2000);
            </script>
          </div>
        </body>
      </html>
    `);
  } catch (error: any) {
    console.error("Failed to exchange code for token", error);
    res.writeHead(500, { "Content-Type": "text/html" }).end(`
      <html>
        <body>
          <h1>Authentication Error</h1>
          <p>${error.message}</p>
          <p>Please try again.</p>
        </body>
      </html>
    `);
  }
}

// ─── HTTP Server ────────────────────────────────────────────────────────────

const portEnv = Number(process.env.PORT ?? 8001);
const port = Number.isFinite(portEnv) ? portEnv : 8001;

// Helper function to set CORS headers
function setCorsHeaders(res: ServerResponse, origin?: string) {
  const allowedOrigins = [
    'https://zerotwo.ai',
    'http://localhost:3000',
    'http://localhost:5173', // Vite dev server
  ];

  const requestOrigin = origin || '*';
  const allowOrigin = allowedOrigins.includes(requestOrigin) ? requestOrigin : '*';

  res.setHeader("Access-Control-Allow-Origin", allowOrigin);
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "content-type, authorization");
  res.setHeader("Access-Control-Allow-Credentials", "true");
}

const httpServer = createServer(
  async (req: IncomingMessage, res: ServerResponse) => {
    const origin = req.headers.origin;

    // Set CORS headers on all responses
    setCorsHeaders(res, origin);

    if (!req.url) {
      res.writeHead(400).end("Missing URL");
      return;
    }

    const url = new URL(req.url, `http://${req.headers.host ?? "localhost"}`);

    if (
      req.method === "OPTIONS" &&
      (url.pathname === ssePath || url.pathname === postPath)
    ) {
      res.writeHead(204);
      res.end();
      return;
    }

    if (req.method === "GET" && url.pathname === ssePath) {
      // Extract Authorization header if present
      const authHeader = req.headers.authorization || req.headers.Authorization;
      const authHeaderStr = authHeader ? (typeof authHeader === "string" ? authHeader : authHeader[0]) : undefined;
      await handleSseRequest(res, undefined, authHeaderStr);
      return;
    }

    if (req.method === "POST" && url.pathname === postPath) {
      await handlePostMessage(req, res, url);
      return;
    }

    if (req.method === "GET" && url.pathname === authCallbackPath) {
      await handleAuthCallback(req, res, url);
      return;
    }

    // Serve static assets for widgets
    if (req.method === "GET") {
      const assetPath = url.pathname.slice(1);
      const fullPath = path.join(ASSETS_DIR, assetPath);
      const resolvedPath = path.resolve(fullPath);

      if (!resolvedPath.startsWith(path.resolve(ASSETS_DIR))) {
        res.writeHead(403).end("Forbidden");
        return;
      }

      if (fs.existsSync(resolvedPath) && fs.statSync(resolvedPath).isFile()) {
        const ext = path.extname(resolvedPath).toLowerCase();
        const contentTypes: { [key: string]: string } = {
          ".html": "text/html",
          ".js": "application/javascript",
          ".css": "text/css",
          ".json": "application/json",
          ".png": "image/png",
          ".jpg": "image/jpeg",
          ".jpeg": "image/jpeg",
          ".gif": "image/gif",
          ".svg": "image/svg+xml",
          ".ico": "image/x-icon",
        };
        const contentType = contentTypes[ext] || "application/octet-stream";

        res.writeHead(200, {
          "Content-Type": contentType,
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "public, max-age=3600",
        });
        fs.createReadStream(resolvedPath).pipe(res);
        return;
      }
    }

    res.writeHead(404).end("Not Found");
  }
);

httpServer.on("clientError", (err: Error, socket) => {
  console.error("HTTP client error", err);
  socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
});

httpServer.listen(port, '0.0.0.0', () => {
  console.log(`Canva MCP server listening on http://0.0.0.0:${port}`);
  console.log(`  SSE stream: GET http://0.0.0.0:${port}${ssePath}`);
  console.log(`  Message post endpoint: POST http://0.0.0.0:${port}${postPath}?sessionId=...`);
  console.log(`  OAuth callback: GET http://0.0.0.0:${port}${authCallbackPath}`);
  console.log(`\nMake sure to set your environment variables:`);
  console.log(`  CANVA_CLIENT_ID=<your_client_id>`);
  console.log(`  CANVA_CLIENT_SECRET=<your_client_secret>`);
  console.log(`  CANVA_REDIRECT_URI=${process.env.CANVA_REDIRECT_URI || "http://127.0.0.1:8001/auth/callback"}`);
});
