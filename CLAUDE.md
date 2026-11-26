# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`action0-url` is a zero-dependency Python library for parsing, manipulating, and re-serializing URLs, wrapping `urllib.parse`. It ships the `action0.url` package (`action0` is a PEP 420 namespace package) from a `src/` layout, is built with hatchling, and uses `uv` for environment/dependency management.

## Rules

- **Never commit without asking.** Also never push, tag, or publish on your own.
- **Discuss first.** Always present the plan and the intended edits and get agreement before changing files.
- Every code change comes with: tests, docstrings, inline comments where the code isn't self-explanatory, and updated usage examples in `README.md` and the Sphinx docs (`docs/usage.md`).
- Every user-visible change gets an entry in `CHANGELOG.md` under "Unreleased" (Keep a Changelog format; behavior changes that can break callers go under "Changed").
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

uv build               # build sdist + wheel into dist/
```

`pytest` also runs the `>>>` examples in the docstrings as doctests (`--doctest-modules` over `src/`), so docstring examples must produce their shown output exactly.

## Architecture

Two modules under `src/action0/url/`:

- `base.py` — `Url`: parses a URL string with `urllib.parse.urlparse` (as it is — no default scheme, relative references round-trip), holds each part (`scheme`, `hostname`, `port`, `path`, `fragment`, `username`, `password`) as a plain mutable attribute, and reassembles them with `urlunparse` in `as_str()`. Constructor keyword arguments default to the `_UNSET` sentinel: a given argument always replaces the part of the base URL string, also with `None`/`""` (which removes it); only omitted arguments keep it. `url.query` and `url.path_params` are properties returning `Params` instances (assigning converts whatever a `Params` can be built from). Attributes hold percent-decoded values; `as_str()` re-encodes them (safe-character sets per part at the top of the module), IDNA-encodes non-ASCII hostnames and brackets IPv6 hosts (`hostname` holds them without brackets). A password may come without a username. Convenience API: `join()` (own RFC 3986 section 5.2 resolution, not `urljoin`, so it works for every scheme), the `/` operator, `copy(**overrides)`, `origin()`, `normalize()` (casing, default ports, dot segments; relative paths stay relative), the `authority` property (`hostname[:port]`, never userinfo), pathlib-style `parent`/`name`/`suffix`, `as_dict()`/`as_parse_result()`, `is_absolute()`/`is_relative()` (absolute = has a scheme), and part-wise `__eq__` (query key order ignored, per-key value order respected). Methods deriving a new Url build it with `type(self)`. `__repr__` redacts the password; `as_str()`/`str()` keep it.
- `params.py` — `Params`: an ordered multi-value mapping, internally a `list[tuple[str, str]]` of pairs so the full representation order — including values of one key interleaved with other keys — round-trips losslessly (`"a=1&b=2&a=3"` stays exactly that). It subclasses `MutableMapping`: the mapping view (`params[key]`, `get()`, `items()`, …) is single-value — the last value per key — while `get_all()`/`add()`/`as_dict()`/`as_tuples()` handle multiple values. `add()` appends at the end of the representation; `set()`/`update()` replace at the position of the key's first pair. All accepted input forms (query string, mapping, iterable of tuples, another `Params`) are normalized to the internal shape; non-string values are coerced (bools become `"true"`/`"false"`), blank values are kept (`"a="` survives round trips); `None` and bytes raise a `TypeError`. `sort()` orders in place, by name only (stable, so per-key value order and thereby equality are kept). The same class serves query parameters (`&` separator, form encoding: space ⇄ `+`) and path params (`;` separator, `form_encoding=False`: `+` is literal, space is `%20`).

Conventions:

- The version is single-sourced as `__version__` in `src/action0/url/__init__.py`; hatch extracts it with the regex in `[tool.hatch.version]`. Bump it only there.
- Releases: pushing a `vX.Y.Z` tag triggers `.github/workflows/release.yml`, which re-runs all checks, verifies the tag matches `__version__` and is on `main`, builds, tests the built wheel on every supported Python, and publishes to PyPI via trusted publishing (environment `pypi`). Never bump the version, tag, or publish on your own — releasing is the user's call.
- Tests mirror the `src/` layout under `tests/action0/url/` and are `unittest.TestCase` classes, executed via pytest.
- Ruff enforces one import per line (isort `force-single-line`), line length 99, `action0` as first-party.
- Docs live in `docs/` (Sphinx + Furo, MyST Markdown pages, autodoc for the API reference). Docstrings are Sphinx-reST (`:param:`, `:py:meth:` roles). CI builds them with `-W` on every run and deploys to GitHub Pages on pushes to `main`. Guide examples in `docs/usage.md` show exact outputs in `#` comments — keep them truthful.
