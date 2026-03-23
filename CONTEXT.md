# 🧭 Context Guide

**Purpose**: Lightweight context file for AI agents - avoids duplication with CLAUDE.md.

**Last Updated**: 2026-03-23

---

## 📚 Documentation Hierarchy

**Use this hierarchy to find information**:

1. **[HANDOFF.md](HANDOFF.md)** (50 lines) - Current session status, next actions
2. **[TASKS.md](TASKS.md)** - Active task board (TODO/IN_PROGRESS/DONE)
3. **[CLAUDE.md](CLAUDE.md)** - Full technical documentation (architecture, commands, gotchas)
4. **[CONTEXT.md](CONTEXT.md)** (this file) - Navigation guide + AI agent instructions
5. **[.agent/workflows/](\.agent\workflows\)** - Standardized workflows for AI agents
6. **[.sessions/](\.sessions\)** - Session logs (7-day retention)

---

## 🤖 For AI Agents: Quick Start

### Before Starting Work

1. **Read HANDOFF.md** - Get current status (30 seconds)
2. **Check TASKS.md** - See what's in progress (1 minute)
3. **Review relevant workflow** - Follow standardized procedure (if applicable)
4. **Update TASKS.md** - Move task to IN_PROGRESS

### During Work

1. **Use TodoWrite tool** - Track progress in real-time
2. **Follow workflow checklist** - Ensure quality and consistency
3. **Update SESSION_LOG** - Document decisions and changes

### After Completion

1. **Update TASKS.md** - Move to DONE with results
2. **Update HANDOFF.md** - Summarize for next agent (keep under 50 lines)
3. **Create/update SESSION_LOG** - Record session details
4. **Run cleanup** - `python .sessions/cleanup.py` (optional)

---

## 🎯 Common Tasks → Documentation Lookup

| What You Need | Where to Look | Estimated Read Time |
|---------------|---------------|---------------------|
| **Current work status** | [HANDOFF.md](HANDOFF.md) | 30 seconds |
| **Active tasks** | [TASKS.md](TASKS.md) | 1 minute |
| **Project architecture** | [CLAUDE.md](CLAUDE.md) - Architecture section | 5 minutes |
| **Setup instructions** | [CLAUDE.md](CLAUDE.md) - Commands section | 3 minutes |
| **Environment variables** | [CLAUDE.md](CLAUDE.md) - Environment Variables section | 2 minutes |
| **Code style conventions** | [CLAUDE.md](CLAUDE.md) - Code Style section | 3 minutes |
| **Gotchas/Known issues** | [CLAUDE.md](CLAUDE.md) - Gotchas section | 2 minutes |
| **Refactoring procedure** | [.agent/workflows/code-refactoring-workflow.md](.agent/workflows/code-refactoring-workflow.md) | 10 minutes |
| **Tool selection** | [.agent/TOOL_CAPABILITIES.md](.agent/TOOL_CAPABILITIES.md) | 5 minutes |
| **Recent session history** | [.sessions/SESSION_LOG_*.md](.sessions/) | 3 minutes |

---

## 🗂️ Project Quick Reference

**9 Projects in this Monorepo**:

| Project | Status | Main File | Lines | Quality |
|---------|--------|-----------|-------|---------|
| `getdaytrends` | ⭐⭐⭐⭐⭐ | main.py | 358 | Refactored (2026-03-23) |
| `desci-platform/biolinker` | ⭐⭐⭐⭐⭐ | main.py | 198 | Excellent |
| `desci-platform/frontend` | ⭐⭐⭐⭐⭐ | - | - | React 19 |
| `desci-platform/contracts` | ⭐⭐⭐⭐⭐ | - | - | Solidity 0.8.20 |
| `content-intelligence` | ⭐⭐⭐⭐⭐ | main.py | 304 | Best practice |
| `lyria-music-player` | ⭐⭐⭐⭐⭐ | main.py | 109 | Perfect CLI |
| `DailyNews` | ⭐⭐⭐⭐ | src/antigravity_mcp/server.py | 255 | Good |
| `AgriGuard` | ⭐⭐⭐⭐ | backend/main.py | 324 | Good |
| `instagram-automation` | ⭐⭐⭐⭐ | main.py | 599 | Good (optional improvement) |

**Details**: See [COMPREHENSIVE_PROJECT_HEALTH_REPORT.md](COMPREHENSIVE_PROJECT_HEALTH_REPORT.md)

---

## 🛠️ AI Agent Tool Selection

**Quick Reference** (See [.agent/TOOL_CAPABILITIES.md](.agent/TOOL_CAPABILITIES.md) for details):

- **Deep Refactoring** → Claude Code
- **Fast Edits** → Cursor AI / Copilot
- **Research** → Gemini Code Assist
- **Documentation** → Claude Code / Gemini
- **Debugging** → Cursor AI

---

## ⚠️ Important Notes

### Don't Duplicate Information
- **CLAUDE.md** has full technical details
- **CONTEXT.md** (this file) is just a navigation guide
- **HANDOFF.md** has current session status only

### Update Frequency
- **HANDOFF.md** - Every session
- **TASKS.md** - Real-time during work
- **SESSION_LOG** - Every session
- **CONTEXT.md** - Only when structure changes
- **CLAUDE.md** - When architecture changes

### Cleanup Schedule
- **Session logs** - 7 days (run `.sessions/cleanup.py`)
- **TASKS.md DONE section** - Archive after 7 days
- **Old refactoring reports** - Keep indefinitely (reference)

---

## 🔗 External Resources

- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Python Code Quality Guide](https://docs.python-guide.org/writing/structure/)
- [React 19 Documentation](https://react.dev/)
- [Hardhat Documentation](https://hardhat.org/docs)

---

## 📊 Monorepo Statistics

**Last Updated**: 2026-03-23

- **Total Projects**: 9
- **Total Lines of Code**: ~15,000 (excluding node_modules, venv)
- **Languages**: Python (70%), TypeScript (20%), Solidity (5%), Shell (5%)
- **Average Project Health**: 4.67/5 stars
- **Active Development**: Yes (daily commits)
- **Test Coverage**: Varies by project (see individual READMEs)

---

**🤖 For AI Agents**: This file is your starting point. Always read HANDOFF.md first, then follow the documentation hierarchy.

**📝 Keep This File Light**: Target < 150 lines. For details, link to CLAUDE.md or other docs.
