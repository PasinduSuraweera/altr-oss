# altr

> Open source doc / excel / ppt skills for LLMs.

[![CI](https://github.com/PasinduSuraweera/altr-oss/actions/workflows/ci.yml/badge.svg)](https://github.com/PasinduSuraweera/altr-oss/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

Claude has document skills. ChatGPT has them. **Open-weight models don't.**
Point `gpt-oss-120b` on Groq (or any model behind an OpenAI-compatible API) at
altr and it gains three tools it can call to produce real files:

| Tool                  | Output  | Good for                                   |
| --------------------- | ------- | ------------------------------------------ |
| `create_document`     | `.docx` | reports, guides, letters, meeting notes    |
| `create_spreadsheet`  | `.xlsx` | budgets, trackers, datasets - with formulas |
| `create_presentation` | `.pptx` | pitch decks, talks - with speaker notes    |

The model sends structured JSON through standard tool calling; altr
validates it (Pydantic) and renders it (`python-docx`, `openpyxl`,
`python-pptx`). Renderer errors are fed back to the model so it can correct
itself. No code execution, no sandboxes - the model can only emit document
content.

## Install

```sh
pip install altr
```

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

## What the model can express

- **Documents**: headings (9 levels), paragraphs with inline
  **bold**/*italic*/`code`, bullet & numbered lists, tables with bold headers,
  images with captions, whole markdown blocks, page breaks.
- **Spreadsheets**: multiple worksheets, bold header rows, column widths,
  frozen header rows, live Excel formulas (`=SUM(B2:B10)`), and bar/line/pie
  charts built from the sheet's data.
- **Presentations**: title slides, section dividers, bulleted slides with
  indent levels, chart slides, full-width image slides, speaker notes.

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

## PDF export

Pass `--pdf` to `make` or `render` to also export each created file as PDF.
Requires LibreOffice (`soffice`) on your PATH. From Python:

```python
from altr import to_pdf
to_pdf("output/report.docx")
```

## Roadmap

- [ ] Recipe/preset library of reusable prompts
- [ ] Chart styling options (colors, axis titles, legends)
- [ ] Nested markdown lists and blockquotes
- [ ] Watermarks and headers/footers

## Contributing

PRs welcome - see [CONTRIBUTING.md](CONTRIBUTING.md). Good first issues:
roadmap items above, or new block types for the document schema.

## License

[MIT](LICENSE) © Pasindu Suraweera
