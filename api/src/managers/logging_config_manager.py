"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================

Colorized logging manager with custom SUCCESS level.
Provides consistent, human-readable log output across all components.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabbarr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""

import logging
import os
import sys

# ---------------------------------------------------------------------------
# Custom SUCCESS level (between INFO=20 and WARNING=30)
# ---------------------------------------------------------------------------
SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def _success(self, message, *args, **kwargs):
    """Log a SUCCESS-level message."""
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)


logging.Logger.success = _success


# ---------------------------------------------------------------------------
# ANSI color codes (Rule #9 colorization scheme)
# ---------------------------------------------------------------------------
COLORS = {
    "CRITICAL": "\033[1;91m",  # Bright Red (Bold)
    "ERROR":    "\033[91m",     # Red
    "WARNING":  "\033[93m",     # Yellow
    "SUCCESS":  "\033[92m",     # Green
    "INFO":     "\033[96m",     # Cyan
    "DEBUG":    "\033[90m",     # Gray
}

SYMBOLS = {
    "CRITICAL": "🚨",
    "ERROR":    "❌",
    "WARNING":  "⚠️",
    "SUCCESS":  "✅",
    "INFO":     "ℹ️",
    "DEBUG":    "🔍",
}

RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Custom formatter
# ---------------------------------------------------------------------------
class ColorizedFormatter(logging.Formatter):
    """Human-readable, colorized log formatter."""

    def __init__(self, use_color: bool = True):
        super().__init__()
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        symbol = SYMBOLS.get(level, "")
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        name = record.name

        if self._use_color:
            color = COLORS.get(level, "")
            return (
                f"{color}[{timestamp}] {level:<8} | {name:<35} | "
                f"{symbol} {record.getMessage()}{RESET}"
            )
        return (
            f"[{timestamp}] {level:<8} | {name:<35} | "
            f"{symbol} {record.getMessage()}"
        )


# ---------------------------------------------------------------------------
# Manager class
# ---------------------------------------------------------------------------
class LoggingConfigManager:
    """Manages logging configuration for all Swabbarr components."""

    def __init__(self, component: str = "swabbarr-api") -> None:
        self._component = component
        self._level = self._resolve_level()
        self._use_color = self._detect_color_support()
        self._configure_root()
        self._silence_noisy_libraries()

    def _resolve_level(self) -> int:
        level_name = os.environ.get("SWABBARR_LOG_LEVEL", "INFO").upper()
        return getattr(logging, level_name, logging.INFO)

    def _detect_color_support(self) -> bool:
        log_format = os.environ.get("SWABBARR_LOG_FORMAT", "human").lower()
        if log_format == "json":
            return False
        return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    def _configure_root(self) -> None:
        root = logging.getLogger()
        root.setLevel(self._level)

        # Remove existing handlers
        root.handlers.clear()

        # Add colorized handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(ColorizedFormatter(use_color=self._use_color))
        root.addHandler(handler)

    def _silence_noisy_libraries(self) -> None:
        noisy = [
            "httpx", "httpcore", "uvicorn", "uvicorn.error",
            "uvicorn.access", "asyncpg", "fastapi",
            "apscheduler", "apscheduler.scheduler",
            "apscheduler.executors", "watchfiles",
        ]
        for lib in noisy:
            logging.getLogger(lib).setLevel(logging.WARNING)

    def get_logger(self, name: str) -> logging.Logger:
        """Get a named logger under the component namespace."""
        return logging.getLogger(f"{self._component}.{name}")


# ---------------------------------------------------------------------------
# Factory function (Rule #1: NEVER call constructor directly)
# ---------------------------------------------------------------------------
def create_logging_config_manager(
    component: str = "swabbarr-api",
) -> LoggingConfigManager:
    """Create and return a configured LoggingConfigManager."""
    return LoggingConfigManager(component=component)


__all__ = ["LoggingConfigManager", "create_logging_config_manager"]
