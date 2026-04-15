import { z } from "zod";

// ─── Tool Input Schemas (JSON Schema) ───────────────────────────────────────

export const uploadAssetFromUrlSchema = {
  type: "object",
  properties: {
    name: {
      type: "string",
      description: "Name for the asset",
    },
    url: {
      type: "string",
      description: "URL of the asset to upload",
    },
  },
  required: ["name", "url"],
  additionalProperties: false,
};

export const searchDesignsSchema = {
  type: "object",
  properties: {
    query: {
      type: "string",
      description: "Search query for design title or content",
    },
    sortBy: {
      type: "string",
      enum: ["relevance", "modified_descending", "modified_ascending", "title_descending", "title_ascending"],
      description: "Sort order for results. Must be 'relevance' when using query parameter.",
    },
    ownershipFilter: {
      type: "string",
      enum: ["any", "owned", "shared"],
      description: "Filter by ownership (default: any)",
    },
    continuation: {
      type: "string",
      description: "Continuation token for pagination",
    },
  },
  additionalProperties: false,
};

export const getDesignSchema = {
  type: "object",
  properties: {
    designId: {
      type: "string",
      description: "The design ID to retrieve",
    },
  },
  required: ["designId"],
  additionalProperties: false,
};

export const getDesignPagesSchema = {
  type: "object",
  properties: {
    designId: {
      type: "string",
      description: "The design ID",
    },
    offset: {
      type: "number",
      description: "Offset for pagination",
    },
    limit: {
      type: "number",
      description: "Limit for pagination",
    },
  },
  required: ["designId"],
  additionalProperties: false,
};

export const getDesignContentSchema = {
  type: "object",
  properties: {
    designId: {
      type: "string",
      description: "The design ID",
    },
  },
  required: ["designId"],
  additionalProperties: false,
};

export const createFolderSchema = {
  type: "object",
  properties: {
    name: {
      type: "string",
      description: "Name of the folder",
    },
    parentFolderId: {
      type: "string",
      description: "Parent folder ID (optional, creates at root if not provided)",
    },
  },
  required: ["name"],
  additionalProperties: false,
};

export const moveItemToFolderSchema = {
  type: "object",
  properties: {
    itemId: {
      type: "string",
      description: "ID of the item to move",
    },
    folderId: {
      type: "string",
      description: "Destination folder ID",
    },
  },
  required: ["itemId", "folderId"],
  additionalProperties: false,
};

export const listFolderItemsSchema = {
  type: "object",
  properties: {
    folderId: {
      type: "string",
      description: "Folder ID to list items from",
    },
    itemType: {
      type: "string",
      enum: ["design", "folder", "image"],
      description: "Filter by item type",
    },
    continuation: {
      type: "string",
      description: "Continuation token for pagination",
    },
  },
  required: ["folderId"],
  additionalProperties: false,
};

export const commentOnDesignSchema = {
  type: "object",
  properties: {
    designId: {
      type: "string",
      description: "The design ID",
    },
    message: {
      type: "string",
      description: "Comment message text",
    },
  },
  required: ["designId", "message"],
  additionalProperties: false,
};

export const listCommentsSchema = {
  type: "object",
  properties: {
    designId: {
      type: "string",
      description: "The design ID",
    },
    commentResolution: {
      type: "string",
      enum: ["resolved", "unresolved"],
      description: "Filter by resolution status",
    },
    continuation: {
      type: "string",
      description: "Continuation token for pagination",
    },
  },
  required: ["designId"],
  additionalProperties: false,
};

export const listRepliesSchema = {
  type: "object",
  properties: {
    designId: {
      type: "string",
      description: "The design ID",
    },
    threadId: {
      type: "string",
      description: "The comment thread ID",
    },
    continuation: {
      type: "string",
      description: "Continuation token for pagination",
    },
  },
  required: ["designId", "threadId"],
  additionalProperties: false,
};

export const replyToCommentSchema = {
  type: "object",
  properties: {
    designId: {
      type: "string",
      description: "The design ID",
    },
    threadId: {
      type: "string",
      description: "The comment thread ID",
    },
    message: {
      type: "string",
      description: "Reply message text",
    },
  },
  required: ["designId", "threadId", "message"],
  additionalProperties: false,
};

export const generateDesignSchema = {
  type: "object",
  properties: {
    query: {
      type: "string",
      description: "Detailed description of what to create (include all context from previous queries)",
    },
    assetIds: {
      type: "array",
      items: {
        type: "string",
      },
      description: "Array of asset IDs to insert in order",
    },
  },
  required: ["query"],
  additionalProperties: false,
};

