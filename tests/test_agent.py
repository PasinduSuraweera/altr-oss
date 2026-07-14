"""Agent-loop tests against a fake OpenAI-compatible client (no network)."""

import copy
import json
from types import SimpleNamespace

from officesmith.agent import OfficeAgent


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    """Replays scripted responses and records the requests it receives."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        # Deep-copy: the agent mutates its messages list between rounds.
        self.requests.append(copy.deepcopy(kwargs))
        return self._responses.pop(0)


def test_agent_executes_tool_calls_then_returns_reply(tmp_path):
    doc_args = {"filename": "memo.docx", "blocks": [{"type": "paragraph", "text": "hi"}]}
    client = FakeClient(
        [
            _response(tool_calls=[_tool_call("call_1", "create_document", doc_args)]),
            _response(content="Created your memo."),
        ]
    )
    agent = OfficeAgent(client=client, out_dir=tmp_path)

    result = agent.run("write me a memo")

    assert [p.name for p in result.files] == ["memo.docx"]
    assert (tmp_path / "memo.docx").exists()
    assert result.reply == "Created your memo."

    # Second request must include the assistant tool_calls turn and the tool result.
    second = client.requests[1]["messages"]
    assert second[-2]["role"] == "assistant"
    assert second[-2]["tool_calls"][0]["function"]["name"] == "create_document"
    tool_msg = second[-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_1"
    assert json.loads(tool_msg["content"])["ok"] is True


def test_agent_feeds_errors_back_to_model(tmp_path):
    bad_args = {"filename": "x.docx", "blocks": []}  # fails validation
    good_args = {"filename": "x.docx", "blocks": [{"type": "paragraph", "text": "ok"}]}
    client = FakeClient(
        [
            _response(tool_calls=[_tool_call("call_1", "create_document", bad_args)]),
            _response(tool_calls=[_tool_call("call_2", "create_document", good_args)]),
            _response(content="done"),
        ]
    )
    agent = OfficeAgent(client=client, out_dir=tmp_path)

    result = agent.run("make a doc")

    error_msg = json.loads(client.requests[1]["messages"][-1]["content"])
    assert error_msg["ok"] is False
    assert len(result.files) == 1


def test_agent_stops_at_max_rounds(tmp_path):
    args = {"filename": "loop.docx", "blocks": [{"type": "paragraph", "text": "again"}]}
    responses = [
        _response(tool_calls=[_tool_call(f"call_{i}", "create_document", args)])
        for i in range(5)
    ]
    client = FakeClient(responses)
    agent = OfficeAgent(client=client, out_dir=tmp_path, max_rounds=3)

    result = agent.run("loop forever")

    assert len(client.requests) == 3
    assert "max tool-call rounds" in result.reply
