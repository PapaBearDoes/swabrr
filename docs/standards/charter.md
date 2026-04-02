# Clean Architecture Charter — Swabbarr

## Sacred Principles - NEVER TO BE VIOLATED

**Version**: v1.0.0
**Last Modified**: 2026-04-01
**Repository**: https://github.com/PapaBearDoes/swabbarr

---

# 🎯 SWABBARR VISION (Never to be violated):

## **Swabbarr Keeps Your Media Library Lean and Intentional**:
1. **Score**     → Evaluate every title against watch activity, requests, rarity, and cultural value
2. **Surface**   → Present removal candidates through a clear, reviewable web dashboard
3. **Reclaim**   → Enable informed pruning decisions that maximize recovered space
4. **Sustain**   → Run on a schedule so the library never silently bloats again

---

## 🏛️ **IMMUTABLE ARCHITECTURE RULES**

### **Rule #1: Factory Function Pattern - MANDATORY**
- **ALL managers MUST use factory functions** — `create_[manager_name]()`
- **NEVER call constructors directly**
- **Factory functions enable**: dependency injection, testing, consistency
- **Examples**: `create_db_manager()`, `create_scoring_engine()`, `create_tautulli_client()`

### **Rule #2: Dependency Injection - REQUIRED**
- **All managers accept dependencies through constructor parameters**
- **Logging manager is always injected; config manager where needed**
- **Additional managers passed as named parameters**
- **Clean separation of concerns maintained**

### **Rule #3: Additive Development - STANDARD**
- **New functionality ADDS capability, never REMOVES**
- **Maintain backward compatibility within a component**
- **Each feature builds on the previous foundation**
- **Scoring model capabilities should only grow, never regress**

### **Rule #4: Configuration — Static Settings Only**

Swabbarr is a single-instance application (not multi-tenant). All configuration
is static — set at deploy time via environment variables and Docker Secrets.

| Type | Sensitive? | Storage | Examples |
|------|-----------|---------|---------|
| API keys, DB password | ✅ Yes | Docker Secrets | `swabbarr_db_password`, `swabbarr_tautulli_api_key` |
| Log level, scoring weights, API URLs | ❌ No | `.env` file | `SWABBARR_LOG_LEVEL`, `SWABBARR_TAUTULLI_URL` |

The two-layer stack for static config:
```
.env file                 ← non-sensitive runtime values (not committed)
      ↓ overridden by
Docker Secrets            ← sensitive values only (never in .env or source)
```

#### **User-Configurable Scoring Weights**
Scoring weights (watch activity, request accountability, rarity, cultural value,
size efficiency) are stored in the database and editable through the web dashboard.
These are **not** environment variables — they are application state that the user
adjusts at runtime. The API writes them to PostgreSQL; the scoring engine reads
them on each run.

### **Rule #5: Resilient Validation with Smart Fallbacks - PRODUCTION CRITICAL**
- **Invalid configurations trigger graceful fallbacks, not system crashes**
- **Data type validation provides safe defaults with logging**
- **A database failure is non-fatal for reads** — use last cached scores, log warning
- **External API failure (Tautulli, Seerr, Radarr/Sonarr) is non-fatal** — log, skip that data source, continue with partial data
- **System prioritizes operational continuity**
- **Clear error logging for debugging while maintaining service availability**

### **Rule #6: File Versioning System - MANDATORY**
- **ALL code files MUST include version headers** in the format `v[Major].[Minor].[Patch]`
- **Version format**:
  - `v1.0.0` — initial release
  - `v1.1.0` — new feature or meaningful change
  - `v1.1.1` — bug fix or small improvement
- **Header placement**: At the top of each file in the module docstring
- **Version increments**: Required for each meaningful change
- **Cross-conversation continuity**: Ensures accurate file tracking across sessions

#### **Required Version Header Format — Swabbarr Standard:**

