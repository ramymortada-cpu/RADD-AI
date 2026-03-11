# Skill: Deploy to Production Server

## When to Use
When deploying a new version to the production server for the first time or as an update.

## Prerequisites Checklist
- [ ] Server: Ubuntu 22.04, min 4 vCPU / 8 GB RAM
- [ ] Docker installed on server
- [ ] Domain name pointing to server IP
- [ ] SSL certificates ready
- [ ] All `.env` production values filled

---

## First-Time Deployment

### Step 1: Server preparation
```bash
# On your LOCAL machine — SSH to server
ssh ubuntu@YOUR_SERVER_IP

# On SERVER:
# Install Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker ubuntu
newgrp docker

# Clone the repo
git clone https://github.com/ramymortada-cpu/RADD-AI.git /opt/radd
cd /opt/radd
```

### Step 2: Configure production environment
```bash
# On SERVER:
cp .env.example .env
nano .env

# Fill in production values:
# APP_ENV=production
# DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/radd?sslmode=require
# REDIS_URL=rediss://default:token@global-xxx.upstash.io:6380
# OPENAI_API_KEY=sk-...
# SECRET_KEY=$(openssl rand -hex 32)
# JWT_SECRET_KEY=$(openssl rand -hex 32)
# META_APP_SECRET=...
# META_VERIFY_TOKEN=...
# WA_PHONE_NUMBER_ID=...
# WA_API_TOKEN=...
```

### Step 3: SSL certificates
```bash
# Install Certbot
sudo apt install certbot -y
sudo certbot certonly --standalone -d yourdomain.com

# Copy certs
mkdir -p /opt/radd/infrastructure/nginx/certs
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/radd/infrastructure/nginx/certs/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/radd/infrastructure/nginx/certs/
sudo chown ubuntu:ubuntu /opt/radd/infrastructure/nginx/certs/*
```

### Step 4: Update nginx config
```bash
sed -i 's/yourdomain.com/YOUR_ACTUAL_DOMAIN/g' /opt/radd/infrastructure/nginx/nginx.conf
```

### Step 5: Generate lockfiles (run LOCALLY first)
```bash
# On your LOCAL machine:
cd apps/api && uv lock
cd apps/web && pnpm install   # generates pnpm-lock.yaml
git add apps/api/uv.lock apps/web/pnpm-lock.yaml
git commit -m "chore: add lockfiles for Docker builds"
git push
```

### Step 6: Pull and deploy
```bash
# On SERVER:
cd /opt/radd
git pull origin main

# Build and start
docker compose -f infrastructure/docker-compose.prod.yml build
docker compose -f infrastructure/docker-compose.prod.yml up -d

# Run migrations
docker compose -f infrastructure/docker-compose.prod.yml exec api alembic upgrade head

# Seed initial data
docker compose -f infrastructure/docker-compose.prod.yml exec api python scripts/seed.py
```

### Step 7: Configure WhatsApp webhook
In Meta Developer Console:
- Webhook URL: `https://yourdomain.com/api/v1/webhooks/whatsapp`
- Verify Token: value of `META_VERIFY_TOKEN` in your `.env`
- Subscribe to: `messages`

---

## Update Deployment (Subsequent Updates)

```bash
# On SERVER:
cd /opt/radd
git pull origin main

# Pull new images (if using pre-built)
docker compose -f infrastructure/docker-compose.prod.yml pull

# Rolling restart (API first for health check)
docker compose -f infrastructure/docker-compose.prod.yml up -d --no-deps api
sleep 15

# Restart workers
docker compose -f infrastructure/docker-compose.prod.yml up -d --no-deps worker kb_indexer

# Restart frontend
docker compose -f infrastructure/docker-compose.prod.yml up -d --no-deps web

# Run any new migrations
docker compose -f infrastructure/docker-compose.prod.yml exec api alembic upgrade head

# Cleanup old images
docker image prune -f --filter "until=24h"
```

---

## Health Checks After Deployment

```bash
# Check all containers running
docker compose -f infrastructure/docker-compose.prod.yml ps

# Check API health
curl https://yourdomain.com/health
curl https://yourdomain.com/ready

# Check logs for errors
docker compose -f infrastructure/docker-compose.prod.yml logs api --tail=50
docker compose -f infrastructure/docker-compose.prod.yml logs worker --tail=50
```

---

## SSL Certificate Renewal (Cron)

```bash
# Add to crontab on server
crontab -e

# Add this line:
0 0 1 * * certbot renew --quiet && \
  cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/radd/infrastructure/nginx/certs/ && \
  cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/radd/infrastructure/nginx/certs/ && \
  docker compose -f /opt/radd/infrastructure/docker-compose.prod.yml restart nginx
```

---

## Rollback

```bash
# Find previous image tag
docker images | grep radd-api

# Rollback to previous version
docker tag radd-api:previous radd-api:latest
docker compose -f infrastructure/docker-compose.prod.yml up -d --no-deps api

# OR rollback via git
git log --oneline -5
git revert HEAD
git push
# Then re-deploy
```
