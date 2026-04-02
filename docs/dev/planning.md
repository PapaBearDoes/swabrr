# Swabbarr — Development Planning

**Version**: v1.0
**Last Modified**: 2026-04-01
**Repository**: https://github.com/PapaBearDoes/swabbarr

---

## Phase Overview

| Phase | Description | Status | Dependencies |
|-------|-------------|--------|-------------|
| 0 | Standards & Scaffold | ✅ Complete | None |
| 1 | Docker Compose, DB Schema, Secrets | ⬜ Planned | Phase 0 |
| 2 | External API Clients | ⬜ Planned | Phase 1 |
| 3 | Scoring Engine | ⬜ Planned | Phase 2 |
| 4 | FastAPI Endpoints | ⬜ Planned | Phase 3 |
| 5 | Dashboard MVP | ⬜ Planned | Phase 4 |
| 6 | Scheduling & Notifications | ⬜ Planned | Phase 4 |
| 7 | TMDB Integration (Rarity & Cultural) | ⬜ Planned | Phase 3 |
| 8 | Removal Tracking & Reporting | ⬜ Planned | Phase 5 |

**Note:** Phases 6, 7, and 8 can be worked in parallel once their dependencies are met.

---

## Phase 0 — Standards & Scaffold

**Goal:** Establish project standards, repo structure, and foundational files.

**Status:** ✅ Complete

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 0.1 | `docs/standards/charter.md` | ✅ Complete | 14 architecture rules |
| 0.2 | `docs/standards/project_instructions.md` | ✅ Complete | Infrastructure, conventions |
| 0.3 | `docs/dev/planning.md` | ✅ Complete | This document |
| 0.4 | `.gitignore` | ✅ Complete | Python, Node, secrets, IDE |
| 0.5 | `README.md` | ✅ Complete | Project overview, setup guide |
| 0.6 | `.env.template` | ✅ Complete | All env vars documented |
| 0.7 | Repo directory skeleton | ✅ Complete | `api/`, `web/`, `db/`, `docs/` structure |

### Exit Criteria
- All standards documents reviewed and committed
- Repo skeleton matches the layout in project_instructions.md
- `.env.template` documents every expected env var
- `.gitignore` covers Python, Node, secrets, IDE files

---

## Phase 1 — Docker Compose, DB Schema, Secrets

**Goal:** Containerized infrastructure with a working database and secrets pattern.

**Status:** ⬜ Planned

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 1.1 | `docker-compose.yml` | ⬜ | swabbarr-api, swabbarr-db, swabbarr-web (stub) |
| 1.2 | `api/Dockerfile` | ⬜ | Multi-stage, Python 3.13, tini, PUID/PGID |
| 1.3 | `api/docker-entrypoint.py` | ⬜ | Pure Python entrypoint per Rule #12 |
| 1.4 | `api/requirements.txt` | ⬜ | fastapi, uvicorn, httpx, asyncpg, apscheduler |
| 1.5 | `api/secrets/README.md` | ⬜ | Documents expected secrets |
| 1.6 | `db/schema.sql` | ⬜ | Full PostgreSQL schema (see below) |
| 1.7 | `api/src/managers/db_manager.py` | ⬜ | Connection pool, acquire() pattern |
| 1.8 | `api/src/managers/logging_config_manager.py` | ⬜ | Colorized logging per Rule #9 |
| 1.9 | `api/src/main.py` | ⬜ | FastAPI app skeleton, lifespan, DB init |

### Database Schema Design

The schema covers six concerns: media identity, scoring, configuration,
protection, removal tracking, and run history.

#### Table: `media_items`
The canonical record for every title in the library. Created during data
ingestion, updated on each scoring run.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | `SERIAL PRIMARY KEY` | Internal ID |
| `tmdb_id` | `INTEGER NOT NULL UNIQUE` | Primary tracking key (TMDB) |
| `media_type` | `VARCHAR(10) NOT NULL` | `movie` or `series` |
| `title` | `VARCHAR(500) NOT NULL` | Display title |
| `year` | `INTEGER` | Release year |
| `added_at` | `TIMESTAMPTZ` | When added to *arr library |
| `file_size_bytes` | `BIGINT` | Total size on disk |
| `quality_profile` | `VARCHAR(100)` | e.g. "Bluray-1080p", "WEBDL-720p" |
| `arr_id` | `INTEGER` | Radarr/Sonarr internal ID |
| `arr_source` | `VARCHAR(20)` | `radarr`, `sonarr`, `sonarr-anime` |
| `episode_count` | `INTEGER` | NULL for movies, total eps for series |
| `poster_url` | `VARCHAR(500)` | TMDB poster path for dashboard display |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | Record creation |
| `updated_at` | `TIMESTAMPTZ DEFAULT NOW()` | Last update |

