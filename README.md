# altr

> Open source doc / excel / ppt skills for LLMs.

[![CI](https://github.com/PasinduSuraweera/altr-oss/actions/workflows/ci.yml/badge.svg)](https://github.com/PasinduSuraweera/altr-oss/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

Claude has document skills. ChatGPT has them. **Open-weight models don't.**
Point `gpt-oss-120b` on Groq (or any model behind an OpenAI-compatible API) at
altr and it gains tools it can call to produce - and edit - real files:

| Tool                  | Output  | Good for                                                  |
| --------------------- | ------- | --------------------------------------------------------- |
| `create_document`     | `.docx` | reports, guides, letters, meeting notes                   |
| `create_spreadsheet`  | `.xlsx` | budgets, trackers, datasets - with formulas               |
| `create_presentation` | `.pptx` | pitch decks, talks - with speaker notes                   |
| `read_office_file`    | -       | inspecting an existing file before editing                |
| `edit_document`       | `.docx` | find/replace, rewrite/delete paragraphs, append sections  |
| `edit_spreadsheet`    | `.xlsx` | set cells and formulas, append rows, add sheets           |
| `edit_presentation`   | `.pptx` | retitle slides, find/replace, append slides               |

The model sends structured JSON through standard tool calling; altr
validates it (Pydantic) and renders it (`python-docx`, `openpyxl`,
`python-pptx`). Validation and renderer errors are fed back to the model so
it can correct itself - including server-side tool-call rejections from
strict endpoints like Groq, which are turned into feedback and retried
instead of crashing the run. No code execution, no sandboxes - the model can
only emit document content.

Output ships with a clean default theme - accent-colored headings, styled
tables and header rows, and charts drawn in a colorblind-safe palette - so
files look designed out of the box. Or bring your own brand template (below).

## Install

```sh
pip install altr-oss
```

The PyPI distribution is `altr-oss`; the import and the CLI command are both
plain `altr`.

Or straight from the repo:

```sh
pip install git+https://github.com/PasinduSuraweera/altr-oss
```

## Quickstart (CLI)

```sh
export GROQ_API_KEY=gsk_...

altr make "Create a 6-slide pitch deck for a solar-powered drone startup"
altr make "Make a 12-month SaaS budget spreadsheet with formula totals"
altr make "Write a 2-page onboarding doc for new backend engineers"
```

Files land in `./output`. Works with any OpenAI-compatible server:

```sh
# Groq (default)
altr make "..." --model openai/gpt-oss-120b

# Ollama, fully local
altr make "..." --base-url http://localhost:11434/v1 --model llama3.3 --api-key ollama

# vLLM / LM Studio / anything else that speaks chat completions
altr make "..." --base-url http://localhost:8000/v1 --model my-model
```

Generation runs at `--temperature 0.3` by default - tool arguments are
structured output, and sampling cooler makes small models dramatically more
reliable at producing complete, schema-correct documents.

Transient rate limits (429) are waited out and retried automatically. For
long documents on Groq's free tier, add `--max-completion-tokens 2500` -
Groq counts the expected output against your per-minute token budget up
front, so uncapped long-document requests are rejected as too large.

By default (`--tools auto`) the edit tools are only sent when your prompt
looks like an edit, to keep requests small on tight free tiers. On a paid
tier, pass `--tools all` so the model always sees every tool regardless of
how you phrase the request.

Editing works from the same command - name the file in your prompt:

```sh
altr make "In output/report.docx, rename Project Falcon to Condor everywhere \
           and append a Risks section with two bullets"
```

The model reads the file first (`read_office_file` gives it paragraph and
slide indexes), then applies validated edit operations in place. Edits are
restricted to files under the working and output directories. One caveat:
editing an `.xlsx` drops its existing charts (an openpyxl round-trip
limitation) - altr warns the model so it can recreate them.

Render a JSON spec directly, no model involved (great for testing):

```sh
altr render presentation examples/pitch-deck.json
altr render spreadsheet examples/budget.json
altr render document examples/onboarding-doc.json
```

## Use it as a library

```python
from altr import OfficeAgent

agent = OfficeAgent(model="openai/gpt-oss-120b", out_dir="out")
result = agent.run("Create a quarterly report with a KPI table")
print(result.files)   # [PosixPath('out/quarterly-report.docx')]
print(result.reply)   # the model's final message
```

## Use it as a skill in your own agent

Already have an agent loop? Take just the tools:

```python
from altr import SYSTEM_PROMPT, get_tools, dispatch

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "system", "content": SYSTEM_PROMPT}, ...],
    tools=get_tools(),          # OpenAI-format tool definitions
)

for call in response.choices[0].message.tool_calls:
    result = dispatch(call.function.name, call.function.arguments, out_dir="out")
    # {"ok": True, "file": "out/report.docx"}  - or {"ok": False, "error": ...}
```

`dispatch` never raises on bad model output - validation and render errors come
back as data you can hand to the model for self-correction.

## Use it as an MCP server

Give Claude Desktop, Claude Code, Cursor, or any MCP client the same document
skills:

```sh
pip install "altr-oss[mcp]"
```

Claude Code:

```sh
claude mcp add altr -- altr mcp --out ~/Documents/altr
```

Claude Desktop / other clients (JSON config):

```json
{
  "mcpServers": {
    "altr": {
      "command": "altr",
      "args": ["mcp", "--out", "/path/for/generated/files"]
    }
  }
}
```

The server speaks stdio and exposes all seven tools; `--docx-template` and
`--pptx-template` work here too.

## What the model can express

- **Documents**: headings (9 levels), paragraphs with inline
  **bold**/*italic*/`code`, bullet & numbered lists, styled tables with banded
  rows, images with captions, whole markdown blocks, page breaks.
- **Spreadsheets**: multiple worksheets, styled header rows, fitted column
  widths, frozen headers, live Excel formulas (`=SUM(B2:B10)`), a detected
  `Total` row set in bold, and bar/line/pie charts built from the sheet's
  data - if the model doesn't say which columns to plot, altr infers the
  numeric ones (and leaves the total row out of the chart).
- **Presentations**: title slides, section dividers, bulleted slides with
  indent levels (plain strings work too), chart slides, full-width image
  slides, speaker notes. Common model slips are repaired: chart data on a
  mislabeled slide still becomes a chart slide.

Filenames from the model are sanitized to their base name, so output can never
escape the output directory. Image paths must point at existing local files -
the system prompt tells the model to only use files you mention.

## Brand templates

Start every generated file from your own template so fonts, colors, and slide
masters match your brand:

```sh
altr make "..." --docx-template brand.docx --pptx-template brand.pptx
altr render presentation deck.json --template brand.pptx
```

Custom `.pptx` templates must keep the stock layout order (0 title,
1 title+content, 2 section header, 5 title only).

Passing a template switches the built-in theme off entirely - your fonts,
colors, and masters are used untouched.

## PDF export

Pass `--pdf` to `make` or `render` to also export each created file as PDF.
Requires LibreOffice (`soffice`) on your PATH. From Python:

```python
from altr import to_pdf
to_pdf("output/report.docx")
```

## Roadmap

- [ ] Model reliability benchmark (which local models handle document tasks?)
- [ ] More edit operations (insert at position, edit tables, restyle)
- [ ] Preserve charts when editing spreadsheets
- [ ] Recipe/preset library of reusable prompts
- [ ] Configurable theme (swap the accent color and chart palette)
- [ ] Chart axis titles and number formats
- [ ] Nested markdown lists and blockquotes
- [ ] Watermarks and headers/footers

## Contributing

PRs welcome - see [CONTRIBUTING.md](CONTRIBUTING.md). Good first issues:
roadmap items above, or new block types for the document schema.

## License

[MIT](LICENSE) © Pasindu Suraweera
