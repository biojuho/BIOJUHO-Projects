import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { config as loadEnv } from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..", "..");

loadEnv({ path: path.join(rootDir, ".env"), quiet: true });
process.env.TOKEN_STORE ??= "file";

const { createCanvaServer, startCanvaHttpServer } = await import("./server.js");

const sessionId = process.env.CANVA_MCP_SESSION_ID || "codex-stdio";
const server = createCanvaServer(sessionId);
const transport = new StdioServerTransport();
let callbackServer = null;

if (process.env.CANVA_MCP_STDIO_CALLBACK_SERVER === "false") {
  process.env.CANVA_MCP_CALLBACK_STATUS = "disabled";
} else {
  try {
    callbackServer = await startCanvaHttpServer({ log: false });
    process.env.CANVA_MCP_CALLBACK_STATUS = "listening";
  } catch (error) {
    const code = error && typeof error === "object" && "code" in error
      ? String((error as { code?: unknown }).code)
      : "unknown";
    process.env.CANVA_MCP_CALLBACK_STATUS = `unavailable:${code}`;
    if (process.env.CANVA_MCP_STDIO_CALLBACK_REQUIRED === "true") {
      throw error;
    }
  }
}

process.on("SIGINT", () => {
  callbackServer?.close();
  void server.close().finally(() => process.exit(0));
});

process.on("SIGTERM", () => {
  callbackServer?.close();
  void server.close().finally(() => process.exit(0));
});

await server.connect(transport);
