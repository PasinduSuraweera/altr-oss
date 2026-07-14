# Contributing to altr

Thanks for your interest! Bug reports, new block types, renderer improvements,
and docs are all welcome.

## Development setup

You need Python 3.10+.

```sh
git clone https://github.com/PasinduSuraweera/altr-oss
cd altr-oss
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Try the offline renderer without an API key:

```sh
altr render presentation examples/pitch-deck.json
```

## Guidelines

- Keep PRs focused: one change per PR.
- Every schema or renderer change needs a test that re-opens the generated
  file and asserts on its contents (see `tests/test_renderers.py`).
- Colors and other visual constants live in `src/altr/theme.py` - renderers
  must not hard-code their own. The chart palette's slot order is a
  colorblind-safety property; never reorder or extend it casually.
- For visual changes, open the generated files (or export them to
  PDF/PNG) and look at them - structural asserts don't catch layout bugs.
- Loosen schemas toward what models actually emit (accept both shapes,
  normalize in a validator) rather than demanding stricter output from the
  model; small local models won't comply.
- Field descriptions in `schemas.py` are model-facing prompt text - keep them
  short, concrete, and example-driven.
- `dispatch()` must never raise on bad model input; return
  `{"ok": False, "error": ...}` so the model can self-correct.

## Releasing to PyPI (maintainers)

Releases publish automatically via PyPI trusted publishing - no API tokens.
One-time setup, done once by the repo owner:

1. On pypi.org: Account -> Publishing -> add a "pending publisher" for project
   `altr-oss` (PyPI rejects `altr` as too similar to an existing project),
   owner `PasinduSuraweera`, repo `altr-oss`, workflow `release.yml`,
   environment `pypi`.
2. On GitHub: repo Settings -> Environments -> create an environment named
   `pypi`.

Then to ship a release: bump `version` in `pyproject.toml`, tag (e.g.
`v0.2.0`), and publish a GitHub release - the workflow builds and uploads to
PyPI.

## Proposing features

Open an issue first for anything beyond a small fix (new document features,
template support, new output formats) - a short design discussion up front
saves rework.
