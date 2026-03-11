# رَدّ (Radd) — AI Customer Service for Arabic E-commerce

> WhatsApp-native, Arabic-first AI support platform for Saudi e-commerce merchants.  
> Powered by RAG, hybrid retrieval, and dialect-aware NLP.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  WhatsApp Customer                                          │
│       ↓                                                     │
│  Meta Webhook  →  FastAPI (radd/webhooks)                   │
│                       ↓                                     │
│               Redis Streams (queue)                         │
│                       ↓                                     │
│           Message Worker (workers/)                         │
│                       ↓                                     │
│    ┌──────────── NLP Pipeline ─────────────────┐            │
│    │ normalize → detect_dialect → classify_intent │         │
│    │      ↓                                   │            │
│    │ [order_status] → Salla API               │            │
│    │      ↓                                   │            │
│    │ RAG: Qdrant + PG BM25 + RRF              │            │
│    │      ↓                                   │            │
│    │ GPT-4.1-mini (Arabic, dialect-aware)      │            │
│    │      ↓                                   │            │
│    │ NLI verify (xlm-roberta-large-xnli)      │            │
│    │      ↓                                   │            │
│    │ Guardrails (PII redaction + injection)   │            │
│    │      ↓                                   │            │
│    │ Confidence routing → reply/escalate      │            │
│    └───────────────────────────────────────────┘            │
│                       ↓                                     │
│           WhatsApp reply / Agent escalation                 │
│                       ↓                                     │
│    Next.js Dashboard (RTL Arabic, real-time WebSocket)      │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start (Local Development)

### Prerequisites
- Docker + Docker Compose
- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node 22 + pnpm

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — fill in OpenAI API key at minimum

# 2. Install all dependencies
make install

# 3. Start local services (PostgreSQL, Redis, Qdrant, MinIO)
make up

# 4. Run database migrations
make migrate

# 5. Seed development data (workspace + users + channel)
make seed

# 6. Start the API (terminal 1)
make api        # → http://localhost:8000
                # → http://localhost:8000/docs  (Swagger UI)

# 7. Start the message worker (terminal 2)
make worker

# 8. Start the frontend (terminal 3)
make web        # → http://localhost:3000
```

**Default login credentials (after seed):**
- Workspace slug: `demo`
- Email: `owner@demo.com`
- Password: `Demo1234!`

---

## Project Structure

```
radd/
├── apps/
│   ├── api/                    # FastAPI backend (Python 3.12)
│   │   ├── radd/
│   │   │   ├── admin/          # KPI analytics, settings, user management
│   │   │   ├── auth/           # JWT + RBAC middleware
│   │   │   ├── actions/        # External actions (Salla API)
│   │   │   ├── conversations/  # Agent conversation management
│   │   │   ├── db/             # SQLAlchemy models + sessions
│   │   │   ├── escalation/     # Escalation queue + agent workflow
│   │   │   ├── knowledge/      # KB CRUD + embedding pipeline
│   │   │   ├── pipeline/       # NLP: normalize→intent→RAG→verify→guardrails
│   │   │   ├── webhooks/       # WhatsApp Meta webhook handler
│   │   │   ├── websocket/      # Real-time agent notifications
│   │   │   └── whatsapp/       # WhatsApp Cloud API client
│   │   ├── workers/
│   │   │   ├── message_worker.py   # Redis Streams consumer
│   │   │   └── kb_indexer.py       # Document chunking + embedding worker
│   │   ├── alembic/            # Database migrations
│   │   ├── scripts/            # seed.py, benchmark.py
│   │   └── tests/
│   └── web/                    # Next.js 15 frontend (RTL Arabic)
│       ├── app/
│       │   ├── (auth)/login/
│       │   └── (dashboard)/
│       │       ├── dashboard/      # 8 KPI cards + live feed
│       │       ├── conversations/  # Chat view + agent reply
│       │       ├── knowledge/      # Document management
│       │       ├── escalations/    # Agent queue
│       │       └── settings/       # Workspace + user management
│       ├── components/
│       └── lib/                # API client + auth + utils
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.web
│   ├── nginx/
│   │   └── nginx.conf
│   ├── docker-compose.yml          # Local dev services
│   └── docker-compose.prod.yml     # Production stack
├── .github/workflows/ci.yml    # CI/CD pipeline
├── Makefile
└── .env.example
```

---

## NLP Pipeline — Confidence Routing

```
C_min = min(C_intent, C_retrieval, C_verify)

