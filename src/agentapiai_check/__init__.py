"""AgentApiAI Check — the open-source ruler for AI API relays."""

from .detect import (  # noqa: F401
    PROBES,
    PROTOCOLS,
    VERSION,
    full_report,
    infer_family,
    infer_protocol,
    probe_summary,
)

__version__ = VERSION
__all__ = [
    "PROBES",
    "PROTOCOLS",
    "VERSION",
    "full_report",
    "infer_family",
    "infer_protocol",
    "probe_summary",
]
