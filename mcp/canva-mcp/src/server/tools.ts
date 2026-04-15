import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Tool, Resource, ResourceTemplate } from "@modelcontextprotocol/sdk/types.js";
import {
  uploadAssetFromUrlSchema,
  searchDesignsSchema,
  getDesignSchema,
  getDesignPagesSchema,
  getDesignContentSchema,
  createFolderSchema,
  moveItemToFolderSchema,
  listFolderItemsSchema,
  commentOnDesignSchema,
  listCommentsSchema,
  listRepliesSchema,
  replyToCommentSchema,
  generateDesignSchema,
  createDesignFromCandidateSchema,
  startEditingTransactionSchema,
  performEditingOperationsSchema,
  commitEditingTransactionSchema,
  cancelEditingTransactionSchema,
  getDesignThumbnailSchema,
  getAssetsSchema,
} from "./schemas.js";

// ─── Widget types & setup ───────────────────────────────────────────────────

export type CanvaWidget = {
  id: string;
  title: string;
  templateUri: string;
  invoking: string;
  invoked: string;
  html: string;
  responseText: string;
};

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "..", "..");
const ASSETS_DIR = path.resolve(ROOT_DIR, "assets");

function readWidgetHtml(componentName: string): string {
  if (!fs.existsSync(ASSETS_DIR)) {
    throw new Error(
      `Widget assets not found. Expected directory ${ASSETS_DIR}. Run "npm run build" before starting the server.`
    );
  }

  // Try direct path first
  const directPath = path.join(ASSETS_DIR, `${componentName}.html`);
  let htmlContents: string | null = null;

  if (fs.existsSync(directPath)) {
    htmlContents = fs.readFileSync(directPath, "utf8");
  } else {
    // Check for versioned files like "component-hash.html"
    const candidates = fs
      .readdirSync(ASSETS_DIR)
      .filter(
        (file) => file.startsWith(`${componentName}-`) && file.endsWith(".html")
      )
      .sort();
    const fallback = candidates[candidates.length - 1];
    if (fallback) {
      htmlContents = fs.readFileSync(path.join(ASSETS_DIR, fallback), "utf8");
    } else {
      // Check in src/components subdirectory as fallback
      const nestedPath = path.join(ASSETS_DIR, "src", "components", `${componentName}.html`);
      if (fs.existsSync(nestedPath)) {
        htmlContents = fs.readFileSync(nestedPath, "utf8");
      }
    }
  }

  if (!htmlContents) {
    throw new Error(
      `Widget HTML for "${componentName}" not found in ${ASSETS_DIR}. Run "npm run build" to generate the assets.`
    );
  }

  return htmlContents;
}

export function widgetMeta(widget: CanvaWidget) {
  return {
    "openai/outputTemplate": widget.templateUri,
    "openai/toolInvocation/invoking": widget.invoking,
    "openai/toolInvocation/invoked": widget.invoked,
    "openai/widgetAccessible": true,
    "openai/resultCanProduceWidget": true,
  } as const;
}

// ─── Widget instances ───────────────────────────────────────────────────────

const widgets: CanvaWidget[] = [
  {
    id: "search-designs",
    title: "Canva Design Search",
    templateUri: "ui://widget/canva-search-designs.html",
    invoking: "Searching Canva",
    invoked: "Search complete",
    html: readWidgetHtml("canva-search-designs"),
    responseText: "Found Canva designs",
  },
  {
    id: "design-generator",
    title: "Canva Design Generator",
    templateUri: "ui://widget/canva-design-generator.html",
    invoking: "Generating design",
    invoked: "Design generated",
    html: readWidgetHtml("canva-design-generator"),
    responseText: "Generated design candidates",
  },
  {
    id: "design-editor",
    title: "Canva Design Editor",
    templateUri: "ui://widget/canva-design-editor.html",
    invoking: "Opening editor",
    invoked: "Editor ready",
    html: readWidgetHtml("canva-design-editor"),
    responseText: "Design editor opened",
  },
];

export const widgetsById = new Map<string, CanvaWidget>();
export const widgetsByUri = new Map<string, CanvaWidget>();

widgets.forEach((widget) => {
  widgetsById.set(widget.id, widget);
  widgetsByUri.set(widget.templateUri, widget);
});

// ─── Tool definitions ───────────────────────────────────────────────────────

