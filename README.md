# Swabrr

**Media Library Pruning Engine**

Swabrr connects to your existing *arr stack (Radarr, Sonarr, Seerr) and Plex ecosystem (via Tautulli) to score every movie and TV series in your library based on watch activity, request history, rarity, cultural value, and storage footprint — then surfaces the best removal candidates through a web dashboard so you can make informed decisions about what to keep and what to toss.

**The name:** "Swabbing the deck" — cleaning up what's cluttering the ship.

**The rule:** Swabrr recommends. A human decides. No auto-deletion. Ever.

---

## How It Works

Every title in your library receives a **keep score** from 0–100. Lower scores are stronger removal candidates. The score is a weighted sum of five signals:

| Signal | Default Weight | Source |
|--------|---------------|--------|
| Watch Activity | 40% | Tautulli |
| Rarity & Replaceability | 20% | TMDB |
| Request Accountability | 15% | Seerr |
| Size Efficiency | 15% | Radarr / Sonarr |
| Cultural Value | 10% | TMDB |

Weights are fully configurable through the web dashboard. Scoring runs happen on a schedule (weekly by default) or on-demand via the dashboard.

### Data Flow

```
Tautulli API ──┐
Seerr API ─────┤
Radarr API ────┼──→ Scoring Engine ──→ PostgreSQL ──→ Dashboard
Sonarr API ────┤
TMDB API ──────┘
```

---

## Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| `swabrr-api` | Python 3.13 / FastAPI | Scoring engine, API clients, REST endpoints |
| `swabrr-web` | Next.js | Dashboard frontend |
| `swabrr-db` | PostgreSQL 17 | Scores, configuration, audit history |

All components run as Docker containers, orchestrated by `docker-compose.yml`.

---

## Requirements

### External Services (read-only API access)
- [Tautulli](https://tautulli.com/) — Plex usage tracking
- [Seerr](https://seerr.dev/) — Media request management
- [Radarr](https://radarr.video/) — Movie management
- [Sonarr](https://sonarr.tv/) — TV series management
- [TMDB API key](https://www.themoviedb.org/documentation/api) — Streaming availability, ratings (optional)

### Infrastructure
- Docker & Docker Compose
- Network access to your *arr services and Tautulli

---

## Quick Start

> **Coming soon** — Swabrr is in active development.

```bash
# Clone the repo
git clone https://github.com/PapaBearDoes/swabrr.git
cd swabrr

# Copy environment template and configure
cp ./.env.template ./.env
# Edit .env with your service URLs

# Add keys as Docker Secrets
openssl rand -base64 24 | tr -d '\n' > api/secrets/swabrr_db_password
openssl rand -base64 36 | tr -d '\n' > api/secrets/swabrr_encryption_key

# Change permissions
chmod 600 swabrr_db_password swabrr_encryption_key

# Start the stack
docker compose up -d
```

---

## Project Structure

```
swabrr/
├── api/                    ← swabrr-api (FastAPI + scoring engine)
│   ├── src/
│   │   ├── main.py
│   │   ├── managers/       ← DB, config, logging managers
│   │   ├── clients/        ← Tautulli, Seerr, Radarr, Sonarr, TMDB
│   │   ├── scoring/        ← Engine, signal calculators, models
│   │   └── routers/        ← REST API endpoints
│   ├── Dockerfile
│   └── secrets/
├── web/                    ← swabrr-web (Next.js dashboard)
├── db/                     ← PostgreSQL schema and migrations
├── docs/
│   ├── standards/          ← Charter, project instructions
│   └── dev/                ← Planning, phase status
├── docker-compose.yml
└── .env.template
```

---

*Built to keep the deck clean* 🏴‍☠️
