# Swabbarr

**Media Library Pruning Engine**

Swabbarr connects to your existing *arr stack (Radarr, Sonarr, Seerr) and Plex
ecosystem (via Tautulli) to score every movie and TV series in your library based
on watch activity, request history, rarity, cultural value, and storage footprint —
then surfaces the best removal candidates through a web dashboard so you can make
informed decisions about what to keep and what to toss.

**The name:** "Swabbing the deck" — cleaning up what's cluttering the ship. Follows
the *arr ecosystem naming convention (Radarr, Sonarr, Swabbarr).

**The rule:** Swabbarr recommends. A human decides. No auto-deletion. Ever.

---

## How It Works

Every title in your library receives a **keep score** from 0–100. Lower scores are
stronger removal candidates. The score is a weighted sum of five signals:

| Signal | Default Weight | Source |
|--------|---------------|--------|
| Watch Activity | 40% | Tautulli |
| Rarity & Replaceability | 20% | TMDB |
| Request Accountability | 15% | Seerr |
| Size Efficiency | 15% | Radarr / Sonarr |
| Cultural Value | 10% | TMDB |

Weights are fully configurable through the web dashboard. Scoring runs happen on a
schedule (weekly by default) or on-demand via the dashboard.

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
| `swabbarr-api` | Python 3.13 / FastAPI | Scoring engine, API clients, REST endpoints |
| `swabbarr-web` | Next.js | Dashboard frontend |
| `swabbarr-db` | PostgreSQL 17 | Scores, configuration, audit history |

All components run as Docker containers, orchestrated by `docker-compose.yml`.

---

## Requirements

### External Services (read-only API access)
- [Tautulli](https://tautulli.com/) — Plex usage tracking
- [Overseerr / Jellyseerr](https://overseerr.dev/) — Media request management
- [Radarr](https://radarr.video/) — Movie management
- [Sonarr](https://sonarr.tv/) — TV series management
- [TMDB API key](https://www.themoviedb.org/documentation/api) — Streaming availability, ratings (optional)

### Infrastructure
- Docker & Docker Compose
- Network access to your *arr services and Tautulli

---

## Quick Start

> **Coming soon** — Swabbarr is in active development. See `docs/dev/planning.md`
> for current phase status.

```bash
# Clone the repo
git clone https://github.com/PapaBearDoes/swabbarr.git
cd swabbarr

# Copy environment template and configure
cp ./.env.template ./.env
# Edit .env with your service URLs

# Add API keys as Docker Secrets
printf "your-tautulli-key" > api/secrets/swabbarr_tautulli_api_key
printf "your-radarr-key"   > api/secrets/swabbarr_radarr_api_key
printf "your-sonarr-key"   > api/secrets/swabbarr_sonarr_api_key
printf "your-seerr-key"    > api/secrets/swabbarr_seerr_api_key
printf "your-db-password"  > api/secrets/swabbarr_db_password

# Start the stack
docker compose up -d
```

---

## Project Structure

```
swabbarr/
├── api/                    ← swabbarr-api (FastAPI + scoring engine)
│   ├── src/
│   │   ├── main.py
│   │   ├── managers/       ← DB, config, logging managers
│   │   ├── clients/        ← Tautulli, Seerr, Radarr, Sonarr, TMDB
│   │   ├── scoring/        ← Engine, signal calculators, models
│   │   └── routers/        ← REST API endpoints
│   ├── Dockerfile
│   └── secrets/
├── web/                    ← swabbarr-web (Next.js dashboard)
├── db/                     ← PostgreSQL schema and migrations
├── docs/
│   ├── standards/          ← Charter, project instructions
│   └── dev/                ← Planning, phase status
├── docker-compose.yml
└── .env.template
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [Charter](docs/standards/charter.md) | Architecture rules (14 rules) |
| [Project Instructions](docs/standards/project_instructions.md) | Infrastructure, conventions |
| [Planning](docs/dev/planning.md) | Phase status, deliverables, schema design |

---

*Built to keep the deck clean* 🏴‍☠️