```python
"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================

MISSION:
    Keep your media library lean and intentional by scoring every title
    against watch activity, requests, rarity, and cultural value —
    then surfacing the best candidates for removal.

============================================================================
{File Description — plain English, one or two sentences}
----------------------------------------------------------------------------
FILE VERSION: v{Major}.{Minor}.{Patch}
LAST MODIFIED: {YYYY-MM-DD}
COMPONENT: {component-name}   ← swabbarr-api | swabbarr-web | swabbarr-db
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""
```

#### **Version Increment Guidelines:**
- **Major** (`v2.0.0`): Breaking changes, architectural shifts
- **Minor** (`v1.1.0`): New functionality, meaningful additions
- **Patch** (`v1.0.1`): Bug fixes, small improvements, documentation updates
- **Cross-session**: Always increment patch or minor when continuing work across conversations


### **Rule #7: Configuration and Secrets Hygiene - MANDATORY**

#### **Secret Naming Convention**
Swabbarr uses `swabbarr_{purpose}` for all Docker Secret filenames.

```
swabbarr/
└── api/secrets/
    ├── swabbarr_db_password            ← PostgreSQL password
    ├── swabbarr_tautulli_api_key       ← Tautulli API key
    ├── swabbarr_radarr_api_key         ← Radarr API key
    ├── swabbarr_sonarr_api_key         ← Sonarr API key
    ├── swabbarr_sonarr_anime_api_key   ← Sonarr-Anime API key
    ├── swabbarr_seerr_api_key          ← Seerr API key
    └── swabbarr_tmdb_api_key           ← TMDB API key (optional, for streaming availability)
```

All `secrets/` directories are gitignored. Only `secrets/README.md` is committed.

#### **Environment Variable Naming Convention**
Static (non-sensitive) config uses `SWABBARR_{CATEGORY}_{NAME}` in SCREAMING_SNAKE_CASE:

```bash
# Logging
SWABBARR_LOG_LEVEL=INFO

# Database
SWABBARR_DB_HOST=swabbarr-db
SWABBARR_DB_PORT=5432

# External Service URLs
SWABBARR_TAUTULLI_URL=http://10.20.30.x:8181
SWABBARR_RADARR_URL=http://10.20.30.x:7878
SWABBARR_SONARR_URL=http://10.20.30.x:8989
SWABBARR_SONARR_ANIME_URL=http://10.20.30.x:8990
SWABBARR_SEERR_URL=http://10.20.30.x:5055

# Scoring Schedule
SWABBARR_SCORE_CRON=0 3 * * 0    # Weekly at 3am Sunday
```

#### **Rule #7 Implementation Process**
1. **Classify the value**: Sensitive (API key, password)? → Docker Secret. Behavioral (URL, log level)? → `.env`
2. **Audit first**: Check `.env.template` for existing variables and `secrets/` before creating new ones
3. **Reuse when possible**: Map new needs to existing variables or secrets
4. **Document in `.env.template`**: Every `.env` variable must have a commented entry in `.env.template`

#### **Reading Secrets in Python**
```python
def _read_secret(path: str) -> str:
    """Read a Docker Secret from its file path. Strips trailing whitespace."""
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"Docker Secret not found at: {path}")
    except PermissionError:
        raise RuntimeError(f"Cannot read Docker Secret at: {path} — permission denied")
```

#### **Red Flags**
- ❌ Sensitive values in `.env`, compose files, or source code
- ❌ Non-sensitive values stored as Docker Secrets (unnecessary complexity)
- ❌ `.env` variables undocumented in `.env.template`
- ❌ Creating new secrets without auditing existing ones first
- ❌ API keys hardcoded anywhere in source code


### **Rule #8: External API Client Pattern - MANDATORY**

Swabbarr integrates with multiple external services. Each integration MUST follow
a consistent client pattern for maintainability and resilience.

