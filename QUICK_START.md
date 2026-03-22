# AI Projects Workspace - Quick Start Guide

**Last Updated**: 2026-03-22
**Target Audience**: New team members, contributors
**Estimated Setup Time**: 30 minutes

---

## 🎯 Prerequisites

### Required Tools

| Tool | Version | Check Command | Install |
|------|---------|---------------|---------|
| **Python** | 3.13.3 | `python --version` | [python.org](https://www.python.org/downloads/) |
| **Node.js** | 22.12.0+ | `node --version` | [nodejs.org](https://nodejs.org/) |
| **Docker** | Latest | `docker --version` | [docker.com](https://www.docker.com/get-started) |
| **Git** | Latest | `git --version` | [git-scm.com](https://git-scm.com/) |

### Optional (Recommended)

- **pyenv** or **asdf** - Python version management
- **nvm** - Node.js version management
- **uv** - Fast Python package manager

---

## 🚀 Quick Start (5 Minutes)

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/biojuho/BIOJUHO-Projects.git
cd BIOJUHO-Projects

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your API keys (required)
# - GEMINI_API_KEY
# - OPENAI_API_KEY (optional)
# - ANTHROPIC_API_KEY (optional)
# - Other service keys as needed

# 4. Start all services
docker compose up -d

# 5. Check services
docker compose ps

# 6. View logs
docker compose logs -f biolinker
```

**Services Available**:
- 🌐 Frontend: http://localhost:5173
- 🔌 Biolinker API: http://localhost:8000
- 🌾 AgriGuard API: http://localhost:8002
- 🐘 PostgreSQL: localhost:5432

### Option 2: Local Development (Manual)

```bash
# 1. Clone repository
git clone https://github.com/biojuho/BIOJUHO-Projects.git
cd BIOJUHO-Projects

# 2. Set Python version (if using pyenv)
pyenv install 3.13.3
pyenv local 3.13.3

# 3. Set Node.js version (if using nvm)
nvm install 22.12.0
nvm use 22.12.0

# 4. Install pre-commit hooks
pip install pre-commit
pre-commit install

# 5. Install Python dependencies (example: biolinker)
cd desci-platform/biolinker
pip install -r requirements.txt

# 6. Install Node.js dependencies (example: frontend)
cd ../frontend
npm install

# 7. Start individual services (see CLAUDE.md for details)
```

---

## 🔐 Environment Setup

### 1. Copy Template

```bash
cp .env.example .env
```

### 2. Get API Keys

| Service | Get Key From | Required? | Notes |
|---------|--------------|-----------|-------|
| **Gemini** | [Google AI Studio](https://makersuite.google.com/app/apikey) | ✅ Yes | Free tier: 1,000 RPD |
| **OpenAI** | [platform.openai.com](https://platform.openai.com/api-keys) | ⚠️ Fallback | Required for fallback chain |
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com/) | ⚠️ Optional | For Claude models |
| **Firebase** | [console.firebase.google.com](https://console.firebase.google.com/) | ✅ Yes | For authentication |

### 3. Essential Environment Variables

```env
# Minimum required for development
GEMINI_API_KEY=your_key_here
POSTGRES_PASSWORD=your_secure_password
VITE_API_URL=http://localhost:8000
```

---

## 🧪 Verify Installation

### 1. Check Python Version

```bash
python --version
# Expected: Python 3.13.3
```

### 2. Check Node.js Version

```bash
node --version
# Expected: v22.12.0 or higher
```

### 3. Test Pre-commit Hooks

```bash
pre-commit run --all-files
# Should pass all checks
```

### 4. Test Docker Services

```bash
docker compose up -d
docker compose ps
# All services should be "Up" and healthy
```

### 5. Test API Endpoints

```bash
# Biolinker API
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# AgriGuard API
curl http://localhost:8002/health
# Expected: {"status":"healthy"}

# Frontend
curl http://localhost:5173
# Expected: HTML response
```

---

## 📁 Project Structure

```
AI Projects/
├── desci-platform/           # DeSci Platform
│   ├── biolinker/           # FastAPI backend (port 8000)
│   ├── frontend/            # React frontend (port 5173)
│   └── contracts/           # Solidity smart contracts
├── AgriGuard/               # Agricultural supply chain
│   └── backend/             # FastAPI backend (port 8002)
├── DailyNews/               # X Growth Engine + Notion automation
├── shared/                  # Shared libraries (LLM config, etc.)
├── scripts/                 # Automation scripts
├── docs/                    # Documentation
├── .env                     # Environment variables (NEVER commit!)
├── .env.example             # Template for .env
├── docker-compose.yml       # Multi-service setup
├── .python-version          # Python version (3.13.3)
├── .nvmrc                   # Node.js version (22.12.0)
└── .pre-commit-config.yaml  # Git hooks configuration
```

---

## 🛠️ Common Development Tasks

### Run Tests

```bash
# Python tests
pytest

# With coverage
pytest --cov --cov-report=html

# Frontend tests
cd desci-platform/frontend
npm test
```

### Run Linters

```bash
# Python (Ruff)
ruff check .
ruff format .

# JavaScript/TypeScript (ESLint)
npm run lint
```

### Database Migrations

```bash
# Generate migration
cd AgriGuard/backend
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Build for Production

```bash
# Frontend
cd desci-platform/frontend
npm run build

# Smart contracts
cd desci-platform/contracts
npx hardhat compile
```

---

## 🐛 Troubleshooting

### Issue: "Python version mismatch"

```bash
# Check current version
python --version

# If wrong version, use pyenv
pyenv install 3.13.3
pyenv local 3.13.3
```

### Issue: "Node modules not found"

```bash
# Clean install
rm -rf node_modules package-lock.json
npm install
```

### Issue: "Docker compose fails"

```bash
# Check Docker is running
docker ps

# Clean restart
docker compose down -v
docker compose up -d

# View logs
docker compose logs -f
```

### Issue: "Pre-commit hooks fail"

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Update hooks
pre-commit autoupdate
```

### Issue: "Database connection refused"

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check connection string in .env
# Should be: postgresql://user:password@localhost:5432/dbname

# For Docker internal network:
# postgresql://user:password@postgres:5432/dbname
```

---

## 📚 Next Steps

### 1. Read Documentation

- [CLAUDE.md](CLAUDE.md) - Project overview and commands
- [SYSTEM_AUDIT_ACTION_PLAN.md](SYSTEM_AUDIT_ACTION_PLAN.md) - Roadmap
- [docs/POSTGRESQL_MIGRATION_PLAN.md](docs/POSTGRESQL_MIGRATION_PLAN.md) - DB migration

### 2. Join Team Channels

- GitHub Discussions - For questions and proposals
- Linear - For sprint planning and task tracking
- Telegram (optional) - For automated notifications

### 3. Make Your First Contribution

```bash
# 1. Create a feature branch
git checkout -b feature/your-feature-name

# 2. Make changes
# ... edit code ...

# 3. Run tests
pytest
npm test

# 4. Pre-commit checks
pre-commit run --all-files

# 5. Commit (hooks will run automatically)
git add .
git commit -m "feat: add new feature"

# 6. Push and create PR
git push origin feature/your-feature-name
```

### 4. Review Key Concepts

- **LLM Cost Optimization**: See `shared/llm/config.py` for tier-based routing
- **MCP Servers**: 6 specialized servers for different capabilities
- **Security**: Pre-commit hooks prevent secret leaks
- **Testing**: Aim for 70% coverage (check with pytest-cov)

---

## 🆘 Getting Help

### Resources

- **Documentation**: Start with [CLAUDE.md](CLAUDE.md)
- **Issues**: Check [GitHub Issues](https://github.com/biojuho/BIOJUHO-Projects/issues)
- **Troubleshooting**: See section above
- **Code Examples**: Look at existing tests in `tests/` directories

### Team Contacts

| Area | Contact | Notes |
|------|---------|-------|
| Backend | Backend Lead | FastAPI, LLM, databases |
| Frontend | Frontend Lead | React, Vite, UI/UX |
| DevOps | DevOps Lead | Docker, CI/CD, infrastructure |
| Blockchain | Smart Contract Lead | Solidity, Hardhat, Web3 |

---

## ✅ Installation Checklist

Use this checklist to verify your setup:

- [ ] Python 3.13.3 installed
- [ ] Node.js 22.12.0+ installed
- [ ] Docker installed and running
- [ ] Repository cloned
- [ ] `.env` file created from `.env.example`
- [ ] API keys added to `.env`
- [ ] Pre-commit hooks installed (`pre-commit install`)
- [ ] Docker Compose services started (`docker compose up -d`)
- [ ] All services healthy (`docker compose ps`)
- [ ] Frontend accessible at http://localhost:5173
- [ ] Biolinker API accessible at http://localhost:8000
- [ ] Tests passing (`pytest`)
- [ ] Linters passing (`ruff check .`)
- [ ] First commit made successfully

---

## 🎉 Welcome to the Team!

You're all set! If you run into any issues, don't hesitate to:

1. Check the troubleshooting section above
2. Search existing GitHub Issues
3. Ask in team chat
4. Create a new issue with the `question` label

Happy coding! 🚀

---

**Last Updated**: 2026-03-22
**Maintainer**: Tech Lead
**Version**: 1.0
