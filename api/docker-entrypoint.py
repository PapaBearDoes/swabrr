"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================

Pure Python Docker entrypoint with PUID/PGID support.
Reads user/group IDs from environment, fixes ownership of writable
directories, drops privileges, and execs the application process.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabbarr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""

import os
import sys


def main() -> None:
    """Entrypoint: fix ownership, drop privileges, exec application."""
    puid = int(os.environ.get("PUID", "1000"))
    pgid = int(os.environ.get("PGID", "1000"))

    # Directories that need to be writable by the application
    writable_dirs = [
        "/app",
    ]

    # Fix ownership of writable directories
    for dir_path in writable_dirs:
        if os.path.exists(dir_path):
            os.system(f"chown -R {puid}:{pgid} {dir_path}")

    # Drop privileges: set group first, then user
    try:
        os.setgid(pgid)
        os.setuid(puid)
    except PermissionError:
        # Already running as non-root or target user
        pass

    print(f"[entrypoint] Running as UID={os.getuid()} GID={os.getgid()}")

    # Exec the application command passed via CMD
    if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])
    else:
        print("[entrypoint] No command provided", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
