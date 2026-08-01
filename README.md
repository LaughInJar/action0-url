# Action0-Url

Easy URL parsing, manipulation and unparsing wrapper around 
urllib.parse's methods (WIP).

Requires Python 3.11 or newer.

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
# https://www.example.com/path/filename.json?foo=baz&foo=123&a=b
url.hostname = "action0.com"
url.port = 8443
url.path = "/public/index.html"
url.username = "user"
url.password = "pass"
url.fragment = "fragment"
# instead of url.as_str() you can also use str(url) or just print(url)
print(url)
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
# 'https://myuser@example.com/index.html?a=b&foo=bar&foo=baz'
```

## Working with query parameters

`url.query` is a `Params` instance which supports single and multiple
values per parameter name:

```python
from action0.url import Url

url = Url("https://example.com/?b=2&a=1&a=3")
url.query.add("c", ["x", "y"])
url.query.remove("a", "1")
print(url.query.as_str())
# b=2&a=3&c=x&c=y
print(url.query.as_str(sort=True))
# a=3&b=2&c=x&c=y
```

`Params` can also be used on its own, e.g. with a `;` separator as used
for path parameters:

```python
from action0.url import Params

params = Params({"foo": "bar", "a": ["b", "c"]}, separator=";")
print(params.as_str())
# foo=bar;a=b;a=c
```

## Development

The project is managed with [uv](https://docs.astral.sh/uv/); `uv run`
creates and syncs the virtual environment automatically:

```shell
uv run pytest        # run the tests
uv run ruff check    # lint
uv run ruff format   # format
uv run mypy          # type-check (also: uv run pyright, uv run ty check)
```

## TODOs

 1. GH-Actions (run linter & test matrix for versions 3.11+)
 2. Docs
 3. Build & publish

## About action0

This is just the namespace I like to use for my personal projects.
I quite like namespaces.