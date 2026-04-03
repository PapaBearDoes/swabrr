# Swabrr — Docker Secrets

This directory holds Docker Secret files for the swabrr-api container.
**All files in this directory (except this README) are gitignored.**

## Required Secrets

| Filename | Purpose |
|----------|---------|
| `swabrr_db_password` | PostgreSQL password |
| `swabrr_encryption_key` | Encryption passphrase for API keys stored in the DB |

**All other API keys** (Tautulli, Radarr, Sonarr, Seerr, TMDB) are configured
through the Swabrr dashboard Settings page and stored encrypted in PostgreSQL.
No individual API key secret files are needed.

## Setup

Create each file with the secret value as plain text:

```bash
# Database password
echo -n "your-db-password" > swabrr_db_password

# Encryption key (generate a strong random key)
openssl rand -base64 32 > swabrr_encryption_key
```

Or on Windows (PowerShell):

```powershell
Set-Content -NoNewline -Path "swabrr_db_password" -Value "your-db-password"

# For the encryption key, use any strong passphrase or random string
Set-Content -NoNewline -Path "swabrr_encryption_key" -Value "your-strong-passphrase-here"
```

## After Setup

1. Start the stack: `docker compose up -d`
2. Open the dashboard: `http://localhost:3000`
3. Go to **Settings** and configure each service (URL + API key)
4. Click **Verify** to test connectivity
5. Enable services and run your first scoring cycle
