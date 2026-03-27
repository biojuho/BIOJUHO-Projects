# getdaytrends Docker Deployment Guide

**Created**: 2026-03-23
**Version**: v4.0 (Post-Refactoring)

---

## Quick Start

### 1. Build and Run with Docker Compose

```bash
# From project root
cd "d:\AI 프로젝트"

# Build the image
docker compose build getdaytrends

# Run one-shot dry-run test
docker compose run --rm getdaytrends python main.py --one-shot --dry-run --limit 3

# Start scheduler service
docker compose up -d getdaytrends

# View logs
docker compose logs -f getdaytrends

# Stop service
docker compose down getdaytrends
```

---

## Environment Variables

Required environment variables in root `.env`:

```env
# === getdaytrends Configuration ===

# Storage
GETDAYTRENDS_STORAGE_TYPE=notion
NOTION_TOKEN=your_notion_token_here
GETDAYTRENDS_NOTION_DATABASE_ID=your_database_id_here

# LLM API Keys
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
OPENAI_API_KEY=your_openai_key

# Schedule
GETDAYTRENDS_SCHEDULE_INTERVAL=240    # 4 hours
GETDAYTRENDS_COUNTRY=korea
GETDAYTRENDS_LIMIT=10

# Features
GETDAYTRENDS_ENABLE_CLUSTERING=true
GETDAYTRENDS_ENABLE_LONG_FORM=true
GETDAYTRENDS_MIN_VIRAL_SCORE=60
GETDAYTRENDS_LONG_FORM_MIN_SCORE=95

# Alerts (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
```

---

## Standalone Docker Build (without docker-compose)

```bash
# Build from project root (includes shared modules)
cd "d:\AI 프로젝트"
docker build -f getdaytrends/Dockerfile -t getdaytrends:latest .

# Run one-shot
docker run --rm \
  --env-file .env \
  -v "$(pwd)/getdaytrends/data:/app/getdaytrends/data" \
  getdaytrends:latest \
  python main.py --one-shot --dry-run --limit 5

# Run scheduler mode
docker run -d \
  --name getdaytrends \
  --env-file .env \
  -v "$(pwd)/getdaytrends/data:/app/getdaytrends/data" \
  -v "$(pwd)/getdaytrends/logs:/app/getdaytrends/logs" \
  --restart unless-stopped \
  getdaytrends:latest
```

---

## Testing in Docker

### Test 1: Help Command
```bash
docker compose run --rm getdaytrends python main.py --help
```

**Expected**: Usage information displayed

### Test 2: Dry Run (3 trends)
```bash
docker compose run --rm getdaytrends python main.py --one-shot --dry-run --limit 3 --verbose
```

**Expected**: Collects 3 trends, analyzes, but doesn't save

### Test 3: Stats Check
```bash
docker compose run --rm getdaytrends python main.py --stats
```

**Expected**: Shows historical trend statistics (if DB exists)

---

## Volume Mounts

The docker-compose configuration mounts:

- `./getdaytrends/data` → SQLite database persistence
- `./getdaytrends/logs` → Application logs

These directories are created automatically on first run.

---

## Health Check

The container includes a basic health check:

```yaml
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3
```

Check status:
```bash
docker inspect --format='{{.State.Health.Status}}' getdaytrends
```

---

## Scheduler Mode vs One-Shot

### Scheduler Mode (default)
Runs continuously, executing pipeline every `SCHEDULE_INTERVAL_MINUTES`:

```bash
docker compose up -d getdaytrends
```

### One-Shot Mode (for cron/manual)
Runs once and exits:

```bash
docker compose run --rm getdaytrends python main.py --one-shot
```

---

## Logs and Monitoring

### View Real-Time Logs
```bash
docker compose logs -f getdaytrends
```

### Check Last 100 Lines
```bash
docker compose logs --tail=100 getdaytrends
```

### Export Logs
```bash
docker compose logs getdaytrends > getdaytrends_logs.txt
```

---

## Troubleshooting

### Container Won't Start

1. Check environment variables:
   ```bash
   docker compose config
   ```

2. Inspect logs:
   ```bash
   docker compose logs getdaytrends
   ```

3. Run interactive shell:
   ```bash
   docker compose run --rm getdaytrends /bin/bash
   ```

### Import Errors

The Dockerfile sets `PYTHONPATH=/app` to include shared modules. Verify:

```bash
docker compose run --rm getdaytrends python -c "import shared; print('shared module found')"
```

### Database Permissions

Ensure data directory is writable:

```bash
# On host
chmod 755 getdaytrends/data
```

---

## Production Deployment

### Using Docker Compose (Recommended)

1. **Set environment variables** in `.env`
2. **Start service**:
   ```bash
   docker compose up -d getdaytrends
   ```
3. **Verify**:
   ```bash
   docker compose ps
   docker compose logs getdaytrends
   ```

### Using systemd with Docker

Create `/etc/systemd/system/getdaytrends-docker.service`:

```ini
[Unit]
Description=GetDayTrends Docker Container
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/AI 프로젝트
ExecStart=/usr/bin/docker compose up -d getdaytrends
ExecStop=/usr/bin/docker compose down getdaytrends
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable getdaytrends-docker
sudo systemctl start getdaytrends-docker
```

---

## Comparison: Docker vs Windows Scheduler vs Systemd

| Method | OS | Isolation | Persistence | Best For |
|--------|----|--------------|-------------|----------|
| **Docker Compose** | Any | ✅ High | ✅ Volumes | Development, Multi-service |
| **Windows Scheduler** | Windows | ❌ None | ✅ Local DB | Windows production |
| **Systemd** | Linux | ❌ None | ✅ Local DB | Linux production |
| **Docker + systemd** | Linux | ✅ High | ✅ Volumes | Linux production (best) |

---

## Update Deployment

### Rebuild After Code Changes

```bash
# Rebuild image
docker compose build getdaytrends

# Restart service
docker compose up -d getdaytrends

# Or do both
docker compose up -d --build getdaytrends
```

### Rolling Update (Zero Downtime)

```bash
# Build new image
docker compose build getdaytrends

# Scale to 2 instances
docker compose up -d --scale getdaytrends=2

# Wait for new instance to be healthy
sleep 30

# Scale back to 1 (removes old instance)
docker compose up -d --scale getdaytrends=1
```

---

## Next Steps

- ✅ Docker configuration complete
- ✅ docker-compose.yml updated
- ✅ .dockerignore created
- ⏭️ Test with dry-run
- ⏭️ Deploy to production

---

**Status**: ✅ Ready for Docker Deployment
**Last Updated**: 2026-03-23