#### Table: `scoring_runs`
One row per scoring execution. Tracks when runs happen and their outcomes.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | `SERIAL PRIMARY KEY` | Run ID |
| `started_at` | `TIMESTAMPTZ NOT NULL` | When run began |
| `completed_at` | `TIMESTAMPTZ` | When run finished (NULL if failed) |
| `trigger` | `VARCHAR(20) NOT NULL` | `scheduled` or `manual` |
| `titles_scored` | `INTEGER` | Total titles processed |
| `candidates_flagged` | `INTEGER` | Titles below threshold |
| `space_reclaimable_bytes` | `BIGINT` | Total size of candidates |
| `partial_data` | `BOOLEAN DEFAULT FALSE` | True if any API was unreachable |
| `notes` | `TEXT` | Any warnings (e.g. "TMDB unavailable") |

#### Table: `media_scores`
Per-title, per-run score results with full breakdown. This is the heart of
the audit trail — every score is explainable.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | `SERIAL PRIMARY KEY` | Internal ID |
| `media_item_id` | `INTEGER REFERENCES media_items(id)` | FK to media item |
| `scoring_run_id` | `INTEGER REFERENCES scoring_runs(id)` | FK to scoring run |
| `keep_score` | `NUMERIC(5,2) NOT NULL` | Final 0–100 score |
| `watch_activity_score` | `NUMERIC(5,2)` | Component score (0–100) |
| `rarity_score` | `NUMERIC(5,2)` | Component score (0–100) |
| `request_score` | `NUMERIC(5,2)` | Component score (0–100) |
| `size_efficiency_score` | `NUMERIC(5,2)` | Component score (0–100) |
| `cultural_value_score` | `NUMERIC(5,2)` | Component score (0–100) |
| `is_candidate` | `BOOLEAN DEFAULT FALSE` | Below threshold? |
| `scored_at` | `TIMESTAMPTZ DEFAULT NOW()` | Timestamp |

**Unique constraint:** `(media_item_id, scoring_run_id)` — one score per title per run.

**Trend query example:**
```sql
SELECT s.keep_score, r.started_at
FROM media_scores s
JOIN scoring_runs r ON s.scoring_run_id = r.id
WHERE s.media_item_id = $1
ORDER BY r.started_at DESC
LIMIT 10;
```

#### Table: `scoring_weights`
User-configurable weights. Single row, updated via dashboard.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | `SERIAL PRIMARY KEY` | Always 1 (single row) |
| `watch_activity` | `NUMERIC(5,2) DEFAULT 40.00` | Weight % |
| `rarity` | `NUMERIC(5,2) DEFAULT 20.00` | Weight % |
| `request_accountability` | `NUMERIC(5,2) DEFAULT 15.00` | Weight % |
| `size_efficiency` | `NUMERIC(5,2) DEFAULT 15.00` | Weight % |
| `cultural_value` | `NUMERIC(5,2) DEFAULT 10.00` | Weight % |
| `candidate_threshold` | `NUMERIC(5,2) DEFAULT 30.00` | Score below this = candidate |
| `updated_at` | `TIMESTAMPTZ DEFAULT NOW()` | Last change |

**Check constraint:** All five weights must sum to 100.

#### Table: `protected_titles`
Titles manually flagged as "never suggest for removal."

| Column | Type | Purpose |
|--------|------|---------|
| `id` | `SERIAL PRIMARY KEY` | Internal ID |
| `media_item_id` | `INTEGER REFERENCES media_items(id) UNIQUE` | FK |
| `reason` | `VARCHAR(500)` | Optional: why protected |
| `protected_at` | `TIMESTAMPTZ DEFAULT NOW()` | When flagged |

