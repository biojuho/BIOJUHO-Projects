# AI Projects Workspace

Multi-project monorepo: DeSci platform, AgriGuard, MCP automation tools.

## Projects

| Project | Stack | Port | Purpose |
|---------|-------|------|---------|
| `desci-platform/biolinker` | FastAPI + ChromaDB + LangChain | 8000 | RFP matching AI agent API |
| `desci-platform/frontend` | React 19 + Vite 7 + Tailwind | 5173 | DeSci platform web UI |
| `desci-platform/contracts` | Hardhat + Solidity 0.8.20 | - | ERC20 (DeSciToken) + ERC721 (ResearchPaperNFT) |
| `AgriGuard/backend` | FastAPI + SQLAlchemy + Web3 | 8002 | Agricultural supply chain tracking |
| `DailyNews` | Python + Notion API + LLM | - | X Growth Engine + Notion automation |

## Commands

### desci-platform/biolinker (Backend)
```bash
cd desci-platform/biolinker
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# Docker: cd desci-platform && docker-compose up
```

### desci-platform/frontend
```bash
cd desci-platform/frontend
npm install
npm run dev        # Dev server on :5173
npm run build      # Production build (esbuild minify)
npm run lint       # ESLint 9
```

### desci-platform/contracts
```bash
cd desci-platform/contracts
npm install
npx hardhat compile
npx hardhat test
npx hardhat run scripts/deploy.js --network sepolia  # Requires PRIVATE_KEY in .env
```

### AgriGuard/backend
```bash
cd AgriGuard/backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

## Architecture

```
desci-platform/
  biolinker/
    main.py              # FastAPI app entry (all routes)
    models.py            # Pydantic schemas (RFPDocument, Paper, VCFirm, etc.)
    services/
      analyzer.py        # LLM-based RFP analysis
      vector_store.py    # ChromaDB + in-memory fallback
      smart_matcher.py   # Asset-based smart matching engine
      matcher.py         # Paper-to-RFP vector matching
      web3_service.py    # DeSciToken rewards + NFT minting
      auth.py            # Firebase token verification
      scheduler.py       # APScheduler for notice collection
      agent_service.py   # Deep research / content / YouTube / literature review
  frontend/
    src/
      App.jsx            # Routes + ErrorBoundary
      contexts/          # AuthContext (Firebase), ToastContext
      components/        # Dashboard, BioLinker, MyLab, Wallet, VCDashboard, etc.
      services/          # API client layer
  contracts/
    contracts/           # Solidity: DeSciToken.sol, ResearchPaperNFT.sol
    scripts/             # deploy.js, deploy_nft.js
```

## MCP Servers & Skills

| MCP Server | Path | Purpose |
| ---------- | ---- | ------- |
| `canva-mcp` | TS/Node | Canva Connect API design automation |
| `github-mcp` | Python | Repo creation & metadata |
| `notebooklm-mcp` | Python | Google NotebookLM research |
| `telegram-mcp` | Python/FastMCP | Telegram notifications & approvals (7 tools) |
| `desci-research-mcp` | Python/FastMCP | arXiv/Semantic Scholar academic search |
| `DailyNews/src/antigravity_mcp` | Python/FastMCP | Content publishing pipeline (15 tools) |

### Automation Scripts

- `scripts/orchestrator.py` - Cross-project pipeline (collect→validate→generate→publish→track)
- `scripts/cost_intelligence.py` - LLM cost analysis, forecasting, optimization suggestions
- `scripts/linear_sync.py` - ROADMAP.md → Linear issue sync
- `scripts/check_security.py` - Secret/API key scanner for pre-commit and Claude Code Hooks
- `getdaytrends/firecrawl_bridge.py` - Firecrawl integration for enriched trend contexts
- `getdaytrends/firecrawl_client.py` - Firecrawl API async client with rate limiting

### Custom Skills (`.agent/skills/`)

- `cost-intelligence` - LLM cost report & optimization
- `content-performance` - Published content performance tracking & feedback loops
- `content-publisher` - Notion/Markdown to Blog/Newsletter converter
- `deep-research` - Multi-source deep research
- `project-organizer` - Project folder organization & history
- `web-auditor` - SEO and performance audits
- `youtube-intelligence` - YouTube video transcript analysis


## Environment Variables

Copy `.env.example` files before running. Key variables:
- `GEMINI_API_KEY` / `GOOGLE_API_KEY` - LLM embeddings + analysis
- `OPENAI_API_KEY` - Fallback LLM provider
- `VITE_FIREBASE_*` - Frontend Firebase config
- `GOOGLE_APPLICATION_CREDENTIALS` - Backend Firebase service account
- `PRIVATE_KEY` - Wallet key for contract deployment (Hardhat test key OK for local)
- `PINATA_API_KEY` / `PINATA_API_SECRET` - IPFS uploads
- `ALLOW_TEST_BYPASS=true` - Dev only: enables test auth token
- `SENTRY_DSN` - Error monitoring (Sentry)
- `FIRECRAWL_API_KEY` - Web crawling for trend enrichment
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` - Telegram notifications
- `LINEAR_API_KEY` - Linear project management sync

## Code Style & Conventions

- **Python**: Requirements pinned to Python 3.12 / 3.13 due to `langchain`/`google.genai` compatibility with 3.14+. No type stubs required. Use `# type: ignore` for third-party libs. Singleton pattern via `get_*()` factory functions.
- **React**: Functional components only. Tailwind CSS for styling. Framer Motion for animations. `useId()` for generated IDs (not `Math.random()`).
- **Solidity**: OpenZeppelin v5 contracts. Pragma `^0.8.20`. Hardhat for testing.
- **Error handling**: FastAPI endpoints wrap DB ops in try/except with `db.rollback()`. Frontend uses ErrorBoundary + ToastContext.

## Gotchas

- `vector_store.py` `search_similar()` returns `List[Tuple[RFPDocument, float]]` - always unpack as `for doc, score in results`
- biolinker CORS defaults to localhost in dev; set `ENV=production` + `ALLOWED_ORIGINS` for deployment
- `DeSciToken.sol` lives in `contracts/` root (not `contracts/contracts/`) due to prior move
- DailyNews `.env` has real API keys - never commit. `.gitignore` covers `.env` globally
- Frontend uses React 19 + React Router 7 - check compatibility when updating deps
- AgriGuard uses SQLite (`agriguard.db`) - not suitable for production concurrency