#### **Required Client Structure**
```python
class [Service]Client:
    def __init__(self, base_url: str, api_key: str, log) -> None:
        """Constructor with explicit URL + key injection."""

    async def health_check(self) -> bool:
        """Verify the service is reachable. Called at startup."""

    async def [data_method](self, ...) -> list[dict] | dict | None:
        """Fetch data with timeout, retry, and error handling."""


def create_[service]_client(base_url: str, api_key: str, log) -> [Service]Client:
    """Factory function."""
```

#### **Required Integrations**
| Client | Service | Data Provided |
|--------|---------|---------------|
| `TautulliClient` | Tautulli | Watch history, play counts, last watched, completion % |
| `SeerrClient` | Seerr | Request history, requestor identity, request date |
| `RadarrClient` | Radarr | Movie metadata, file size, quality profile, TMDB ID |
| `SonarrClient` | Sonarr | Series metadata, episode counts, file size, quality |
| `SonarrAnimeClient` | Sonarr-Anime | Same as Sonarr, separate instance |
| `TMDBClient` | TMDB API | Streaming availability, ratings, cultural significance (optional) |

#### **Resilience Requirements**
- **Timeout**: All HTTP calls must have a configurable timeout (default 30s)
- **Retry**: Transient failures (5xx, timeouts) retry up to 3 times with exponential backoff
- **Graceful degradation**: If a service is unreachable, scoring continues with partial data — log a warning, do not crash
- **Health check at startup**: All clients verify connectivity; failures are logged as warnings, not fatal errors
- **httpx for all HTTP**: Use `httpx.AsyncClient` — never `requests` or `urllib`
- **Rate limiting**: Respect external API rate limits; add configurable delay between batch calls


### **Rule #9: LoggingConfigManager with Colorization Enforcement - MANDATORY**

All components MUST use `LoggingConfigManager` for consistent, colorized log output.

#### **Required File Structure**
- **File Name**: `src/managers/logging_config_manager.py`
- **Factory Function**: `create_logging_config_manager()` (NEVER call constructor directly)
- **Import Pattern**: `from src.managers.logging_config_manager import create_logging_config_manager`

#### **Required Colorization Scheme**
| Log Level | Color | ANSI Code | Symbol | Purpose |
|-----------|-------|-----------|--------|---------|
| CRITICAL | Bright Red (Bold) | `\033[1;91m` | 🚨 | System failures |
| ERROR | Red | `\033[91m` | ❌ | Exceptions, failed operations |
| WARNING | Yellow | `\033[93m` | ⚠️ | Degraded state, potential issues |
| INFO | Cyan | `\033[96m` | ℹ️ | Normal operations, status updates |
| DEBUG | Gray | `\033[90m` | 🔍 | Diagnostic details, verbose output |
| SUCCESS | Green | `\033[92m` | ✅ | Successful completions (custom level 25) |

#### **Human-Readable Output Format**
```
[2026-04-01 03:00:00] INFO     | swabbarr-api.scoring_engine  | ℹ️ Starting scheduled scoring run
[2026-04-01 03:00:01] SUCCESS  | swabbarr-api.tautulli_client | ✅ Fetched watch history for 523 titles
[2026-04-01 03:00:02] WARNING  | swabbarr-api.tmdb_client     | ⚠️ TMDB API unreachable — scoring without streaming data
[2026-04-01 03:00:15] SUCCESS  | swabbarr-api.scoring_engine  | ✅ Scored 523 movies, 87 series — 47 removal candidates
[2026-04-01 03:00:15] ERROR    | swabbarr-api.seerr_client    | ❌ Connection refused to Seerr at http://10.20.30.x:5055
```

#### **Implementation Checklist**
- [ ] `logging_config_manager.py` exists in `src/managers/`
- [ ] Factory function named `create_logging_config_manager()`
- [ ] Color scheme matches the standard table above
- [ ] SUCCESS level (25) registered with `logger.success()` method
- [ ] Supports `LOG_FORMAT=human` (default) and `LOG_FORMAT=json`
- [ ] TTY detection for automatic color support
- [ ] Noisy libraries silenced (httpx, uvicorn, asyncpg, etc.)


