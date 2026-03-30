# AgriGuard × DeSci Platform — Technical Whitepaper
*Version 1.0 | March 2026*

---

## Abstract

This whitepaper presents a dual blockchain platform combining agricultural supply chain traceability (AgriGuard) with decentralized science infrastructure (DeSci/BioLinker). The system leverages Ethereum smart contracts, IPFS decentralized storage, real-time IoT monitoring, and token economics to create transparent, incentivized ecosystems for food safety and scientific research.

---

## 1. System Architecture

### 1.1 Overview

The platform consists of two complementary applications sharing common infrastructure:

| Layer | AgriGuard | DeSci Platform |
|---|---|---|
| **Frontend** | React + Vite + TailwindCSS | React + Vite + TailwindCSS |
| **Backend** | FastAPI + SQLAlchemy | FastAPI + ChromaDB |
| **Storage** | SQLite / PostgreSQL | IPFS (Pinata) + Firestore |
| **Blockchain** | AgriGuard.sol | DSCIToken.sol + BioLinker.sol + DeSciDAO.sol |
| **Infra** | Docker + Nginx HTTPS | Docker + Nginx HTTPS |

### 1.2 Security

- **HTTPS**: Nginx reverse proxy with TLS 1.3
- **Rate Limiting**: 30 req/s per IP, burst 20
- **API Auth**: Firebase JWT verification
- **Consent Hashing**: SHA-256 on-chain audit trail for legal compliance
- **WebSocket**: Authenticated IoT data feeds

---

## 2. AgriGuard: Supply Chain Traceability

### 2.1 Product Lifecycle

```
Farmer → Harvester → Transporter → Warehouse → Retailer → Consumer
  │          │            │             │          │          │
  └── QR ────┴── QR ──────┴─── QR ──────┴── QR ───┴── QR ───┘
             Blockchain Event Records
```

Each lifecycle transition is recorded as a `TrackingEvent` with:
- **product_id**: unique product identifier
- **timestamp**: ISO 8601 UTC
- **status**: lifecycle stage (Planted → Harvested → In Transit → Delivered → Quality Check)
- **location**: GPS zone or facility name
- **handler_id**: responsible entity

### 2.2 Cold-Chain IoT Monitoring

Real-time temperature and humidity monitoring via WebSocket:

- **Sampling Rate**: 5-second intervals
- **Sensors**: Temperature (-30°C to 50°C), Humidity (0-100%)
- **Alert Thresholds**: Temp > 8°C or < -25°C, Humidity > 85% or < 30%
- **Data Retention**: 2,000 readings in-memory, persistent archival to DB
- **Zone Aggregation**: Per-zone averages, min/max, alert counts

### 2.3 Smart Contract

```solidity
contract AgriGuard {
    struct Product {
        string name;
        string origin;
        address owner;
        bool verified;
    }

    mapping(uint256 => Product) public products;
    mapping(uint256 => TrackingEvent[]) public history;

    function registerProduct(...) external;
    function addTrackingEvent(...) external;
    function verifyProduct(uint256 id) external;
}
```

---

## 3. DeSci Platform: Decentralized Science

### 3.1 Research Paper Lifecycle

```
Upload → IPFS Storage → NFT Minting → Peer Review → Token Reward
                           │
                    Consent Hash (SHA-256)
                    → On-chain Audit Trail
```

### 3.2 Token Economics (DSCI)

| Action | Reward | Contract Function |
|---|---|---|
| Paper Upload | 100 DSCI | `rewardPaperUpload()` |
| Peer Review | 50 DSCI | `rewardPeerReview()` |
| Data Sharing | 200 DSCI | `rewardDataShare()` |

**Total Supply**: Governed by DSCIToken.sol (ERC-20)
**Distribution**: 40% Community Rewards, 25% Treasury, 20% Team, 15% Investors

### 3.3 DAO Governance (DeSciDAO.sol)

```
proposalCount = 0

createProposal(title, description)
  → requires 100 DSCI minimum balance
  → voting period: 3 days
  → quorum: 10% of total supply

vote(proposalId, support)
  → weight = balanceOf(voter)
  → 1 DSCI = 1 vote

executeProposal(proposalId)
  → requires: passed + quorum met + voting ended
```

### 3.4 IP-NFT (BioLinker.sol)

Each uploaded paper receives an IP-NFT containing:
- **token_uri**: IPFS CID of the paper
- **consent_hash**: SHA-256(timestamp + wallet + IPFS CID)
- **consent_timestamp**: ISO 8601 UTC

This creates an immutable, on-chain record of intellectual property ownership and legal consent.

---

## 4. AI Agent Services

### 4.1 BioLinker AI

- **RFP Matching**: ChromaDB vector search for grant opportunity matching
- **Smart Matching**: Automated asset-to-RFP scoring (0-100)
- **Proposal Generation**: LLM-powered draft generation with critique loop
- **Literature Review**: Multi-source academic paper synthesis

### 4.2 News & Trends Bot

- **Multi-source RSS**: 40+ curated technology news feeds
- **LLM Summarization**: Gemini Pro API with fallback chain (Anthropic → Gemini → Grok → OpenAI)
- **Canva Integration**: Automated infographic generation
- **Notion CMS**: Automated page creation with rich blocks

---

## 5. Infrastructure

### 5.1 Deployment

```yaml
# Docker Compose Stack
services:
  nginx:        # HTTPS reverse proxy (443)
  backend:      # FastAPI + SQLAlchemy / ChromaDB
  frontend:     # React SPA (built assets)
  chromadb:     # Vector database
```

### 5.2 CI/CD

GitHub Actions pipelines for both projects:
- **Backend**: pip install → seed_db → pytest
- **Frontend**: npm ci → lint → build → test
- **Contracts**: npm ci → hardhat test

### 5.3 Internationalization

- **Framework**: react-i18next
- **Languages**: Korean (default), English
- **Persistence**: localStorage-based language preference

---

## 6. Roadmap

| Phase | Timeline | Deliverables |
|---|---|---|
| V1: MVP | 2026 Q1 ✅ | Core APIs, basic UI, mock blockchain |
| V2: Stability | 2026 Q1 ✅ | Timeouts, locks, proofreading |
| V3: Visual | 2026 Q1 ✅ | Framer Motion, Canva, CI/CD |
| V4: Production | 2026 Q2 | HTTPS, DAO, IoT, i18n, IR |
| V5: Mainnet | 2026 Q3 | Ethereum mainnet, partner pilots |
| V6: Scale | 2026 Q4 | Token sale, global expansion |

---

## 7. References

1. Ethereum Foundation. *Solidity Documentation*. https://docs.soliditylang.org
2. IPFS Protocol. *Content Addressing*. https://docs.ipfs.tech
3. WHO. *Food Safety Fact Sheet*. https://www.who.int/news-room/fact-sheets/detail/food-safety
4. DeSci Foundation. *Decentralized Science*. https://desci.com