C_min ≥ 0.85  →  auto_rag      (send AI response directly)
C_min ≥ 0.60  →  escalated_soft  (send + flag for review)
C_min < 0.60  →  escalated_hard  (hold + alert agent)
```

**Gate G1 (NLP benchmark):** 95% accuracy on 100-query Arabic test set.  
Run with: `make benchmark`

---

## Production Deployment

### Option A — Docker Compose on a VPS (simplest)

**1. Provision a server** (Ubuntu 22.04, 4 vCPU, 8 GB RAM minimum)

**2. Install Docker**
```bash
curl -fsSL https://get.docker.com | bash
```

**3. Clone the repo**
```bash
git clone https://github.com/YOUR_ORG/radd.git /opt/radd
cd /opt/radd
cp .env.example .env
# Fill in production values (Neon DB, Upstash Redis, OpenAI, WhatsApp, Salla)
nano .env
```

**4. Add SSL certificates**
```bash
# Using Certbot
apt install certbot
certbot certonly --standalone -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem infrastructure/nginx/certs/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem   infrastructure/nginx/certs/
```

**5. Update nginx.conf** — replace `yourdomain.com` with your actual domain

**6. Deploy**
```bash
docker compose -f infrastructure/docker-compose.prod.yml up -d
docker compose -f infrastructure/docker-compose.prod.yml exec api alembic upgrade head
```

**7. Configure WhatsApp webhook**  
In Meta Developer Console → your App → WhatsApp → Webhook:
- URL: `https://yourdomain.com/api/v1/webhooks/whatsapp`
- Verify Token: value of `META_VERIFY_TOKEN` in your `.env`

---

### Option B — GitHub Actions + Auto-deploy (recommended)

1. Push the repo to GitHub
2. Add these secrets in **Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `GHCR_TOKEN` | GitHub PAT with `packages:write` |
| `SSH_DEPLOY_KEY` | Private SSH key for your server |
| `DEPLOY_HOST` | Your server's IP |
| `DEPLOY_USER` | SSH user (e.g. `ubuntu`) |
| `SLACK_WEBHOOK_URL` | (optional) for deploy notifications |

3. Push to `main` → CI runs tests → builds images → deploys automatically.

---

## External Services Required

| Service | Purpose | Cost |
|---------|---------|------|
| [Neon](https://neon.tech) | PostgreSQL (serverless) | Free tier available |
| [Upstash](https://upstash.com) | Redis (serverless) | Free tier available |
| [OpenAI](https://platform.openai.com) | Embeddings + GPT-4.1-mini | ~$0.002/1k msgs |
| [Meta WhatsApp](https://business.facebook.com) | WhatsApp Cloud API | 1000 free msgs/mo |
| [Salla](https://salla.dev) | Order status integration | Free (partner API) |
| Qdrant | Vector search (self-hosted) | Included in compose |

---

## Available Make Commands

```
make help        — Show all commands
make up          — Start local Docker services
make down        — Stop Docker services
make migrate     — Run DB migrations
make seed        — Seed dev data
make api         — Start FastAPI on :8000
make worker      — Start message worker
make web         — Start Next.js on :3000
make test        — Run all tests (pytest + vitest)
make benchmark   — Run Arabic NLP benchmark (target ≥ 80%)
make lint        — Lint backend + frontend
make typecheck   — Type-check backend + frontend
make install     — Install all dependencies (uv + pnpm)
make build       — Build production Docker images
```

---

## Environment Variables

See [`.env.example`](.env.example) for the full list with descriptions.

---

*Built with FastAPI · Next.js 15 · PostgreSQL 16 · Qdrant 1.12 · Redis 7 · OpenAI*