### **Rule #10: Python 3.13 and Virtual Environment Standardization - MANDATORY**

All Swabbarr Docker containers MUST use Python 3.13 with virtual environments for package isolation.

#### **Docker Multi-Stage Build Pattern**
```dockerfile
# Stage 1: Builder
FROM python:3.13-slim AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH"
COPY --from=builder /opt/venv /opt/venv
```

#### **Critical Requirements**
| Requirement | Correct | Incorrect |
|-------------|---------|-----------|
| Base image | `python:3.13-slim` | `python:3.12-slim`, any other version |
| Venv creation | `python -m venv /opt/venv` | Installing to system Python |
| Package copy | `COPY --from=builder /opt/venv /opt/venv` | Copying site-packages directly |
| PATH setting | `ENV PATH="/opt/venv/bin:$PATH"` | Relying on system Python |


### **Rule #11: AI Assistant File System Tool Usage - MANDATORY**

When Claude or other AI assistants are editing project files, the correct tools must be used for the file location.

#### **User's Computer (Windows paths, network paths)**
For files on the user's Windows machine or network shares (paths like `Y:\git\swabbarr\...`):

```
Desktop Commander:read_file        - Read file contents
Desktop Commander:edit_block       - Make targeted edits (preferred for changes)
Desktop Commander:write_file       - Write entire file (use for new files or full rewrites)
Desktop Commander:list_directory   - Browse directories
Desktop Commander:start_search     - Search for files or content
```

#### **Claude's Container**
For files in Claude's own container (`/home/claude/`, `/mnt/user-data/`):

```
str_replace    - Edit files in Claude's container
view           - Read files in Claude's container
create_file    - Create files in Claude's container
bash_tool      - Execute commands in Claude's container
```

#### **How to Identify File Location**
| Path Pattern | Location | Tools to Use |
|--------------|----------|-------------|
| `Y:\git\...` | User's Windows machine | `Desktop Commander:*` |
| `\\10.20.30.*\...` | Network share | `Desktop Commander:*` |
| `/home/claude/...` | Claude's container | `str_replace`, `view`, etc. |
| `/mnt/user-data/...` | Claude's container | `str_replace`, `view`, etc. |

#### **Best Practices**
1. **Prefer `Desktop Commander:edit_block`** over `write_file` for targeted changes
2. **Always read the file first** before editing to confirm current content
3. **Chunk writes to 25–30 lines maximum** — this is standard practice, not an emergency measure


### **Rule #12: Pure Python Docker Entrypoints with PUID/PGID Support - MANDATORY**

All Swabbarr containers MUST use Pure Python entrypoint scripts with `tini` for runtime PUID/PGID configuration.

#### **Required Architecture**
```
Container Start (as root)
  ↓
tini (PID 1) — signal handling, zombie reaping
  ↓
docker-entrypoint.py (Python)
  ├─ Read PUID/PGID from environment
  ├─ Fix ownership of writable directories
  ├─ Drop privileges (os.setgid → os.setuid)
  └─ exec application
  ↓
Application process (runs as configured user)
```

#### **Dockerfile Requirements**
```dockerfile
FROM python:3.13-slim AS runtime

ARG DEFAULT_UID=1000
ARG DEFAULT_GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g ${DEFAULT_GID} appgroup && \
    useradd -m -u ${DEFAULT_UID} -g ${DEFAULT_GID} appuser

COPY docker-entrypoint.py /app/docker-entrypoint.py

# NOTE: Do NOT use USER directive — entrypoint handles this at runtime
ENTRYPOINT ["/usr/bin/tini", "--", "python", "/app/docker-entrypoint.py"]
CMD ["python", "src/main.py"]
```

#### **Environment Variables**
| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | 1000 | User ID to run the component as |
| `PGID` | 1000 | Group ID to run the component as |