#### Table: `removal_history`
Tracks items the user has removed and marked complete in the dashboard.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | `SERIAL PRIMARY KEY` | Internal ID |
| `media_item_id` | `INTEGER REFERENCES media_items(id)` | FK |
| `tmdb_id` | `INTEGER NOT NULL` | Preserved for reference after item gone |
| `title` | `VARCHAR(500) NOT NULL` | Preserved title |
| `media_type` | `VARCHAR(10) NOT NULL` | `movie` or `series` |
| `file_size_bytes` | `BIGINT` | Size at time of removal |
| `final_keep_score` | `NUMERIC(5,2)` | Score when removed |
| `removed_at` | `TIMESTAMPTZ DEFAULT NOW()` | When marked removed |

#### Table: `watch_data_cache`
Raw watch data from Tautulli, cached per scoring run to avoid re-fetching
and to provide a data snapshot for auditability.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | `SERIAL PRIMARY KEY` | Internal ID |
| `media_item_id` | `INTEGER REFERENCES media_items(id)` | FK |
| `scoring_run_id` | `INTEGER REFERENCES scoring_runs(id)` | FK |
| `total_plays` | `INTEGER DEFAULT 0` | Total play count across all users |
| `unique_viewers` | `INTEGER DEFAULT 0` | Distinct users who watched |
| `last_watched_at` | `TIMESTAMPTZ` | Most recent play |
| `avg_completion_pct` | `NUMERIC(5,2)` | Average watch completion % |
| `requested_by` | `VARCHAR(100)` | Seerr requestor username (NULL if not requested) |
| `requestor_watched` | `BOOLEAN` | Did the requestor watch it? |
| `request_date` | `TIMESTAMPTZ` | When requested in Seerr |

#### Schema Notes

- **Indexes:** `media_items.tmdb_id`, `media_scores.media_item_id`,
  `media_scores.scoring_run_id`, `media_scores.keep_score`,
  `media_scores.is_candidate`
- **Cascade deletes:** If a `media_item` is removed from `media_items`,
  cascade to `media_scores`, `watch_data_cache`, `protected_titles`
- **The `removal_history` table intentionally preserves data** even after
  the media_item record is gone — it's the historical log of what was pruned.

### Exit Criteria
- `docker-compose up` brings up swabbarr-api and swabbarr-db
- Schema applied, tables created, seed data for scoring_weights inserted
- DB connection pool working with acquire() pattern
- Logging output matches Rule #9 colorization scheme
- Secrets pattern functional (API keys readable from Docker Secrets)
- Health check endpoint returns 200

---

## Phase 2 — External API Clients

**Goal:** Build async clients for every external service Swabbarr reads from.

**Status:** ⬜ Planned

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 2.1 | `api/src/clients/tautulli_client.py` | ⬜ | Watch history, play counts, completion % |
| 2.2 | `api/src/clients/seerr_client.py` | ⬜ | Request history, requestor identity |
| 2.3 | `api/src/clients/radarr_client.py` | ⬜ | Movie metadata, file size, TMDB ID |
| 2.4 | `api/src/clients/sonarr_client.py` | ⬜ | Series metadata, episode counts, file size |
| 2.5 | `api/src/clients/base_client.py` | ⬜ | Shared httpx logic, retry, timeout |

### Implementation Notes

#### Base Client Pattern
All clients inherit shared behavior from `BaseClient`:
- `httpx.AsyncClient` with configurable timeout (default 30s)
- Retry logic: 3 attempts with exponential backoff for 5xx and timeouts
- `health_check()` method called at startup
- Structured error logging (never crashes, logs and returns None/empty)

#### Tautulli Client
- **Endpoint:** `GET /api/v2?cmd=get_history` (paginated)
- **Key data:** `rating_key` (Plex ID), `play_count`, `last_played`,
  `watched_status`, `user`, `percent_complete`
- **Challenge:** Tautulli tracks by Plex `rating_key`, not TMDB ID.
  We need to cross-reference with Radarr/Sonarr metadata to map to TMDB IDs.
  Radarr and Sonarr both store the Plex `rating_key` or we can match by title+year.

#### Seerr Client
- **Endpoint:** `GET /api/v1/request` (paginated)
- **Key data:** `media.tmdbId`, `requestedBy.displayName`, `createdAt`, `status`
- **Maps directly to TMDB ID** — no cross-referencing needed

