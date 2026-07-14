import json

from altr.tools import dispatch, get_tools


def test_get_tools_shape():
    tools = get_tools()
    names = {t["function"]["name"] for t in tools}
    assert names == {
        "create_document",
        "create_spreadsheet",
        "create_presentation",
        "read_office_file",
        "edit_document",
        "edit_spreadsheet",
        "edit_presentation",
    }
    for tool in tools:
        assert tool["type"] == "function"
        assert tool["function"]["description"]
        assert tool["function"]["parameters"]["type"] == "object"


def test_dispatch_creates_file(tmp_path):
    args = json.dumps(
        {
            "filename": "notes.docx",
            "blocks": [{"type": "paragraph", "text": "hello"}],
        }
    )
    result = dispatch("create_document", args, tmp_path)
    assert result["ok"] is True
    assert (tmp_path / "notes.docx").exists()


def test_dispatch_unknown_tool(tmp_path):
    result = dispatch("create_pdf", "{}", tmp_path)
    assert result["ok"] is False
    assert "unknown tool" in result["error"]


def test_dispatch_bad_json(tmp_path):
    result = dispatch("create_document", "{not json", tmp_path)
    assert result["ok"] is False
    assert "not valid JSON" in result["error"]


def test_dispatch_invalid_arguments(tmp_path):
    result = dispatch("create_document", json.dumps({"filename": "x.docx", "blocks": []}), tmp_path)
    assert result["ok"] is False
    assert "invalid arguments" in result["error"]
