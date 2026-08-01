# action0-url

Easy URL parsing, manipulation and unparsing — a friendly, typed wrapper
around {py:mod}`urllib.parse`.

```shell
pip install action0-url    # or: uv add action0-url
```

```python
from action0.url import Url

url = Url("https://www.example.com/path/filename.json?foo=bar")
url.query.set("foo", "baz")
url.hostname = "api.example.com"
print(url)
# https://api.example.com/path/filename.json?foo=baz
```

**Highlights**

- Every URL part (`scheme`, `hostname`, `port`, `path`, `fragment`, …) is a
  plain mutable attribute — parse once, change what you need, render again.
- Query and path parameters are dict-like, multi-value aware
  {py:class}`~action0.url.params.Params` mappings.
- Convenience methods for everyday work: {py:meth}`~action0.url.base.Url.join`,
  the `/` operator, {py:meth}`~action0.url.base.Url.copy`,
  {py:meth}`~action0.url.base.Url.origin`,
  {py:meth}`~action0.url.base.Url.normalize`, pathlib-style `parent` /
  `name` / `suffix`.
- Parts are stored percent-decoded and re-encoded on rendering; non-ASCII
  hostnames become punycode.
- Fully typed (checked with mypy strict, pyright and ty), zero runtime
  dependencies, Python 3.11+.

The `action0` namespace is simply the one the author likes to use for
personal projects.

```{toctree}
:maxdepth: 2

usage
api
```