#### Radarr Client
- **Endpoint:** `GET /api/v3/movie`
- **Key data:** `tmdbId`, `title`, `year`, `sizeOnDisk`, `qualityProfileId`,
  `movieFile.quality`, `added`
- **Direct TMDB ID source** for all movies

#### Sonarr Client (used for both Sonarr and Sonarr-Anime)
- **Endpoint:** `GET /api/v3/series`
- **Key data:** `tvdbId`, `title`, `year`, `statistics.sizeOnDisk`,
  `statistics.episodeCount`, `qualityProfileId`, `added`
- **Challenge:** Sonarr uses TVDB IDs. We need to resolve to TMDB IDs.
  Options: (a) Sonarr v4 may include `tmdbId` in the API response,
  (b) Use TMDB API's `/find/{external_id}?external_source=tvdb_id` endpoint,
  (c) Sonarr stores TMDB ID in its metadata — check `GET /api/v3/series/{id}`
  for an `imdbId` or `tmdbId` field in the response.
- **Sonarr-Anime uses the same client class** with a different base URL and API key.

### TVDB → TMDB ID Resolution Strategy
This is a critical data pipeline concern. Preferred approach (in order):
1. Check if Sonarr's API response already includes `tmdbId` (Sonarr v4+)
2. If not, use TMDB's find-by-external-ID endpoint: `GET /find/{tvdb_id}?external_source=tvdb_id`
3. Cache resolved mappings in a `tvdb_tmdb_map` table to avoid repeated lookups

### Exit Criteria
- All clients instantiate via factory functions
- Health check passes against live Lofn services
- Each client can fetch a full library dump and return structured data
- Error handling tested: client returns gracefully when service is down
- TVDB → TMDB resolution working for series

---

## Phase 3 — Scoring Engine

**Goal:** Build the core scoring logic that takes raw data from all clients,
merges it into unified records, applies the weighted formula, and persists
results to PostgreSQL.

**Status:** ⬜ Planned

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 3.1 | `api/src/scoring/models.py` | ⬜ | Pydantic models for media records, scores |
| 3.2 | `api/src/scoring/signals.py` | ⬜ | Five signal calculators |
| 3.3 | `api/src/scoring/engine.py` | ⬜ | Orchestrator: fetch → merge → score → persist |
| 3.4 | `api/src/managers/config_manager.py` | ⬜ | Read scoring weights from DB |

### Signal Calculator Details

#### Watch Activity Signal (default 40%)
**Inputs:** play_count, unique_viewers, last_watched_at, avg_completion_pct
**Formula considerations:**
- `unique_viewers / total_users` ratio (out of 11 users)
- Recency decay: exponential decay from last_watched_at. A title watched
  yesterday scores near 100%; a title last watched 3 years ago decays heavily.
- Completion penalty: avg_completion < 50% suggests people started and bailed
- Play count has diminishing returns (10 plays is better than 1, but 50 is
  not 5x better than 10)
- Never-watched titles score 0 for this signal

#### Rarity & Replaceability Signal (default 20%)
**Inputs:** streaming_availability (from TMDB/JustWatch), file_quality
**Formula considerations:**
- Available on 3+ major streaming services → low rarity (easy to re-get)
- Available on 1 service → medium rarity
- Not on any streaming service → high rarity (strong keep signal)
- File quality matters: a rare encode is harder to replace than a common one
- **Phase 7 dependency:** Until TMDB integration is built, this signal
  defaults to a neutral 50/100 for all titles. Scoring still works, just
  without streaming data.

#### Request Accountability Signal (default 15%)
**Inputs:** was_requested, requestor_watched, request_age
**Formula considerations:**
- Not requested → neutral (50/100) — neither good nor bad
- Requested AND requestor watched → bonus (75/100)
- Requested AND requestor DID NOT watch → penalty (15/100)
- Request age amplifies the penalty: requested 2 years ago and still
  unwatched is worse than requested 2 weeks ago and unwatched

#### Size Efficiency Signal (default 15%)
**Inputs:** file_size_bytes, keep_score_without_size
**Formula considerations:**
- This is a meta-signal — it modifies impact based on other scores
- A 60GB title with a low keep score is a stronger removal candidate
  than a 2GB title with the same low keep score
- Normalize against library median file size
- TV series naturally have large footprints — the multiplier accounts for this