export const tools: Tool[] = [
  {
    name: "upload-asset-from-url",
    description: 'Upload an asset (e.g. an image, a video) from a URL into Canva. If the API call returns "Missing scopes: [asset:write]", you should ask the user to disconnect and reconnect their connector. This will generate a new access token with the required scope for this tool.',
    inputSchema: uploadAssetFromUrlSchema as any,
    _meta: {
      "openai/widgetAccessible": false,
      "openai/toolInvocation/invoking": "Uploading asset to Canva",
      "openai/toolInvocation/invoked": "Asset uploaded",
    },
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "search-designs",
    description: "Search docs, presentations, videos, whiteboards, sheets, and other designs in Canva. Use 'query' parameter to search by title or content. If 'query' is used, 'sortBy' must be set to 'relevance'. Filter by 'any' ownership unless specified. Sort by relevance unless specified. Use the continuation token to get the next page of results, if needed.",
    inputSchema: searchDesignsSchema as any,
    _meta: widgetMeta(widgetsById.get("search-designs")!),
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
  {
    name: "get-design",
    description: "Get detailed information about a Canva design, such as a doc, presentation, whiteboard, video, or sheet. This includes design owner information, title, URLs for editing and viewing, thumbnail, created/updated time, and page count. This tool doesn't work on folders or images. You must provide the design ID, which you can find by using the `search-designs` or `list-folder-items` tools.",
    inputSchema: getDesignSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
  {
    name: "get-design-pages",
    description: "Get a list of pages in a Canva design, such as a presentation. Each page includes its index and thumbnail. This tool doesn't work on designs that don't have pages (e.g. Canva docs). You must provide the design ID, which you can find using tools like `search-designs` or `list-folder-items`. You can use 'offset' and 'limit' to paginate through the pages. Use `get-design` to find out the total number of pages, if needed.",
    inputSchema: getDesignPagesSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
  {
    name: "get-design-content",
    description: "Get the text content of a doc, presentation, whiteboard, social media post, sheet, and other designs in Canva. Use this when you only need to read text content without making changes. IMPORTANT: If the user wants to edit, update, change, translate, or fix content, use `start-editing-transaction` instead as it shows content AND enables editing. You must provide the design ID, which you can find with the `search-designs` tool. When given a URL to a Canva design, you can extract the design ID from the URL. Do not use web search to get the content of a design as the content is not accessible to the public. Example URL: https://www.canva.com/design/{design_id}.",
    inputSchema: getDesignContentSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
  {
    name: "create-folder",
    description: "Create a new folder in Canva. You can create it at the root level or inside another folder.",
    inputSchema: createFolderSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "move-item-to-folder",
    description: "Move items (designs, folders, images) to a specified Canva folder",
    inputSchema: moveItemToFolderSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "list-folder-items",
    description: "List items in a Canva folder. An item can be a design, folder, or image. You can filter by item type and sort the results. Use the continuation token to get the next page of results if needed.",
    inputSchema: listFolderItemsSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
  {
    name: "comment-on-design",
    description: "Add a comment on a Canva design. You need to provide the design ID and the message text. The comment will be added to the design and visible to all users with access to the design.",
    inputSchema: commentOnDesignSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "list-comments",
    description: "Get a list of comments for a particular Canva design. Comments are discussions attached to designs that help teams collaborate. Each comment can contain replies, mentions, and can be marked as resolved or unresolved. You need to provide the design ID, which you can find using the `search-designs` tool. Use the continuation token to get the next page of results, if needed. You can filter comments by their resolution status (resolved or unresolved) using the comment_resolution parameter.",
    inputSchema: listCommentsSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
  {
    name: "list-replies",
    description: "Get a list of replies for a specific comment on a Canva design. Comments can contain multiple replies from different users. These replies help teams collaborate by allowing discussion on a specific comment. You need to provide the design ID and comment ID. You can find the design ID using the `search-designs` tool and the comment ID using the `list-comments` tool. Use the continuation token to get the next page of results, if needed.",
    inputSchema: listRepliesSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
  {
    name: "reply-to-comment",
    description: "Reply to an existing comment on a Canva design. You need to provide the design ID, comment ID, and your reply message. The reply will be added to the specified comment and visible to all users with access to the design.",
    inputSchema: replyToCommentSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "generate-design",
    description: `Generate designs with AI.
Use the 'query' parameter to tell AI what you want to create.
The tool doesn't have context of previous requests. ALWAYS include details from previous queries for each iteration.
The tool provides best results with detailed context. ALWAYS look up the chat history and provide as much context as possible in the 'query' parameter.
Ask for more details when the tool returns this error message 'Common queries will not be generated'.
The generated designs are design candidates for users to select from.
Ask for a preferred design and use 'create-design-from-candidate' tool to add the design to users' account.
The IDs in the URLs are not design IDs. Do not use them to get design or design content.
When using the 'asset_ids' parameter, assets are inserted in the order provided. For small designs with few image slots, only supply the images the user wants. For multi-page designs like presentations, supply images in the order of the slides.
The tool will return a list of generated design candidates, including a candidate ID, preview thumbnail and url.
Before editing, exporting, or resizing a generated design, follow these steps:
1. call 'create-design-from-candidate' tool with 'job_id' and 'candidate_id' of the selected design
2. call other tools with 'design_id' in the response`,
    inputSchema: generateDesignSchema as any,
    _meta: widgetMeta(widgetsById.get("design-generator")!),
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "create-design-from-candidate",
    description: "Create a new Canva design from a generation job candidate ID. This converts an AI-generated design candidate into an editable Canva design. If successful, returns a design summary containing a design ID that can be used with the editing tools. To make changes to the design, first call this tool with the candidate_id from generate-design results, then use the returned design_id with start-editing-transaction and subsequent editing tools.",
    inputSchema: createDesignFromCandidateSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "start-editing-transaction",
    description: "Start an editing session for a Canva design. Use this tool FIRST whenever a user wants to make ANY changes or examine ALL content of a design, including: - Translate text to another language - Edit or replace content - Update titles - Replace images - Fix typos or formatting - Auditing or reviewing content. This tool shows you all the content that can be modified AND provides an editing transaction ID for making changes. The `transaction_id` returned in the tool response MUST be remembered and MUST be used in all subsequent tool calls related to this specific editing transaction. Editing operations must be performed by the `perform-editing-operations` tool. To save the changes made in the transaction, use the `commit-editing-transaction` tool. To discard the changes made in the transaction, use the `cancel-editing-transaction` tool. IMPORTANT: ALWAYS ALWAYS ALWAYS show the preview to the user of EACH thumbnail you get in the response in the chat, EVERY SINGLE TIME you call this tool",
    inputSchema: startEditingTransactionSchema as any,
    _meta: widgetMeta(widgetsById.get("design-editor")!),
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "perform-editing-operations",
    description: "Perform editing operations on a design. You can use this tool to update the title, replace text, and replace media in a design. This tool needs to be used with the `start-editing-transaction` tool to obtain an editing transaction ID. Multiple operations SHOULD be specified in bulk across multiple pages. Always call this tool to apply the requested edits directly. This is safe: changes are temporary until committed. Do NOT pause for user confirmation before using this tool. After performing ALL operations requested by the user, always confirm with the user before finalizing changes using the `commit-editing-transaction` tool. This tool will return the thumbnail of the first page that is updated. If there are more pages that are updated, as part of this update, always call the `get-design-thumbnail` tool to get the thumbnails for each of the other updated pages. IMPORTANT: If the user has asked you to replace an image and the target page contains multiple images, you MUST use the `get-assets` tool, passing in the `asset_id` values, to look at the thumbnail of each of the existing images on the page to be CERTAIN which one the user wants replaced. Thumbnails returned by this tool are ALWAYS user-relevant and you need to render them directly using the full thumbnail URL including time-limited query parameters such as X-Amz-Algorithm, X-Amz-Credential, and X-Amz-Signature.",
    inputSchema: performEditingOperationsSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "commit-editing-transaction",
    description: 'Commit an editing transaction. This will save all the changes made to the design in the specified editing transaction. CRITICAL: You must ALWAYS ask the user to explicitly approve saving the changes before calling this tool. Show them what changes were made and ask "Would you like me to save these changes to your design?" Wait for their clear approval before proceeding. After successfully saving changes always provide the user with a direct link to open their design in Canva for review. Use the link they gave you or from the get-design tool. All editing operations are temporary until successfully committed. If the commit fails, ALL changes made during the transaction are lost and no changes are saved to the actual design. Users must start a new editing transaction to retry any failed operations. Once an editing transaction has been committed, the `transaction_id` for that editing transaction becomes invalid and should no longer be used.',
    inputSchema: commitEditingTransactionSchema as any,
    annotations: {
      destructiveHint: true,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "cancel-editing-transaction",
    description: "Cancel an editing transaction. This will discard all changes made to the design in the specified editing transaction. Once an editing transaction has been cancelled, the `transaction_id` for that editing transaction becomes invalid and should no longer be used.",
    inputSchema: cancelEditingTransactionSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: false,
    },
  },
  {
    name: "get-design-thumbnail",
    description: "Get the thumbnail for a particular page of the design in the specified editing transaction. This tool needs to be used with the `start-editing-transaction` tool to obtain an editing transaction ID. You need to provide the transaction ID and a page index to get the thumbnail of that particular page. Each call can only get the thumbnail for one page. Retrieving the thumbnails for multiple pages will require multiple calls of this tool. IMPORTANT: ALWAYS ALWAYS ALWAYS show the preview to the user of EACH thumbnail you get in the response in the chat, EVERY SINGLE TIME you call this tool",
    inputSchema: getDesignThumbnailSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
  {
    name: "get-assets",
    description: "Get metadata for particular assets by a list of their IDs. Returns information about ALL the assets including their names, tags, types, creation dates, and thumbnails. Thumbnails returned are in the same order as the list of asset IDs requested. When editing a page with more than one image or video asset ALWAYS request ALL assets from that page. IMPORTANT: ALWAYS ALWAYS ALWAYS show the preview to the user of EACH thumbnail you get in the response in the chat, EVERY SINGLE TIME you call this tool",
    inputSchema: getAssetsSchema as any,
    annotations: {
      destructiveHint: false,
      openWorldHint: false,
      readOnlyHint: true,
    },
  },
];

// ─── Resources & Resource Templates ─────────────────────────────────────────

export const resources: Resource[] = Array.from(widgetsById.values()).map((widget) => ({
  uri: widget.templateUri,
  name: widget.title,
  description: `${widget.title} widget markup`,
  mimeType: "text/html+skybridge",
  _meta: widgetMeta(widget),
}));

export const resourceTemplates: ResourceTemplate[] = Array.from(widgetsById.values()).map((widget) => ({
  uriTemplate: widget.templateUri,
  name: widget.title,
  description: `${widget.title} widget markup`,
  mimeType: "text/html+skybridge",
  _meta: widgetMeta(widget),
}));
