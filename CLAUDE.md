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

- `base.py` — `Url`: splits a URL string with `urllib.parse.urlsplit` (as it is — no default scheme, relative references round-trip) and assembles it itself in `as_str()` (RFC 3986 section 5.3; no `urlunparse`, whose output for host-less URLs varies between Python versions). Path params are split off the last segment by the module itself, for the schemes in `_PATH_PARAMS_SCHEMES` only. The string parts (`path`, `fragment`, `username`, `password`) are stored **percent-encoded** in `__slots__` (`_path`, …), which makes an unmodified URL render exactly as written; the public attributes are properties that show and take the *decoded* values, `raw_path` / `raw_fragment` expose the encoded form. Every property setter validates (`_check_scheme`, `_check_hostname`, `_check_port`: `ValueError` for impossible values, `TypeError` for wrong types; `None` removes a part), so a Url can always be rendered — keep it that way when adding parts. `scheme` and `hostname` are stored lowercase, an IPv6 hostname without brackets. Constructor and `copy()` keyword arguments default to the `_UNSET` sentinel: a given argument always replaces the part, also with `None`/`""`. `url.query` and `url.path_params` are properties returning `Params` instances (assigning copies whatever a `Params` can be built from); the query is form-encoded only for the schemes in `_FORM_ENCODED_SCHEMES`. Rendering IDNA-encodes non-ASCII hostnames, brackets IPv6 hosts and prefixes paths that would be read as a scheme (`./a:b`) or a host (`/.//x`). Convenience API: `join()` (own RFC 3986 section 5.2 resolution on the raw paths, works for every scheme, reads a string reference in the context of the base scheme), the `/` operator, `copy()` (clones the slots without calling `__init__`, so it works for subclasses with their own constructor — everything deriving a new Url goes through it), `origin()`, `normalize()`, the `authority` property (`hostname[:port]`, never userinfo), pathlib-style `parent`/`name`/`suffix`, `as_dict()`/`as_parse_result()`, `is_absolute()`/`is_relative()` (absolute = has a scheme), and `__eq__` on the canonical encoded form (`%7E` equals `~`, `%2F` does not equal `/`; query key order ignored, per-key value order respected). `__repr__` redacts the password and never raises; `as_str()`/`str()` keep it; error messages for unparsable URLs are redacted too (`_redact_userinfo`).
- `params.py` — `Params`: an ordered multi-value mapping, internally a `list[tuple[str, str]]` of pairs so the full representation order — including values of one key interleaved with other keys — round-trips losslessly (`"a=1&b=2&a=3"` stays exactly that). Parameters parsed from a string also keep that string (`_raw`) and `as_str()` returns it until the pairs are modified; every mutation has to go through `_changed()`, which drops it together with the cached single-value index (`_singles()`, what makes the mapping methods O(1)). It subclasses `MutableMapping`: the mapping view (`params[key]`, `get()`, `items()`, …) is single-value — the last value per key — while `get_all()`/`add()`/`as_dict()`/`as_tuples()` handle multiple values. `add()` appends at the end of the representation; `set()`/`update()` replace at the position of the key's first pair (`update()` is all-or-nothing and linear). All accepted input forms (query string, mapping, iterable of tuples, another `Params`) are normalized to the internal shape. Input is strict: names must be `str`, values `str`/`int`/`float`/`bool` (bools become `"true"`/`"false"`) or an iterable of those — everything else raises a `TypeError`, matching the type hints. Blank values are kept (`"a="` survives round trips). `sort()` orders in place, by name only (stable, so per-key value order and thereby equality are kept). The same class serves query parameters (`&` separator, form encoding: space ⇄ `+`) and path params or non-web queries (`form_encoding=False`: `+` is literal, space is `%20`).

Conventions:

- The version is single-sourced as `__version__` in `src/action0/url/__init__.py`; hatch extracts it with the regex in `[tool.hatch.version]`. Bump it only there.
- Releases: pushing a `vX.Y.Z` tag triggers `.github/workflows/release.yml`, which re-runs all checks, verifies the tag matches `__version__`, is on `main` and has a section in `CHANGELOG.md`, builds, tests the built wheel on every supported Python, and publishes to PyPI via trusted publishing (environment `pypi`). Never bump the version, tag, or publish on your own — releasing is the user's call.
- Tests mirror the `src/` layout under `tests/action0/url/` and are `unittest.TestCase` classes, executed via pytest.
- GitHub Actions are pinned to commit SHAs with the release in a trailing comment; Dependabot (`.github/dependabot.yml`) updates them.
- Ruff enforces one import per line (isort `force-single-line`), line length 99, `action0` as first-party.
- Docs live in `docs/` (Sphinx + Furo, MyST Markdown pages, autodoc for the API reference). Docstrings are Sphinx-reST (`:param:`, `:py:meth:` roles). CI builds them with `-W` on every run and deploys to GitHub Pages on pushes to `main`; the site is labelled as describing `main` (not a release), so docs, README and code change together. Guide examples in `docs/usage.md` show exact outputs in `#` comments — keep them truthful.