#### Cultural Value Signal (default 10%)
**Inputs:** tmdb_vote_average, tmdb_vote_count, awards (if available)
**Formula considerations:**
- TMDB rating 8.0+ → high cultural value
- TMDB rating 5.0–8.0 → moderate
- TMDB rating below 5.0 → low cultural value
- Vote count matters: 8.5 rating with 50,000 votes is more reliable than
  8.5 with 12 votes
- "Classic" threshold: released before 2000 with high rating → bonus
- **Phase 7 dependency:** Full TMDB data. Until then, use whatever rating
  data Radarr/Sonarr already store in their metadata.

### Data Merge Strategy
The scoring engine merges data from all clients into a single `MediaRecord`
per TMDB ID. The merge order:

```
1. Radarr/Sonarr → media identity (TMDB ID, title, year, file size, quality)
2. Tautulli → watch data (play count, viewers, recency, completion)
3. Seerr → request data (requestor, watched, request date)
4. TMDB → cultural/rarity data (rating, streaming availability)
```

If a title exists in Radarr/Sonarr but has no Tautulli history, it gets
zero for watch activity. If it has no Seerr request, it gets neutral for
request accountability. Missing data never crashes the merge — it just
produces a partial record with the available signals.

### Exit Criteria
- Scoring engine runs end-to-end: fetch → merge → score → persist
- All five signal calculators produce values in 0–100 range
- Weighted sum correctly applies user-configurable weights from DB
- Score breakdown stored per-title in `media_scores`
- Partial data (missing API) produces partial scores, not crashes
- Same inputs produce identical scores (determinism verified)
- Scoring run summary logged with colorized output

---

## Phase 4 — FastAPI Endpoints

**Goal:** REST API that the dashboard will consume. Exposes scores,
configuration, media details, and action triggers.

**Status:** ⬜ Planned

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 4.1 | `api/src/routers/scores.py` | ⬜ | Score listing, filtering, sorting |
| 4.2 | `api/src/routers/config.py` | ⬜ | Read/update scoring weights |
| 4.3 | `api/src/routers/media.py` | ⬜ | Media details, protect/unprotect |
| 4.4 | `api/src/routers/actions.py` | ⬜ | Trigger scoring run, mark removed |
| 4.5 | `api/src/routers/health.py` | ⬜ | Health check, service status |

### Endpoint Design

#### Scores Router (`/api/scores`)
```
GET  /api/scores                  → Paginated score list (latest run)
GET  /api/scores/candidates       → Only titles below threshold
GET  /api/scores/{tmdb_id}        → Single title's current score + breakdown
GET  /api/scores/{tmdb_id}/history → Score trend over past N runs
GET  /api/scores/summary          → Dashboard summary stats
```

**Query parameters for listing:**
- `media_type` — filter by `movie` or `series`
- `sort_by` — `keep_score`, `file_size`, `title`, `last_watched`
- `sort_order` — `asc` or `desc`
- `page`, `per_page` — pagination
- `min_score`, `max_score` — score range filter

#### Config Router (`/api/config`)
```
GET  /api/config/weights          → Current scoring weights
PUT  /api/config/weights          → Update weights (must sum to 100)
GET  /api/config/threshold        → Current candidate threshold
PUT  /api/config/threshold        → Update threshold
```

#### Media Router (`/api/media`)
```
GET  /api/media/{tmdb_id}         → Full media details + watch data
POST /api/media/{tmdb_id}/protect → Add to protected list
DELETE /api/media/{tmdb_id}/protect → Remove from protected list
GET  /api/media/protected         → List all protected titles
```

#### Actions Router (`/api/actions`)
```
POST /api/actions/score           → Trigger manual scoring run
GET  /api/actions/status          → Current run status (idle/running/%)
POST /api/actions/remove/{tmdb_id} → Mark title as removed
GET  /api/actions/removal-history → Removal history with space reclaimed
```

#### Health Router (`/api/health`)
```
GET  /api/health                  → Overall health
GET  /api/health/services         → Status of each external service
```

### Exit Criteria
- All endpoints return proper JSON responses
- Score listing supports filtering, sorting, and pagination
- Weight updates enforce sum-to-100 constraint
- Manual scoring trigger works and returns run status
- Mark-as-removed writes to removal_history
- Health endpoint checks DB + all external services
- Error responses use proper HTTP status codes, no stack traces