#### **Implementation Checklist**
- [ ] `docker-entrypoint.py` exists in the component's root directory
- [ ] Dockerfile installs `tini` in runtime stage
- [ ] Dockerfile does NOT use `USER` directive
- [ ] `ENTRYPOINT` uses tini + Python pattern
- [ ] Entrypoint reads `PUID`/`PGID` from environment
- [ ] Entrypoint fixes ownership of all writable directories
- [ ] Entrypoint drops privileges before exec


### **Rule #13: Scoring Engine Architecture - MANDATORY**

The scoring engine is Swabbarr's core. It MUST be deterministic, auditable, and
configurable without code changes.

#### **Scoring Model**
Every title (movie or series) receives a **keep score** from 0–100. Lower scores
are stronger removal candidates. The score is a weighted sum of five signal categories:

| Signal Category | Default Weight | Data Source | Measures |
|----------------|---------------|-------------|----------|
| **Watch Activity** | 40% | Tautulli | Play count, unique viewers, recency, completion % |
| **Rarity & Replaceability** | 20% | TMDB / manual | Streaming availability, file rarity |
| **Request Accountability** | 15% | Seerr | Requested? Did requestor watch it? |
| **Size Efficiency** | 15% | Radarr/Sonarr | Value-per-GB — large low-score files rank lower |
| **Cultural Value** | 10% | TMDB | Rating, awards, "classic" status |

Weights are user-configurable through the dashboard and stored in PostgreSQL.
They MUST sum to 100%.

#### **TV Show Weighting**
TV series receive a **removal priority multiplier** because of their outsized
storage footprint. A series scoring 30/100 that occupies 180 GB is a much more
impactful removal than a movie scoring 30/100 at 8 GB. The dashboard surfaces
this as "reclaimable space" alongside the keep score.

#### **Primary Tracking Key**
All media is tracked by **TMDB ID** as the primary identifier. This is the common
key used to merge data across Tautulli, Seerr, Radarr, Sonarr, and TMDB. For TV
series, Sonarr uses TVDB IDs internally — the client must resolve these to TMDB IDs
during data ingestion.

#### **Scheduling**
Scoring runs are triggered by **APScheduler** running inside the FastAPI process —
not by system cron or a separate worker container. The dashboard displays "next
scheduled run" and "last run status." Manual triggers invoke the same scoring
function via an API endpoint.

#### **Scoring Run Lifecycle**
```
1. Scheduled trigger (APScheduler) or manual trigger (dashboard button)
2. Fetch data from all external APIs (Tautulli, Seerr, Radarr, Sonarr, TMDB)
3. Merge data by TMDB ID into unified records
4. Apply scoring formula with current weights
5. Persist scores + breakdown to PostgreSQL (with timestamp)
6. Flag titles below configurable threshold as removal candidates
7. Log summary: titles scored, candidates flagged, potential space reclaimable
```

#### **Determinism & Auditability**
- **Same inputs = same scores.** No randomness in the scoring formula.
- **Score breakdown stored per-title**: The dashboard shows exactly WHY a title scored low — which category dragged it down.
- **Historical scores preserved**: Each scoring run is timestamped. Score trends over time are visible in the dashboard.
- **No auto-deletion. Ever.** Swabbarr recommends. A human decides.
- **Manual removal workflow**: The user deletes media by hand through Radarr/Sonarr, then marks the item as "removed" in the Swabbarr dashboard to clear it from the suggestions list. Swabbarr never sends delete commands to the *arr APIs.

#### **Red Flags**
- ❌ Scoring formula that cannot be explained to the user
- ❌ Auto-deleting media without human approval
- ❌ Weights that don't sum to 100%
- ❌ Scoring run that crashes on partial API data instead of degrading gracefully
- ❌ Score results not persisted (ephemeral scoring defeats auditability)


### **Rule #14: Database Access Pattern - MANDATORY**

