# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`action0-url` is a zero-dependency Python library for parsing, manipulating, and re-serializing URLs, wrapping `urllib.parse`. It ships the `action0.url` package (`action0` is a PEP 420 namespace package) from a `src/` layout, is built with hatchling, and uses `uv` for environment/dependency management.

## Rules

- **Never commit without asking.** Also never push, tag, or publish on your own.
- **Discuss first.** Always present the plan and the intended edits and get agreement before changing files.
- Every code change comes with: tests, docstrings, inline comments where the code isn't self-explanatory, and updated usage examples in `README.md` and the Sphinx docs (`docs/usage.md`).
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

uv run --group docs sphinx-build -W --keep-going -b html docs docs/_build/html  # build docs
```

`pytest` also runs the `>>>` examples in the docstrings as doctests (`--doctest-modules` over `src/`), so docstring examples must produce their shown output exactly.

## Architecture

Two modules under `src/action0/url/`:

- `base.py` — `Url`: parses a URL string with `urllib.parse.urlparse`, holds each part (`scheme`, `hostname`, `port`, `path`, `path_params`, `fragment`, `username`, `password`) as a plain mutable attribute, and reassembles them with `urlunparse` in `as_str()`. Constructor keyword arguments override the corresponding parts of the base URL string. `url.query` is a `Params` instance, not a string. Attributes hold percent-decoded values; `as_str()` re-encodes them (safe-character sets per part at the top of the module) and IDNA-encodes non-ASCII hostnames. Convenience API: `join()`, the `/` operator, `copy(**overrides)`, `origin()`, `normalize()` (casing, default ports, dot segments), the `authority` property, pathlib-style `parent`/`name`/`suffix`, `as_dict()`/`as_parse_result()`, `is_absolute()`/`is_relative()`, and part-wise `__eq__` (query key order ignored, per-key value order respected). `__repr__` redacts the password; `as_str()`/`str()` keep it.
- `params.py` — `Params`: an insertion-ordered multi-value mapping (internally `dict[str, list[str]]`). It subclasses `MutableMapping`: the mapping view (`params[key]`, `get()`, `items()`, …) is single-value — the last value per key — while `get_all()`/`add()`/`as_dict()`/`as_tuples()` handle multiple values. All accepted input forms (query string, mapping, iterable of tuples, another `Params`) are normalized to the internal shape; non-string values are coerced (bools become `"true"`/`"false"`), blank values are kept (`"a="` survives round trips). `sort()` orders in place. The same class serves query parameters (`&` separator) and path params (`;` separator).

Conventions:

- The version is single-sourced as `__version__` in `src/action0/url/__init__.py`; hatch extracts it with the regex in `[tool.hatch.version]`. Bump it only there.
- Tests mirror the `src/` layout under `tests/action0/url/` and are `unittest.TestCase` classes, executed via pytest.
- Ruff enforces one import per line (isort `force-single-line`), line length 99, `action0` as first-party.
- Docs live in `docs/` (Sphinx + Furo, MyST Markdown pages, autodoc for the API reference). Docstrings are Sphinx-reST (`:param:`, `:py:meth:` roles). CI builds them with `-W` on every run and deploys to GitHub Pages on pushes to `main`. Guide examples in `docs/usage.md` show exact outputs in `#` comments — keep them truthful.