---

## Phase 5 — Dashboard MVP

**Goal:** A web dashboard that displays scores, lets the user review
candidates, adjust weights, protect titles, and mark removals.

**Status:** ⬜ Planned

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 5.1 | Next.js project scaffold | ⬜ | App Router, TypeScript, Tailwind |
| 5.2 | `web/Dockerfile` | ⬜ | Multi-stage Node build |
| 5.3 | Dashboard layout + navigation | ⬜ | Sidebar: Scores, Candidates, Config, History |
| 5.4 | Score table page | ⬜ | Sortable, filterable, paginated |
| 5.5 | Candidate review page | ⬜ | Below-threshold titles, "mark removed" action |
| 5.6 | Title detail modal/page | ⬜ | Score breakdown, watch history, trend chart |
| 5.7 | Configuration page | ⬜ | Weight sliders, threshold adjustment |
| 5.8 | Protected titles page | ⬜ | List + add/remove protection |
| 5.9 | Removal history page | ⬜ | Historical removals, total space reclaimed |
| 5.10 | Dashboard summary | ⬜ | Library size, space used, candidates count, next run |

### Dashboard Pages

#### Score Table (main view)
- Columns: Poster, Title, Year, Type, Keep Score, File Size, Last Watched, Status
- Color-coded scores: green (70+), yellow (30–70), red (below 30)
- Click row → detail view
- Filter by type (movie/series), score range
- Sort by any column
- "Candidates only" toggle

#### Candidate Review
- Filtered view of titles below threshold
- Running total of "space reclaimable if all removed"
- "Mark as removed" button per title
- Batch selection for marking multiple
- Shows which signal category is dragging each title down

#### Title Detail
- Poster image, title, year, quality, file size
- Score breakdown: bar chart or radar chart of five signals
- Score trend: line chart over past N runs
- Watch history: who watched, when, completion %
- Seerr request info: who requested, when, did they watch
- Protect / unprotect toggle

#### Configuration
- Five weight sliders that must sum to 100%
- Visual feedback showing weight distribution
- Candidate threshold slider
- "Run scoring now" button with progress indicator
- Last run summary: when, how many scored, candidates flagged

#### Removal History
- Table of all marked-removed titles
- Cumulative space reclaimed chart
- Filterable by date range and media type

### Exit Criteria
- All pages render with live data from the API
- Score table supports sort/filter/pagination
- Weight sliders enforce sum-to-100 constraint
- "Mark as removed" workflow functional end-to-end
- Protection toggle works from detail view
- Manual scoring trigger shows progress
- Responsive layout works on desktop and tablet

---

## Phase 6 — Scheduling & Notifications

**Goal:** Automated scoring runs via APScheduler with optional notifications
when new candidates are flagged.

**Status:** ⬜ Planned

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 6.1 | APScheduler integration in `main.py` | ⬜ | Cron-based trigger inside FastAPI lifespan |
| 6.2 | Schedule configuration endpoint | ⬜ | Read/update cron expression via API |
| 6.3 | Run history page (dashboard) | ⬜ | Past runs with stats, partial data warnings |
| 6.4 | Dashboard schedule display | ⬜ | Next run time, last run summary |
| 6.5 | Notification system (optional) | ⬜ | Webhook/email when new candidates appear |

### Implementation Notes

#### APScheduler Setup
- Use `APScheduler` with `AsyncIOScheduler` inside FastAPI's lifespan
- Default schedule: weekly, Sunday at 3am (`SWABBARR_SCORE_CRON`)
- The scheduler calls the same scoring function as the manual trigger
- Scheduler state visible via `/api/actions/status`

#### Run History
Each scoring run is already persisted in `scoring_runs`. This phase adds:
- Dashboard page showing past runs in a table
- Per-run detail: how many titles scored, candidates flagged, which APIs
  were unreachable, total reclaimable space
- Ability to compare two runs side-by-side (which titles changed score)

#### Notifications (Stretch Goal)
Optional webhook integration to notify when a scoring run completes and
new candidates are found. Options:
- Discord webhook (post to a channel in your server)
- Generic webhook URL (for Ntfy, Gotify, Pushover, etc.)
- Configurable via dashboard: enable/disable, webhook URL, minimum
  candidate count to trigger notification

