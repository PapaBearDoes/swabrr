# Swabbarr Project Instructions

**Version**: v1.0
**Last Modified**: 2026-04-01
**Repository**: https://github.com/PapaBearDoes/swabbarr

---

## What Is Swabbarr?

Swabbarr is a media library pruning engine. It connects to your existing *arr stack
(Radarr, Sonarr, Seerr) and Plex ecosystem (via Tautulli) to score every movie and
TV series in your library based on watch activity, request history, rarity, cultural
value, and storage footprint — then surfaces the best removal candidates through a
web dashboard so you can make informed decisions about what to keep and what to toss.

**The name:** "Swabbing the deck" — cleaning up what's cluttering the ship. Follows
the *arr ecosystem naming convention (Radarr, Sonarr, Swabbarr).

**The rule:** Swabbarr recommends. A human decides. No auto-deletion. Ever.

---

## Standards Documents

Always read the relevant standards documents before proposing architecture or writing code.
They are the authoritative source of truth for this project.

| Document | Location | Purpose |
|----------|----------|---------|
| Charter | `docs/standards/charter.md` | Immutable architecture rules (14 rules) |
| Project Instructions | `docs/standards/project_instructions.md` | Infrastructure, conventions, tools (this file) |

**Workflow:** Read standards → check current phase status → then write code.

---

## Infrastructure

### Servers

| Server | Role | OS | CPU | RAM | GPU | Notes |
|--------|------|----|-----|-----|-----|-------|
| **Lofn** | Primary homelab host, NAS, K8s cluster | Debian Bookworm | Ryzen 7 5800x | 64 GB | RTX 3060 - 12Gb VRAM | Hosts *arr stack, Seerr, Tautulli, Swabbarr |
| **Bacchus** | AI rig, Plex server | Windows 11 | Ryzen 7 7700x | 64 GB | RTX 5060 - 8Gb VRAM | Runs Plex |

### Network

- LAN: `10.20.30.0/24`
- NAS media path: `Y:\media\...` (Samba share from Lofn)
- K8s manifests: `Y:\k8s\...`

### Key Services (all on Lofn K8s)

| Service | Purpose | API Used By Swabbarr |
|---------|---------|---------------------|
| **Tautulli** | Plex usage tracking | Watch history, play counts, last watched |
| **Seerr** | Media request management | Request history, requestor identity |
| **Radarr** | Movie management | Movie metadata, file size, quality, TMDB ID |
| **Sonarr** | TV series management | Series metadata, episode counts, file size |
| **Sonarr-Anime** | Anime series management | Same as Sonarr, separate instance |
| **Plex** | Media consumption (on Bacchus) | Consumed via Tautulli, not directly |

### Plex Users

- **11 active users**: 7 remote, 4 local (household)
- All users are weighted equally for scoring purposes

### NAS Capacity

- **Total**: 32 TB
- **Available**: 12.5 TB
- **Target available**: 20 TB
- **Space to reclaim**: ~7.5 TB

---

## Repository Layout

```
swabbarr/
├── api/                          ← swabbarr-api (FastAPI + scoring engine)
│   ├── src/
│   │   ├── main.py               ← Application entry, scheduler setup
│   │   ├── managers/
│   │   │   ├── db_manager.py     ← PostgreSQL connection pool
│   │   │   ├── config_manager.py  ← Scoring weights, app settings
│   │   │   └── logging_config_manager.py
│   │   ├── clients/
│   │   │   ├── tautulli_client.py
│   │   │   ├── seerr_client.py
│   │   │   ├── radarr_client.py
│   │   │   ├── sonarr_client.py
│   │   │   └── tmdb_client.py
│   │   ├── scoring/
│   │   │   ├── engine.py         ← Core scoring logic
│   │   │   ├── signals.py        ← Signal category calculators
│   │   │   └── models.py         ← Score data models
│   │   └── routers/
│   │       ├── scores.py         ← Score results, removal candidates
│   │       ├── config.py         ← Weight configuration
│   │       ├── media.py          ← Media details, protected titles
│   │       └── actions.py        ← Trigger scoring run, approve removals
│   ├── docker-entrypoint.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── secrets/
│       └── README.md
├── web/                          ← swabbarr-web (frontend — TBD)
│   ├── src/
│   └── Dockerfile
├── db/
│   ├── schema.sql                ← Full PostgreSQL schema
│   └── migrations/               ← Versioned SQL migrations
├── docs/
│   ├── standards/
│   │   ├── charter.md            ← 14 architecture rules
│   │   └── project_instructions.md  ← This file
│   └── dev/
│       └── planning.md           ← Phase status, deliverables
├── docker-compose.yml
├── .env.template
├── .gitignore
└── README.md
```

---

## Docker Stack

Three containers (plus database), all orchestrated by `docker-compose.yml` at the repo root.

| Container | Image | Role |
|-----------|-------|------|
| `swabbarr-api` | Built from `api/` | FastAPI backend — scoring engine, external API clients, REST endpoints |
| `swabbarr-web` | TBD | Dashboard frontend |
| `swabbarr-db` | `postgres:17-alpine` | PostgreSQL — scores, config, audit history |

