"""officesmith - office document skills for open-weight models."""

from .agent import DEFAULT_MODEL, GROQ_BASE_URL, OfficeAgent, RunResult
from .prompts import SYSTEM_PROMPT
from .schemas import DocumentSpec, PresentationSpec, SpreadsheetSpec
from .tools import dispatch, get_tools

__all__ = [
    "OfficeAgent",
    "RunResult",
    "SYSTEM_PROMPT",
    "DEFAULT_MODEL",
    "GROQ_BASE_URL",
    "DocumentSpec",
    "SpreadsheetSpec",
    "PresentationSpec",
    "get_tools",
    "dispatch",
]
