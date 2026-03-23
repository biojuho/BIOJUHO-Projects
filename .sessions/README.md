# Session Logs

**Purpose**: Track AI agent work sessions for continuity across context windows.

---

## 📁 Directory Structure

```
.sessions/
├── SESSION_LOG_2026-03-23.md    # Today's active log
├── SESSION_LOG_2026-03-22.md    # Recent logs (last 7 days)
├── cleanup.py                   # Automatic log rotation script
├── archive/                     # Logs older than 7 days
│   └── SESSION_LOG_2026-03-15.md
└── README.md                    # This file
```

---

## 🔄 Log Rotation Policy

- **Retention**: 7 days
- **Frequency**: Run `cleanup.py` daily or per session
- **Archive Location**: `.sessions/archive/`

### Manual Cleanup
```bash
python .sessions/cleanup.py
```

### Automatic Cleanup (Git Hook)
Add to `.git/hooks/post-commit`:
```bash
#!/bin/bash
python .sessions/cleanup.py
```

---

## 📝 Log Format

Each session log should include:
- **Agent**: Which AI tool (Claude Code, Gemini, Codex, etc.)
- **Session Start**: Date/time
- **Objectives**: What the session aims to accomplish
- **Actions Taken**: Chronological work log
- **Files Modified**: List of changed files
- **Next Agent TODO**: Handoff tasks

---

## 🔗 Related Files

- [HANDOFF.md](../HANDOFF.md) - Current status relay (50 lines max)
- [TASKS.md](../TASKS.md) - Kanban task board
- [.agent/workflows/](../.agent/workflows/) - Agent workflow guides
