import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

import { resourceTemplates, resources, tools } from "../dist/server/tools.js";

const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STDIO_ENTRY = "dist/server/stdio.js";

async function withCanvaClient(callback) {
  const port = "19250";
  const transport = new StdioClientTransport({
    command: "node",
    args: [STDIO_ENTRY],
    cwd: ROOT_DIR,
    env: {
      ...process.env,
      PORT: port,
      CANVA_REDIRECT_URI: `http://127.0.0.1:${port}/auth/callback`,
      CANVA_MCP_SESSION_ID: "inventory-test-session",
      CANVA_MCP_QUIET_AUTH_ERRORS: "true",
    },
  });
  const client = new Client({ name: "canva-mcp-inventory-test", version: "1.0.0" });
  await client.connect(transport);

  try {
    return await callback(client);
  } finally {
    await client.close();
  }
}

function sorted(values) {
  return [...values].sort((a, b) => a.localeCompare(b));
}

test("stdio tool inventory exactly mirrors the server registry", async () => {
  const registryToolNames = sorted(tools.map((tool) => tool.name));
  assert.equal(new Set(registryToolNames).size, registryToolNames.length);

  const runtimeToolNames = await withCanvaClient(async (client) => {
    const response = await client.listTools();
    return sorted(response.tools.map((tool) => tool.name));
  });

  assert.deepEqual(runtimeToolNames, registryToolNames);
  assert.equal(runtimeToolNames.includes("auth-status"), true);
  assert.equal(runtimeToolNames.includes("authenticate"), true);
  assert.equal(runtimeToolNames.includes("search-designs"), true);
  assert.equal(runtimeToolNames.includes("generate-design"), true);
  assert.equal(runtimeToolNames.includes("start-editing-transaction"), true);
});

test("widget-backed tools keep resources and templates in the same inventory", async () => {
  const resourceUris = new Set(resources.map((resource) => resource.uri));
  const templateUris = new Set(resourceTemplates.map((template) => template.uriTemplate));
  const widgetToolTemplates = tools
    .map((tool) => tool._meta?.["openai/outputTemplate"])
    .filter(Boolean);

  assert.deepEqual(sorted(resourceUris), sorted(templateUris));
  assert.equal(widgetToolTemplates.length, 3);

  for (const templateUri of widgetToolTemplates) {
    assert.equal(resourceUris.has(templateUri), true, `${templateUri} missing from resources`);
    assert.equal(templateUris.has(templateUri), true, `${templateUri} missing from resource templates`);
  }

  const runtimeInventory = await withCanvaClient(async (client) => {
    const listedResources = await client.listResources();
    const listedTemplates = await client.listResourceTemplates();
    return {
      resources: sorted(listedResources.resources.map((resource) => resource.uri)),
      templates: sorted(listedTemplates.resourceTemplates.map((template) => template.uriTemplate)),
    };
  });

  assert.deepEqual(runtimeInventory.resources, sorted(resourceUris));
  assert.deepEqual(runtimeInventory.templates, sorted(templateUris));
});