**Rules:**
- All solutions must be Docker-based
- Sensitive values (API keys, passwords) use Docker Secrets — never `.env` or compose files
- Non-sensitive config uses `.env` (with `.env.template` committed as reference)
- Secret files live in `api/secrets/` (gitignored)
- Secret naming convention: `swabbarr_{purpose}` (e.g. `swabbarr_tautulli_api_key`)

---

## Architecture: Scoring Model

### How Scoring Works

Every title (movie or TV series) in the library receives a **keep score** from 0–100.
Lower scores are stronger removal candidates. The score is a weighted sum of five
signal categories, with user-configurable weights stored in PostgreSQL.

### Signal Categories

| Category | Default Weight | Source | What It Measures |
|----------|---------------|--------|------------------|
| Watch Activity | 40% | Tautulli | Play count, unique viewers, recency decay, completion % |
| Rarity & Replaceability | 20% | TMDB | Streaming availability, acquisition difficulty |
| Request Accountability | 15% | Seerr | Was it requested? Did the requestor watch it? |
| Size Efficiency | 15% | Radarr/Sonarr | Value-per-GB — low-score + large file = strong candidate |
| Cultural Value | 10% | TMDB | Rating, awards, "classic" designation |

### Data Flow

```
Tautulli API ──┐
Seerr API ─────┤
Radarr API ────┼──→ Scoring Engine ──→ PostgreSQL ──→ Dashboard
Sonarr API ────┤
TMDB API ──────┘
```

### Key Design Decisions

- **TMDB ID as primary key.** All media tracked by TMDB ID across all data sources. Sonarr's TVDB IDs are resolved to TMDB IDs during ingestion.
- **APScheduler, not system cron.** Scoring runs are scheduled inside the FastAPI process. Dashboard shows next run time and last run status. Manual trigger via API endpoint.
- **Next.js for the web frontend.** Consistent with our other projects, robust build pipeline with GitHub Actions, strong UI/UX capabilities.
- **No auto-deletion.** Swabbarr surfaces candidates. A human deletes by hand in Radarr/Sonarr, then marks the item complete in the dashboard.
- **TV shows weighted heavier** for removal priority due to storage footprint.
- **Partial data is acceptable.** If TMDB is unreachable, score without streaming data.
- **Scores are historical.** Each run is timestamped and preserved for trend analysis.
- **Score breakdowns are stored.** The dashboard shows exactly which category dragged a title down.

---

## Current Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Standards documents, repo scaffold | ✅ Complete |
| 1 | Docker Compose skeleton, DB schema, secrets pattern | ✅ Complete |
| 2 | External API clients (Tautulli, Seerr, Radarr, Sonarr) | ✅ Complete |
| 3 | Scoring engine — formula, signal calculators, persistence | ✅ Complete |
| 4 | FastAPI endpoints — scores, config, media, actions | ✅ Complete |
| 5 | Dashboard MVP — score table, filters, removal workflow | ✅ Complete |
| 6 | Scheduled runs, notifications, trend tracking | 🔄 Backend Complete |
| 7 | TMDB integration — streaming availability, cultural value | ✅ Complete |
| 8 | Removal tracking — mark removed, history, reclaim reporting | ⬜ Planned |

See `docs/dev/planning.md` for full deliverable lists and notes per phase.

---

## Development Conventions

- **Language:** Python 3.13 — always `python:3.13-slim` base image, `/opt/venv` virtual env
- **No bash scripts** — Python for all scripting needs
- **Factory functions mandatory** — `create_[manager_name]()` for every manager; never call constructors directly
- **Dependency injection** — managers receive dependencies as constructor parameters; `log` always last
- **File version headers** — every file needs `FILE VERSION`, `LAST MODIFIED`, `COMPONENT` fields
- **`COMPONENT` field** values: `swabbarr-api` | `swabbarr-web` | `swabbarr-db`
- **Chunked file writes** — 25–30 lines per write operation (Desktop Commander standard)
- **httpx for all HTTP** — never `requests` or `urllib`; use `httpx.AsyncClient`
- **No hardcoded values** — API keys, URLs, and weights always come from config or secrets

### File System Tools

| Path pattern | Tool to use |
|---|---|
| `Y:\...` | `Desktop Commander:*` |
| `Y:\git\swabbarr\...` | `Desktop Commander:*` |
| `\\10.20.30.*\...` | `Desktop Commander:*` |
| `/home/claude/...` | `str_replace`, `view`, `bash_tool` |
| `/mnt/user-data/...` | `str_replace`, `view`, `bash_tool` |

---

## User Preferences

- Works on Windows with **Zed** editor and **GitHub Desktop**
- Git repository on NAS share at `Y:\git\swabbarr\` (Samba — `\\10.20.30.253\nas\git\swabbarr`)
- All Git operations should be committable from GitHub Desktop on Windows
- Collaborative language — "we", "our" rather than "you" / "your code"
- No bash scripting — Python preferred for any automation
- Docker-based solutions are the default

---

*This document is the starting point for every new conversation about the Swabbarr project.
Read it first, then read the charter before writing any code.*
