"""A minimal tool-calling loop for any OpenAI-compatible endpoint.

Defaults target Groq and openai/gpt-oss-120b, but base_url/model can point at
Ollama, vLLM, LM Studio, or anything else that speaks chat completions.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from openai import BadRequestError, OpenAI, RateLimitError

from .prompts import SYSTEM_PROMPT
from .tools import dispatch, get_tools

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"


def _tool_use_failure_feedback(error: BadRequestError) -> str | None:
    """Feedback for the model when the endpoint rejected its own tool call.

    Some endpoints (Groq) validate tool-call arguments against the JSON schema
    server-side and answer 400 with code 'tool_use_failed' instead of returning
    the call. Returns None for unrelated 400s, which should keep raising.
    """
    body = error.body if isinstance(error.body, dict) else {}
    body = body.get("error", body)
    if not isinstance(body, dict) or body.get("code") != "tool_use_failed":
        return None
    parts = [
        "Your last tool call was rejected because its arguments did not match "
        "the tool's parameter schema.",
        str(body.get("message", "")),
    ]
    failed = body.get("failed_generation")
    if failed:
        parts.append(f"This is the call you attempted:\n{failed}")
    parts.append(
        "Call the tool again with arguments that follow the schema exactly - "
        "same field names, same 'type'/'layout' values, all required fields."
    )
    return "\n\n".join(p for p in parts if p)


_CREATE_TOOLS = ["create_document", "create_spreadsheet", "create_presentation"]
_EDIT_TOOLS = ["read_office_file", "edit_document", "edit_spreadsheet", "edit_presentation"]

_EDIT_HINTS = re.compile(
    r"\.(docx|xlsx|pptx)\b|\b(edit|update|modify|revise|change|fix|rename|append|"
    r"insert|delete|remove|existing|add .{0,40}(to|into))\b",
    re.IGNORECASE,
)


def _tools_for(prompt: str) -> list[dict]:
    """Send the edit tools only when the prompt suggests an existing file.

    Tool schemas are prompt tokens on every round; all seven together
    (~5k tokens) would blow tight per-minute budgets like Groq's free tier.
    """
    if _EDIT_HINTS.search(prompt):
        return get_tools()
    return get_tools(_CREATE_TOOLS)


def _rate_limit_delay(error: RateLimitError) -> float:
    """Seconds to wait before retrying a 429, from the provider's own hint.

    Groq puts 'Please try again in 7.66s' in the message; fall back to the
    Retry-After header, then to a safe default.
    """
    body = error.body if isinstance(error.body, dict) else {}
    body = body.get("error", body) if isinstance(body, dict) else {}
    match = re.search(r"try again in ([0-9.]+)s", str(body.get("message", "")))
    if match:
        return min(float(match.group(1)) + 1.0, 90.0)
    retry_after = error.response.headers.get("retry-after")
    if retry_after and retry_after.replace(".", "", 1).isdigit():
        return min(float(retry_after) + 1.0, 90.0)
    return 15.0


@dataclass
class RunResult:
    """Files created during a run, plus the model's final text reply."""

    files: list[Path] = field(default_factory=list)
    reply: str = ""


class OfficeAgent:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = GROQ_BASE_URL,
        api_key: str | None = None,
        out_dir: str | Path = "output",
        max_rounds: int = 8,
        temperature: float = 0.3,
        max_completion_tokens: int | None = None,
        docx_template: str | Path | None = None,
        pptx_template: str | Path | None = None,
        client: OpenAI | None = None,
    ) -> None:
        api_key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if client is None and not api_key:
            raise ValueError(
                "no API key: pass api_key= or set GROQ_API_KEY (or OPENAI_API_KEY)"
            )
        self.client = client or OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.out_dir = Path(out_dir)
        self.max_rounds = max_rounds
        # Low temperature: tool arguments are structured output, and sampling
        # hot is where most schema misses and threadbare content come from.
        self.temperature = temperature
        # Optional output cap. Some providers count it against per-minute
        # token limits up front, so capping it lets big requests through
        # tiers they would otherwise never fit (e.g. Groq free tier).
        self.max_completion_tokens = max_completion_tokens
        self.templates: dict[str, Path] = {}
        if docx_template:
            self.templates["docx"] = Path(docx_template)
        if pptx_template:
            self.templates["pptx"] = Path(pptx_template)

    def run(self, prompt: str) -> RunResult:
        """Ask the model to fulfil `prompt`, executing its tool calls."""
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        result = RunResult()

        request: dict = {
            "model": self.model,
            "tools": _tools_for(prompt),
            "tool_choice": "auto",
            "temperature": self.temperature,
        }
        if self.max_completion_tokens is not None:
            request["max_completion_tokens"] = self.max_completion_tokens

        rounds = 0
        rate_limit_waits = 0
        while rounds < self.max_rounds:
            try:
                response = self.client.chat.completions.create(
                    messages=messages, **request
                )
            except BadRequestError as e:
                feedback = _tool_use_failure_feedback(e)
                if feedback is None:
                    raise
                messages.append({"role": "user", "content": feedback})
                rounds += 1
                continue
            except RateLimitError as e:
                rate_limit_waits += 1
                if rate_limit_waits > 3:
                    raise
                time.sleep(_rate_limit_delay(e))
                continue  # waiting doesn't consume a round
            rounds += 1
            message = response.choices[0].message

            if not message.tool_calls:
                result.reply = message.content or ""
                return result

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
            )
            for tc in message.tool_calls:
                outcome = dispatch(
                    tc.function.name, tc.function.arguments, self.out_dir, self.templates
                )
                if outcome.get("ok") and "file" in outcome:  # reads return no file
                    path = Path(outcome["file"])
                    if path not in result.files:
                        result.files.append(path)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(outcome),
                    }
                )

        result.reply = "stopped: reached max tool-call rounds"
        return result
