# Swabbarr — Docker Secrets

This directory holds Docker Secret files for the swabbarr-api container.
**All files in this directory (except this README) are gitignored.**

## Required Secrets

| Filename | Purpose |
|----------|---------|
| `swabbarr_db_password` | PostgreSQL password |
| `swabbarr_tautulli_api_key` | Tautulli API key |
| `swabbarr_radarr_api_key` | Radarr API key |
| `swabbarr_sonarr_api_key` | Sonarr API key |
| `swabbarr_sonarr_anime_api_key` | Sonarr-Anime API key |
| `swabbarr_seerr_api_key` | Seerr API key |

## Optional Secrets

| Filename | Purpose |
|----------|---------|
| `swabbarr_tmdb_api_key` | TMDB API key (enables rarity + cultural scoring) |

## Setup

Create each file with the secret value as plain text, no trailing newline:

```bash
echo -n "your-api-key-here" > swabbarr_tautulli_api_key
echo -n "your-api-key-here" > swabbarr_radarr_api_key
```

Or on Windows (PowerShell):

```powershell
Set-Content -NoNewline -Path "swabbarr_tautulli_api_key" -Value "your-api-key-here"
Set-Content -NoNewline -Path "swabbarr_radarr_api_key" -Value "your-api-key-here"
```

## Finding Your API Keys

- **Tautulli:** Settings → Web Interface → API Key
- **Radarr:** Settings → General → API Key
- **Sonarr:** Settings → General → API Key
- **Seerr:** Settings → General → API Key
- **TMDB:** https://www.themoviedb.org/settings/api → API Read Access Token
