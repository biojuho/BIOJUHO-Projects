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

## Environment Variables

Copy `.env.example` files before running. Key variables:
- `GEMINI_API_KEY` / `GOOGLE_API_KEY` - LLM embeddings + analysis
- `OPENAI_API_KEY` - Fallback LLM provider
- `VITE_FIREBASE_*` - Frontend Firebase config
- `GOOGLE_APPLICATION_CREDENTIALS` - Backend Firebase service account
- `PRIVATE_KEY` - Wallet key for contract deployment (Hardhat test key OK for local)
- `PINATA_API_KEY` / `PINATA_API_SECRET` - IPFS uploads
- `ALLOW_TEST_BYPASS=true` - Dev only: enables test auth token

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
