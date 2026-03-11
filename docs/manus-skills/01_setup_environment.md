# Skill: Setup Development Environment

## When to Use
Run this skill when setting up the project for the first time on any machine.

## Steps

### 1. Install uv (Python package manager)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv --version  # should print uv 0.5.x
```

### 2. Install pnpm (Node package manager)
```bash
npm install -g pnpm
pnpm --version  # should print 9.x
```

### 3. Install Python dependencies
```bash
cd apps/api
uv sync
```

### 4. Install Node dependencies
```bash
cd apps/web
pnpm install
```

### 5. Configure environment
```bash
cp .env.example .env
```
Open `.env` and fill in minimum required fields:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string  
- `OPENAI_API_KEY` — starts with `sk-`
- `SECRET_KEY` — run `openssl rand -hex 32`
- `JWT_SECRET_KEY` — run `openssl rand -hex 32` (different value)

### 6. Start local Docker services
```bash
docker compose -f infrastructure/docker-compose.yml up -d
# Wait 10 seconds for services to initialize
docker compose -f infrastructure/docker-compose.yml ps
```
Expected: postgres, redis, qdrant, minio all showing "running"

### 7. Run database migrations
```bash
cd apps/api
uv run alembic upgrade head
```
Expected output: `Running upgrade  -> 0001_initial_schema, ...`

### 8. Seed test data
```bash
cd apps/api
uv run python scripts/seed.py
```
Expected: creates workspace `demo`, user `owner@demo.com` / `Demo1234!`

### 9. Verify everything works
```bash
# Start API
cd apps/api && uv run uvicorn radd.main:app --reload --port 8000 &
sleep 3
curl http://localhost:8000/health
# Expected: {"status": "ok", ...}
```

## Success Criteria
- `curl http://localhost:8000/health` returns 200
- `curl http://localhost:8000/ready` returns 200
- Dashboard loads at http://localhost:3000 after `pnpm dev`
