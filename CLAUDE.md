# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`action0-url` is a zero-dependency Python library for parsing, manipulating, and re-serializing URLs, wrapping `urllib.parse`. It ships the `action0.url` package (`action0` is a PEP 420 namespace package) from a `src/` layout, is built with hatchling, and uses `uv` for environment/dependency management.

## Rules

- **Never commit without asking.** Also never push, tag, or publish on your own.
- **Discuss first.** Always present the plan and the intended edits and get agreement before changing files.
- Every code change comes with: tests, docstrings, inline comments where the code isn't self-explanatory, and updated usage examples in `README.md`.
- Before considering work done, run ruff, mypy, and pytest (commands below) and fix what they report.
- Supported Python versions: 3.11 up to the latest release. Don't use syntax or stdlib features introduced after 3.11, and don't rely on behavior removed in newer versions.

## Commands

`uv run` syncs the environment automatically (the dev dependency group is installed by default), so no separate install step is needed.

```sh
uv run pytest                                   # all tests
uv run pytest tests/action0/url/test_params.py  # one file
uv run pytest tests/action0/url/test_params.py::ParamsInitTestCase::test_separator_init  # one test

uv run ruff check      # lint (add --fix to autofix)
uv run ruff format     # format
uv run mypy            # type-check (strict; files are configured in pyproject.toml)
uv run pyright         # type-check
uv run ty check        # type-check
```

## Architecture

Two modules under `src/action0/url/`:

- `base.py` — `Url`: parses a URL string with `urllib.parse.urlparse`, holds each part (`scheme`, `hostname`, `port`, `path`, `path_params`, `fragment`, `username`, `password`) as a plain mutable attribute, and reassembles them with `urlunparse` in `as_str()`. Constructor keyword arguments override the corresponding parts of the base URL string. `url.query` is a `Params` instance, not a string.
- `params.py` — `Params`: an insertion-ordered multi-value mapping (internally `dict[str, list[str]]`). All accepted input forms (query string, dict, iterable of tuples; values as a single string or an iterable of strings) are normalized to that internal shape. The same class serves query parameters (`&` separator) and path params (`;` separator).

Conventions:

- The version is single-sourced as `__version__` in `src/action0/url/__init__.py`; hatch extracts it with the regex in `[tool.hatch.version]`. Bump it only there.
- Tests mirror the `src/` layout under `tests/action0/url/` and are `unittest.TestCase` classes, executed via pytest.
- Ruff enforces one import per line (isort `force-single-line`), line length 99, `action0` as first-party.