### Exit Criteria
- Scheduled scoring runs fire on cron schedule
- Schedule is configurable via API and dashboard
- Run history page shows past runs with stats
- Dashboard shows next scheduled run time
- (Stretch) Notification fires on new candidates

---

## Phase 7 — TMDB Integration (Rarity & Cultural Value)

**Goal:** Enrich scoring with streaming availability and cultural significance
data from TMDB's API.

**Status:** ⬜ Planned

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 7.1 | `api/src/clients/tmdb_client.py` | ⬜ | TMDB API v3 integration |
| 7.2 | Streaming availability lookup | ⬜ | TMDB's watch providers endpoint |
| 7.3 | Cultural value data enrichment | ⬜ | Ratings, vote count, keywords, awards |
| 7.4 | TVDB → TMDB resolution cache | ⬜ | `tvdb_tmdb_map` table for Sonarr lookups |
| 7.5 | Rarity signal calculator update | ⬜ | Replace neutral 50/100 default with real data |
| 7.6 | Cultural value signal calculator update | ⬜ | Use TMDB ratings instead of *arr metadata |
| 7.7 | Dashboard: streaming availability display | ⬜ | Show which services have each title |

### Implementation Notes

#### TMDB Watch Providers
- **Endpoint:** `GET /movie/{id}/watch/providers` and `GET /tv/{id}/watch/providers`
- Returns flat-rate (subscription), rent, and buy options per region
- Filter by user's region (US default, configurable)
- **Rate limit:** TMDB allows ~40 requests/second. For 500+ movies plus
  series, batch with small delays.

#### Rarity Scoring with Streaming Data
```
Available on 4+ services (Netflix, Hulu, Disney+, etc.)  → 15/100 (very replaceable)
Available on 2-3 services                                 → 35/100
Available on 1 service                                    → 60/100
Not on any streaming service                              → 90/100 (rare, keep)
```

#### Cultural Value Enrichment
TMDB provides richer data than what Radarr/Sonarr store:
- `vote_average` and `vote_count` — rating reliability
- `keywords` — can flag "cult classic", "award winner" tags
- `release_date` — age-based classic detection
- Genre data — some genres have higher rewatch value (comedy, animation)

#### TVDB → TMDB Resolution
For series from Sonarr (which uses TVDB IDs):
```
1. Check tvdb_tmdb_map table for cached mapping
2. If miss, call TMDB: GET /find/{tvdb_id}?external_source=tvdb_id
3. Cache the result in tvdb_tmdb_map
4. If TMDB returns no match, log warning and use neutral scores
```

#### Caching Strategy
TMDB data changes slowly. Cache streaming availability for 7 days per title.
Cultural data (ratings, keywords) can be cached for 30 days. A `tmdb_cache`
table stores raw TMDB responses with TTL timestamps.

### Exit Criteria
- TMDB client fetches streaming availability and ratings for all titles
- TVDB → TMDB resolution works for all Sonarr series
- Rarity signal uses real streaming data instead of neutral default
- Cultural value signal uses TMDB ratings instead of *arr metadata
- Dashboard shows streaming provider icons per title
- TMDB rate limits respected, batch fetching works for full library

---

## Phase 8 — Removal Tracking & Reporting

**Goal:** Complete the removal workflow — user deletes media by hand in
Radarr/Sonarr, then marks items complete in the dashboard. Track total
space reclaimed over time.

**Status:** ⬜ Planned

### Deliverables

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 8.1 | Mark-as-removed API endpoint | ⬜ | Moves item to removal_history |
| 8.2 | Batch mark-as-removed | ⬜ | Select multiple and mark at once |
| 8.3 | Removal history dashboard page | ⬜ | Timeline of removals with sizes |
| 8.4 | Space reclaimed reporting | ⬜ | Cumulative chart, progress toward 7.5 TB goal |
| 8.5 | Stale candidate detection | ⬜ | Flag candidates that disappeared from *arrs |
| 8.6 | Export functionality | ⬜ | CSV export of candidates or removal history |

### Implementation Notes

#### Mark-as-Removed Workflow
```
1. User reviews candidates in dashboard
2. User deletes title in Radarr or Sonarr (by hand)
3. User clicks "Mark as removed" in Swabbarr dashboard
4. Swabbarr copies title/size/score to removal_history
5. Item cleared from active suggestions
6. Next scoring run confirms title is gone from *arr library
```