export const createDesignFromCandidateSchema = {
  type: "object",
  properties: {
    jobId: {
      type: "string",
      description: "Generation job ID",
    },
    candidateId: {
      type: "string",
      description: "Candidate design ID",
    },
  },
  required: ["jobId", "candidateId"],
  additionalProperties: false,
};

export const startEditingTransactionSchema = {
  type: "object",
  properties: {
    designId: {
      type: "string",
      description: "The design ID to edit",
    },
  },
  required: ["designId"],
  additionalProperties: false,
};

export const performEditingOperationsSchema = {
  type: "object",
  properties: {
    transactionId: {
      type: "string",
      description: "The editing transaction ID",
    },
    operations: {
      type: "array",
      items: {
        type: "object",
      },
      description: "Array of editing operations to perform",
    },
  },
  required: ["transactionId", "operations"],
  additionalProperties: false,
};

export const commitEditingTransactionSchema = {
  type: "object",
  properties: {
    transactionId: {
      type: "string",
      description: "The editing transaction ID to commit",
    },
  },
  required: ["transactionId"],
  additionalProperties: false,
};

export const cancelEditingTransactionSchema = {
  type: "object",
  properties: {
    transactionId: {
      type: "string",
      description: "The editing transaction ID to cancel",
    },
  },
  required: ["transactionId"],
  additionalProperties: false,
};

export const getDesignThumbnailSchema = {
  type: "object",
  properties: {
    transactionId: {
      type: "string",
      description: "The editing transaction ID",
    },
    pageIndex: {
      type: "number",
      description: "The page index to get thumbnail for",
    },
  },
  required: ["transactionId", "pageIndex"],
  additionalProperties: false,
};

export const getAssetsSchema = {
  type: "object",
  properties: {
    assetIds: {
      type: "array",
      items: {
        type: "string",
      },
      description: "Array of asset IDs to retrieve",
    },
  },
  required: ["assetIds"],
  additionalProperties: false,
};

// ─── Zod Parsers ────────────────────────────────────────────────────────────

export const uploadAssetFromUrlParser = z.object({
  name: z.string(),
  url: z.string().url(),
});

export const searchDesignsParser = z.object({
  query: z.string().optional(),
  sortBy: z.enum(["relevance", "modified_descending", "modified_ascending", "title_descending", "title_ascending"]).optional(),
  ownershipFilter: z.enum(["any", "owned", "shared"]).optional(),
  continuation: z.string().optional(),
});

export const getDesignParser = z.object({
  designId: z.string(),
});

export const getDesignPagesParser = z.object({
  designId: z.string(),
  offset: z.number().optional(),
  limit: z.number().optional(),
});

export const getDesignContentParser = z.object({
  designId: z.string(),
});

export const createFolderParser = z.object({
  name: z.string(),
  parentFolderId: z.string().optional(),
});

export const moveItemToFolderParser = z.object({
  itemId: z.string(),
  folderId: z.string(),
});

export const listFolderItemsParser = z.object({
  folderId: z.string(),
  itemType: z.enum(["design", "folder", "image"]).optional(),
  continuation: z.string().optional(),
});

export const commentOnDesignParser = z.object({
  designId: z.string(),
  message: z.string(),
});

export const listCommentsParser = z.object({
  designId: z.string(),
  commentResolution: z.enum(["resolved", "unresolved"]).optional(),
  continuation: z.string().optional(),
});

export const listRepliesParser = z.object({
  designId: z.string(),
  threadId: z.string(),
  continuation: z.string().optional(),
});

export const replyToCommentParser = z.object({
  designId: z.string(),
  threadId: z.string(),
  message: z.string(),
});

export const generateDesignParser = z.object({
  query: z.string(),
  assetIds: z.array(z.string()).optional(),
});

export const createDesignFromCandidateParser = z.object({
  jobId: z.string(),
  candidateId: z.string(),
});

export const startEditingTransactionParser = z.object({
  designId: z.string(),
});

export const performEditingOperationsParser = z.object({
  transactionId: z.string(),
  operations: z.array(z.any()),
});

export const commitEditingTransactionParser = z.object({
  transactionId: z.string(),
});

export const cancelEditingTransactionParser = z.object({
  transactionId: z.string(),
});

export const getDesignThumbnailParser = z.object({
  transactionId: z.string(),
  pageIndex: z.number(),
});

export const getAssetsParser = z.object({
  assetIds: z.array(z.string()),
});
