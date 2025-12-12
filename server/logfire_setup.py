"""Global logfire configuration helper."""

from threading import Lock
from typing import Any

import logfire

_logfire_lock = Lock()
_logfire_configured = False


def ensure_logfire_configured(**config_kwargs: Any) -> None:
    """Configure logfire exactly once per process."""
    global _logfire_configured
    if _logfire_configured:
        return
    with _logfire_lock:
        if _logfire_configured:
            return
        logfire.configure(**config_kwargs)
        _logfire_configured = True
