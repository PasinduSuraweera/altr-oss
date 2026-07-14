"""altr - open source doc/excel/ppt skills for LLMs."""

from .agent import DEFAULT_MODEL, GROQ_BASE_URL, OfficeAgent, RunResult
from .markdown import markdown_to_blocks
from .pdf import soffice_available, to_pdf
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
    "markdown_to_blocks",
    "to_pdf",
    "soffice_available",
]
