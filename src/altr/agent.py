"""A minimal tool-calling loop for any OpenAI-compatible endpoint.

Defaults target Groq and openai/gpt-oss-120b, but base_url/model can point at
Ollama, vLLM, LM Studio, or anything else that speaks chat completions.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI

from .prompts import SYSTEM_PROMPT
from .tools import dispatch, get_tools

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"


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

    def run(self, prompt: str) -> RunResult:
        """Ask the model to fulfil `prompt`, executing its tool calls."""
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        result = RunResult()

        for _ in range(self.max_rounds):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=get_tools(),
                tool_choice="auto",
            )
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
                outcome = dispatch(tc.function.name, tc.function.arguments, self.out_dir)
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