#### Stale Candidate Detection
On each scoring run, if a title exists in `media_items` but is no longer
returned by Radarr/Sonarr, it was deleted outside of Swabbarr's workflow.
The scoring engine should:
1. Detect the missing title
2. Auto-move it to `removal_history` with a note: "Removed outside Swabbarr"
3. Credit the file size toward space reclaimed
4. Remove from active `media_items`

This handles the case where you delete something in Radarr/Sonarr and
forget to mark it in the dashboard — the system self-heals on next run.

#### Space Reclaimed Reporting
The dashboard shows a progress tracker:
- **Target:** 7.5 TB to reclaim (configurable in settings)
- **Reclaimed so far:** Sum of `removal_history.file_size_bytes`
- **Remaining:** Target minus reclaimed
- **Visual:** Progress bar or gauge chart
- **Timeline:** Line chart of cumulative space reclaimed over time

#### CSV Export
Export options for data portability:
- Current candidates list (title, score, size, signals)
- Removal history (title, date removed, size, final score)
- Full score dump (all titles, all signals, current run)

### Exit Criteria
- Mark-as-removed works for single and batch selections
- Removal history page shows all removals with dates and sizes
- Space reclaimed progress bar shows progress toward target
- Stale candidate detection auto-moves deleted titles
- CSV export works for candidates, history, and full scores
- Cumulative reclamation chart displays correctly

---

## Open Questions & Future Considerations

### Questions to Resolve During Development

1. **Tautulli → TMDB ID mapping:** What's the most reliable cross-reference
   method? Plex rating_key → Radarr/Sonarr title match, or does Tautulli
   expose TMDB/TVDB IDs directly in its API?

2. **Anime handling:** Sonarr-Anime titles may have different TMDB coverage.
   Should anime have different default weights or scoring rules?

3. **Multi-file titles:** Some movies have multiple files (e.g., a 1080p and
   a 4K copy). How does Radarr report these? Sum the sizes? Score once?

4. **User weighting:** Currently all 11 users are equal. Should there be an
   option to weight household (local) users differently from remote users?
   Decision: No, everyone is equal. Revisit only if requested.

5. **Recency decay curve:** Exponential decay is the plan, but what's the
   half-life? 6 months? 1 year? This should be configurable in the dashboard
   alongside the scoring weights.

### Future Phase Ideas (Post-MVP)

- **Plex watchlist integration:** If a title is on someone's Plex watchlist,
  boost its keep score (they intend to watch it)
- **Genre-based scoring adjustments:** Some genres (documentaries, kids content)
  might deserve different treatment
- **Collection awareness:** Don't suggest removing 1 movie from a trilogy —
  detect collections and score them as a unit
- **Disk usage forecasting:** Based on current download rate from Radarr/Sonarr,
  estimate when the NAS will be full again
- **User dashboard:** Let Plex users see their own watch stats and what
  they've requested vs watched (accountability transparency)
- **Quality downgrade suggestions:** Instead of removing, suggest replacing
  a 4K remux with a 1080p encode to save space while keeping the title
- **Seasonal scoring:** Holiday movies score higher in November/December,
  summer blockbusters in June/July

---

## Development Workflow

### Branch Strategy
- `main` — stable, deployable
- `dev` — integration branch
- `feature/{phase}-{description}` — per-feature branches
- Example: `feature/p2-tautulli-client`, `feature/p3-scoring-engine`

### Commit Convention
- `feat: {description}` — new feature
- `fix: {description}` — bug fix
- `docs: {description}` — documentation
- `refactor: {description}` — code restructure
- `chore: {description}` — build, deps, config

### CI/CD
- GitHub Actions builds Docker images on push to `main`
- Images pushed to GHCR (`ghcr.io/papabeardoes/swabbarr-api`, etc.)
- Lofn pulls from GHCR and deploys via K8s manifests
- No auto-deploy — manual pull and apply on Lofn

### Testing Strategy
- API clients: test against live services on Lofn (real data)
- Scoring engine: determinism tests (same inputs → same outputs)
- API endpoints: integration tests with test database
- Dashboard: manual testing during development, browser-based

---

*This document tracks all planning, deliverables, and design decisions for
the Swabbarr project. Update phase statuses as work progresses.*
