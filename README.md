# Action0-Url

[![CI](https://github.com/LaughInJar/action0-url/actions/workflows/ci.yml/badge.svg)](https://github.com/LaughInJar/action0-url/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/action0-url)](https://pypi.org/project/action0-url/)

Easy URL parsing, manipulation and unparsing wrapper around 
urllib.parse's methods.

Requires Python 3.11 or newer.

Full documentation including the API reference:
<https://laughinjar.github.io/action0-url/> — what changed between
releases is in the [changelog](CHANGELOG.md).

## Installation

```shell
pip install action0-url    # or: uv add action0-url
```

## Usage

Either with an existing url:

```python
from action0.url import Url

url = Url("https://www.example.com/path/filename.json?foo=bar")
url.query.set("foo", "baz")
print(url.as_str())
# https://www.example.com/path/filename.json?foo=baz
url.query.add("a", "b")
print(url.as_str())
# https://www.example.com/path/filename.json?foo=baz&a=b
url.query.add("foo", "123")
print(url.as_str())
# https://www.example.com/path/filename.json?foo=baz&a=b&foo=123
url.hostname = "action0.com"
url.port = 8443
url.path = "/public/index.html"
url.username = "user"
url.password = "pass"
url.fragment = "fragment"
# instead of url.as_str() you can also use str(url) or just print(url)
print(url)
# https://user:pass@action0.com:8443/public/index.html?foo=baz&a=b&foo=123#fragment
```

Or construct one (and manipulate):

```python
from action0.url import Url

url = Url(
    scheme="https",
    hostname="example.com",
    path="index.html",
    query={"a": "b", "foo": ["bar", "baz"]},
    port=1234
)
print(url)
# https://example.com:1234/index.html?a=b&foo=bar&foo=baz
url.username="myuser"
url.port=None
print(url)
# https://myuser@example.com/index.html?a=b&foo=bar&foo=baz
```

Keyword arguments replace the parts of a base URL — also with an empty
value: `None` (or `""`) removes a part, only arguments that are left out
keep it:

```python
from action0.url import Url

print(Url("https://example.com:8443/old.html?a=1#top", path="/new.html", port=None, query=None))
# https://example.com/new.html#top
```

Nothing is assumed about parts a URL string doesn't have, so relative
references round-trip (a hostname is only recognized after `//`):

```python
from action0.url import Url

url = Url("/docs/index.html?lang=en")
print(repr(url.scheme), url.hostname, url)
# '' None /docs/index.html?lang=en
print(Url("//example.com/x").hostname, "|", Url("example.com/x").path)
# example.com | example.com/x
```

## Working with query parameters

`url.query` is a `Params` instance which supports single and multiple
values per parameter name. It behaves like a dict (a `MutableMapping`)
where subscription works with a single value per name — the last one —
while `add()`, `get_all()` and friends handle multiple values:

```python
from action0.url import Url

url = Url("https://example.com/?b=2&a=1&a=3")
url.query["c"] = "4"          # replace/set values, like Params.set()
url.query.add("c", ["x", 5])  # non-strings are coerced, bools become "true"/"false"
url.query.remove("a", "1")
print(url.query["a"])         # the single (last) value; use get() for a default
# 3
print(url.query.get_all("c"))
# ['4', 'x', '5']
print("b" in url.query, len(url.query))
# True 3
print(url.query.as_str())
# b=2&a=3&c=4&c=x&c=5
print(url.query.as_str(sort=True))  # by name, the values of a name keep their order
# a=3&b=2&c=4&c=x&c=5
url.query.update({"b": 9}, token="abc")  # replaces values of existing names
print(url.query.as_str())
# b=9&a=3&c=4&c=x&c=5&token=abc
url.query.sort()  # persistent, unlike as_str(sort=True)
print(url.query.as_str())
# a=3&b=9&c=4&c=x&c=5&token=abc
url.query = {"q": "new"}  # assigning replaces all parameters (also: a string, None)
print(url)
# https://example.com/?q=new
```

Names, values (also blank ones) and their order survive parsing and
re-rendering: `Params("a=&b=1&a=2").as_str()` is `"a=&b=1&a=2"` again.
Only the spelling is normalized: a name without `=` gets one (`flag`
becomes `flag=`), empty pairs (`a=1&&b=2`) are dropped and escapes are
written in their canonical form (`%20` becomes `+`).

Values that are not strings are converted (`True` becomes `"true"`, other
objects go through `str()`); `None` and bytes raise a `TypeError`.

`Params` can also be used on its own, e.g. with a `;` separator as used
for path parameters:

```python
from action0.url import Params

params = Params({"foo": "bar", "a": ["b", "c"]}, separator=";")
print(params.as_str())
# foo=bar;a=b;a=c
```

In a query a space is written as `+` (form encoding). That doesn't apply
to path parameters, so `url.path_params` is created with
`form_encoding=False`: a `+` is a literal plus sign there and a space is
written as `%20`.

## Building and comparing URLs

```python
from action0.url import Url

# append path segments with "/" (always returns a new Url)
api = Url("https://example.com").origin() / "api" / "v2"
print(api / "users")
# https://example.com/api/v2/users

# resolve links like a browser does (RFC 3986, for every scheme)
print(Url("https://example.com/docs/intro.html").join("chapter2.html"))
# https://example.com/docs/chapter2.html
print(Url("myapp://host/a/b").join("../c"))
# myapp://host/c

# derive variants without touching the original
url = Url("https://user:secret@example.com:8443/index.html")
print(url.copy(scheme="http", port=None))
# http://user:secret@example.com/index.html

# the authority ("hostname:port") and the origin as readable shortcuts
print(url.authority, "|", url.origin())
# example.com:8443 | https://example.com:8443

# IPv6 hosts are held without their brackets and rendered with them
ipv6 = Url("http://[::1]:8080/status")
print(ipv6.hostname, "|", ipv6.authority, "|", ipv6)
# ::1 | [::1]:8080 | http://[::1]:8080/status

# equality compares the parts; query parameter order doesn't matter
print(Url("https://example.com?a=1&b=2") == Url("https://example.com?b=2&a=1"))
# True

# repr() never leaks the password (str() / as_str() keep it)
print(repr(url))
# Url(https://user:***@example.com:8443/index.html)

# a password doesn't need a username
print(Url("redis://:secret@localhost:6379/0").password)
# secret
```

`Url` and `Params` are mutable and therefore not hashable — use
`str(url)` as dictionary key or set member.

## Paths, normalization and encoding

```python
from action0.url import Url

url = Url("https://example.com/docs/guide/intro.html?lang=en")
print(url.name, "|", url.suffix, "|", url.parent)
# intro.html | .html | https://example.com/docs/guide?lang=en
url.name = "outro.html"
print(url)
# https://example.com/docs/guide/outro.html?lang=en

# RFC 3986 style normalization: casing, default ports, dot segments
print(Url("https://example.com:443/a/./b/../c").normalize())
# https://example.com/a/c
print(Url("a/../../b").normalize())  # relative paths stay relative
# ../b

# parts are stored decoded, rendering percent-encodes them again ...
url = Url("https://example.com/a%20b", fragment="§ 2")
print(url.path, "|", url)
# /a b | https://example.com/a%20b#%C2%A7%202

# ... and non-ASCII hostnames become punycode
print(Url(scheme="https", hostname="bücher.example"))
# https://xn--bcher-kva.example

# absolute means "has a scheme" (RFC 3986)
print(url.is_absolute(), Url("file:///etc/hosts").is_absolute(), Url("//example.com/a").is_relative())
# True True True
```

Decoding has two lossy corners: a `%2F` inside a path segment becomes a
plain `/`, and escapes that are not valid UTF-8 are replaced. Hostnames
are IDNA-encoded with Python's standard library (IDNA 2003), which maps
`straße.de` to `strasse.de` where current browsers keep the `ß` — assign
the punycode form as hostname if that matters.

For debugging and stdlib interoperability there are also `url.as_dict()`
(all parts as a plain dictionary) and `url.as_parse_result()` (the
`urllib.parse.ParseResult` named tuple).

## Development

The project is managed with [uv](https://docs.astral.sh/uv/); `uv run`
creates and syncs the virtual environment automatically:

```shell
uv run pytest        # run the tests (incl. the docstring examples as doctests)
uv run ruff check    # lint
uv run ruff format   # format
uv run mypy          # type-check (also: uv run pyright, uv run ty check)

# build the docs (Sphinx; deployed to GitHub Pages on push to main)
uv run --group docs sphinx-build -W --keep-going -b html docs docs/_build/html
```

User-visible changes are recorded in [CHANGELOG.md](CHANGELOG.md) under
"Unreleased".

### Releasing

The version lives only in `src/action0/url/__init__.py` (`__version__`).
To release: bump it, turn the "Unreleased" section of the changelog into
the new version, merge to `main`, then tag the release commit and push
the tag — the release workflow re-runs all checks, verifies that the tag
matches `__version__` and is on `main`, builds sdist + wheel, tests the
built wheel and publishes to PyPI via trusted publishing:

```shell
git tag v0.1.0
git push origin v0.1.0
```

## AI-assisted development

In the spirit of transparency: most of this project's code, tests and
documentation are written by [Claude Code](https://claude.com/claude-code),
Anthropic's coding agent — under human direction and review. The designs
are specified, discussed and iterated by a human, and every change is
reviewed before it lands in `main` or in a release. AI-authored commits
carry a `Co-Authored-By: Claude ...` trailer.

## About action0

This is just the namespace I like to use for my personal projects.
I quite like namespaces.