PostgreSQL is Swabbarr's source of truth for scores, configuration, and audit history.
All access must be controlled, safe, and consistent.

#### **Connection Pool**
All DB access goes through `DBManager.acquire()` as an async context manager.

```python
# ✅ CORRECT
async with db_manager.acquire() as conn:
    row = await conn.fetchrow(
        "SELECT * FROM media_scores WHERE tmdb_id = $1", tmdb_id
    )

# ❌ WRONG — never store a raw connection outside acquire()
conn = await pool.acquire()
```

#### **Query Safety — Parameterized Queries Only**
All SQL queries MUST use asyncpg's parameterized format (`$1`, `$2`, ...).
String interpolation in SQL is a hard prohibition.

```python
# ✅ CORRECT
await conn.fetch(
    "SELECT * FROM media_scores WHERE media_type = $1 AND keep_score < $2",
    media_type, threshold,
)

# ❌ WRONG — SQL injection risk, immediate violation
await conn.fetch(f"SELECT * FROM media_scores WHERE media_type = '{media_type}'")
```

#### **Who Is Allowed to Query the DB**
| Component | Allowed? | Notes |
|-----------|---------|-------|
| `DBManager` | ✅ Yes | Owns the pool; exposes `acquire()` |
| `ScoringEngine` | ✅ Yes | Writes score results via `DBManager.acquire()` |
| `ConfigManager` | ✅ Yes | Reads/writes scoring weights and settings |
| FastAPI endpoints | ✅ Yes | Via `DBManager.acquire()` for dashboard data |
| External API clients | ❌ No | Clients fetch from external services only |


#### **Red Flags**
- ❌ f-string SQL queries anywhere
- ❌ Raw pool access outside `DBManager.acquire()`
- ❌ External API clients writing to the DB directly
- ❌ Missing parameterized queries


---

## 🔧 **MANAGER IMPLEMENTATION STANDARDS**

### **Required Manager Structure:**
```python
"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================
{Manager Description}
----------------------------------------------------------------------------
FILE VERSION: v{Major}.{Minor}.{Patch}
LAST MODIFIED: {YYYY-MM-DD}
COMPONENT: swabbarr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""

class [Manager]Manager:
    def __init__(self, [dependencies...], log) -> None:
        """Constructor with dependency injection. log is always last."""

    async def [operation](self, ...):
        """Async operations for DB/cache/network managers."""

    def [sync_operation](self, ...):
        """Sync operations for config/logging managers."""


async def create_[manager]_manager([parameters]) -> [Manager]Manager:
    """Async factory function for managers that require IO at startup."""
    ...

def create_[manager]_manager([parameters]) -> [Manager]Manager:
    """Sync factory function for managers that don't require IO at startup."""
    ...


__all__ = ['[Manager]Manager', 'create_[manager]_manager']
```

---

## 🏥 **PRODUCTION RESILIENCE PHILOSOPHY**

### **Operational Continuity Over Perfection**
Swabbarr serves a household's media library. A failed scoring run should never
corrupt existing data or leave the system in an unusable state.

- **System availability is paramount** — prefer safe defaults over crashes
- **Graceful degradation** when external APIs are unreachable
- **Comprehensive logging** of all issues for debugging
- **Partial data is better than no data** — score with what you have, flag gaps

### **Error Handling Hierarchy**
1. **Unrecoverable errors** (missing DB, bad schema): Fail-fast with clear log at startup
2. **DB pool failure at startup**: Fail-fast — Swabbarr cannot operate without the DB
3. **External API failure**: Non-fatal — log warning, score without that data source, note in results
4. **Scoring formula error**: Log error, preserve previous scores, do not overwrite with bad data
5. **Dashboard request error**: Return appropriate HTTP error, never expose stack traces

---

## 🚨 **VIOLATION PREVENTION**

