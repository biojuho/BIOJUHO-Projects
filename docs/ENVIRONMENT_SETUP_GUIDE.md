# Environment Setup Guide

**Last Updated**: 2026-03-24

This document provides comprehensive guidance for setting up environment variables across all projects in the AI Projects workspace.

## Quick Start

```bash
# 1. Copy root .env template
cp .env.example .env

# 2. Copy project-specific templates
cp desci-platform/biolinker/.env.example desci-platform/biolinker/.env
cp desci-platform/frontend/.env.example desci-platform/frontend/.env
cp AgriGuard/backend/.env.example AgriGuard/backend/.env
cp getdaytrends/.env.example getdaytrends/.env
cp DailyNews/.env.example DailyNews/.env

# 3. Fill in your API keys (see sections below)
```

## Critical Variables (Required for Docker Compose)

These variables must be set in root `.env` for `docker compose up` to work:

### Gemini AI (Required)
```bash
GEMINI_API_KEY=your_key_here
# Get from: https://aistudio.google.com/apikey
# Used by: biolinker, getdaytrends, DailyNews
```

### Firebase (Required for DeSci Platform)
```bash
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
# Get from: Firebase Console > Project Settings > Your apps
# Used by: desci-platform/frontend
```

### Notion (Required for getdaytrends)
```bash
NOTION_TOKEN=secret_xxx
GETDAYTRENDS_NOTION_DATABASE_ID=xxx
# Get from: https://www.notion.so/my-integrations
# Used by: getdaytrends storage, DailyNews
```

### Telegram (Required for Alerts)
```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=your_chat_id
# Get from: @BotFather on Telegram
# Used by: getdaytrends alerts, DailyNews notifications
```

### Web3 (Required for AgriGuard)
```bash
WEB3_PROVIDER_URI=https://sepolia.infura.io/v3/YOUR_PROJECT_ID
AGRIGUARD_PRIVATE_KEY=0x...
# Get from: Infura/Alchemy for provider, MetaMask for private key
# Used by: AgriGuard blockchain integration
```

## Optional Variables

### OpenAI (Fallback LLM)
```bash
OPENAI_API_KEY=sk-proj-...
# Used by: shared/llm as fallback provider
```

### X/Twitter API
```bash
X_API_KEY=your_key
X_API_SECRET=your_secret
X_ACCESS_TOKEN=your_token
X_ACCESS_SECRET=your_token_secret
# Used by: DailyNews X publishing, getdaytrends X client
```

### Google Sheets (Alternative Storage)
```bash
GOOGLE_SHEETS_ID=your_sheet_id
# Used by: getdaytrends alternative to Notion
```

### Firecrawl (Enhanced Web Scraping)
```bash
FIRECRAWL_API_KEY=fc-xxx
# Used by: getdaytrends context enrichment
```

### Sentry (Error Monitoring)
```bash
SENTRY_DSN=https://xxx@sentry.io/xxx
# Used by: All FastAPI services
```

## Environment Variable Priority

1. **Project `.env`** (highest priority)
2. **Root `.env`**
3. **System environment variables**
4. **Default values in code** (lowest priority)

Example:
```
getdaytrends/.env        # GEMINI_API_KEY=project_specific_key (used)
.env                     # GEMINI_API_KEY=shared_key (ignored for getdaytrends)
```

## Validation

### Check Docker Compose Variables
```bash
docker compose config 2>&1 | grep -i warning
```

Expected warnings if .env not set:
- `GEMINI_API_KEY is not set`
- `WEB3_PROVIDER_URI is not set`
- etc.

### Validate Project-Specific Variables
```bash
# getdaytrends
cd getdaytrends
python -c "from config import AppConfig; print(AppConfig().editorial_profile)"

# DailyNews
cd DailyNews
python scripts/collect_news.py --help

# biolinker
cd desci-platform/biolinker
python -c "from services.settings import Settings; print(Settings().gemini_api_key[:10])"
```

## Security Best Practices

### ✅ Do
- Add `.env` to `.gitignore` (already done)
- Use different API keys for dev/staging/prod
- Rotate keys regularly
- Use `.env.example` as template with dummy values
- Store production keys in secure vault (e.g., 1Password, AWS Secrets Manager)

### ❌ Don't
- Commit `.env` files
- Share API keys in Slack/Discord
- Use production keys in development
- Hardcode keys in source code
- Log full API keys (mask with `key[:10] + '...'`)

## Pre-commit Security Checks

The repository includes Gitleaks pre-commit hook that scans for:
- API keys
- Private keys
- Tokens
- Passwords

If commit is blocked:
```bash
# Review the detected secret
git diff --staged

# If false positive, add to .gitleaksignore
echo "path/to/file:line_number" >> .gitleaksignore

# If real secret, remove it and use environment variable instead
```

## Troubleshooting

### Docker Compose "variable is not set"
**Problem**: Warning during `docker compose config`
**Solution**: Create `.env` in project root with required variables

### Import Error: API Key Not Found
**Problem**: `KeyError: 'GEMINI_API_KEY'`
**Solution**:
1. Check `.env` file exists
2. Verify variable name matches exactly (case-sensitive)
3. Restart Python interpreter to reload environment

### Firebase Auth Fails in Frontend
**Problem**: "Firebase: Error (auth/invalid-api-key)"
**Solution**:
1. Check `desci-platform/frontend/.env`
2. Verify all `VITE_FIREBASE_*` variables are set
3. Rebuild: `npm run build`
4. Clear browser cache

### Notion API 401 Unauthorized
**Problem**: `HTTPError: 401 Client Error: Unauthorized`
**Solution**:
1. Regenerate integration token at notion.so/my-integrations
2. Share database with integration
3. Update `NOTION_TOKEN` in `.env`

## Environment Variable Reference

See individual `.env.example` files:
- [Root .env.example](.env.example)
- [biolinker .env.example](../desci-platform/biolinker/.env.example)
- [frontend .env.example](../desci-platform/frontend/.env.example)
- [AgriGuard .env.example](../AgriGuard/backend/.env.example)
- [getdaytrends .env.example](../getdaytrends/.env.example)
- [DailyNews .env.example](../DailyNews/.env.example)

## Related Documentation

- [Pre-commit Setup Guide](./PRE_COMMIT_SETUP.md)
- [Docker Deployment Guide](../getdaytrends/DOCKER_DEPLOYMENT.md)
- [AgriGuard PostgreSQL Migration](./POSTGRESQL_MIGRATION_PLAN.md)

---

**Questions?** Open an issue or check CLAUDE.md for project architecture.
