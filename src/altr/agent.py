"""A minimal tool-calling loop for any OpenAI-compatible endpoint.

Defaults target Groq and openai/gpt-oss-120b, but base_url/model can point at
Ollama, vLLM, LM Studio, or anything else that speaks chat completions.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from openai import BadRequestError, OpenAI

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

        for _ in range(self.max_rounds):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=get_tools(),
                    tool_choice="auto",
                    temperature=self.temperature,
                )
            except BadRequestError as e:
                feedback = _tool_use_failure_feedback(e)
                if feedback is None:
                    raise
                messages.append({"role": "user", "content": feedback})
                continue
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
                if outcome.get("ok"):
                    result.files.append(Path(outcome["file"]))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(outcome),
                    }
                )

        result.reply = "stopped: reached max tool-call rounds"
        return result