### **Before Making ANY Code Change:**
1. Does this maintain the factory function pattern? ✅ Required
2. Does this preserve all existing functionality? ✅ Required
3. Does this follow dependency injection principles? ✅ Required
4. Does this use the correct config layer (sensitive → secrets, behavioral → `.env`)? ✅ Required
5. Does this implement resilient error handling? ✅ Required
6. Does this include a proper file version header with `COMPONENT`? ✅ Required
7. Did I audit existing secrets before creating new ones? ✅ Required
8. Does this use LoggingConfigManager with standard colorization? ✅ Required
9. Does this use Python 3.13 with `/opt/venv`? ✅ Required
10. Am I using the correct file system tools for the file location? ✅ Required
11. Does the Dockerfile use a Pure Python entrypoint with tini? ✅ Required
12. Do all external API clients follow the client pattern (timeout, retry, health check)? ✅ Required
13. Is the scoring engine deterministic, auditable, and non-destructive? ✅ Required
14. Are all SQL queries parameterized with `$1, $2, ...` — no f-string SQL anywhere? ✅ Required

### **Red Flags — IMMEDIATE STOP:**
- ❌ Direct constructor calls in production code
- ❌ Hardcoded configuration values in source code (API keys, URLs, weights)
- ❌ Sensitive values in `.env`, compose files, or source code
- ❌ `print()` statements instead of LoggingConfigManager
- ❌ Missing file version headers or `COMPONENT` field
- ❌ Using `USER` directive in Dockerfile instead of entrypoint privilege dropping
- ❌ Bash scripts for Docker entrypoints
- ❌ Missing `tini` for PID 1 signal handling
- ❌ External API client without timeout/retry/health check
- ❌ Scoring engine that auto-deletes media
- ❌ f-string SQL queries
- ❌ Raw pool access outside `DBManager.acquire()`
- ❌ Scoring run that crashes instead of degrading on partial API data


---

## 🎯 **ARCHITECTURAL SUCCESS METRICS**

### **Code Quality:**
- ✅ All managers use factory functions
- ✅ All configuration externalized to `.env` / Docker Secrets
- ✅ Scoring weights stored in PostgreSQL, editable via dashboard
- ✅ Clean dependency injection throughout
- ✅ Production-ready resilient error handling
- ✅ Consistent file versioning with `COMPONENT` field across all code files
- ✅ No secrets in source control
- ✅ No hardcoded API keys or URLs anywhere

### **Scoring Engine Health:**
- ✅ Deterministic: same inputs always produce same scores
- ✅ Auditable: score breakdown stored and visible per-title
- ✅ Non-destructive: recommendations only, never auto-deletes
- ✅ Resilient: partial API data produces partial scores, not crashes
- ✅ Historical: scoring runs are timestamped and preserved

### **Production Readiness:**
- ✅ Operational continuity under external API failures
- ✅ Comprehensive, colorized logging for debugging
- ✅ PUID/PGID working correctly for volume mounts on Lofn
- ✅ Scheduled scoring runs via cron with manual trigger option

---

## 💪 **COMMITMENT**

**This architecture serves the household's media library by providing:**
- **Intelligent pruning recommendations** — backed by real usage data, not guesswork
- **Full transparency** — every score is explainable, every recommendation is reviewable
- **Human-in-the-loop safety** — no media is ever deleted without explicit approval
- **Reliable scheduled operation** — the library never silently bloats again
- **Professional-grade engineering** — the same standards we hold for all our projects

**The media library is curated by the household. Swabbarr just makes sure nothing is forgotten in the bilge.**

---

**Status**: Living Document
**Authority**: Project Lead + AI Assistant Collaboration
**Enforcement**: Mandatory for ALL code changes
**Version**: v1.0.0

---

## 🏆 **ARCHITECTURE PLEDGE**

*"We commit to maintaining Clean Architecture principles with production-ready resilience, consistent file versioning, proper secrets management, and a scoring engine that is always deterministic, auditable, and non-destructive — because your media library deserves better than guesswork."*

---

**Built to keep the deck clean** 🏴‍☠️
