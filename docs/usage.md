# Guide

Everything here is runnable as-is; the `#` comments show the exact output.

## Parsing a URL

Pass a URL string to {py:class}`~action0.url.base.Url` and every part
becomes an attribute:

```python
from action0.url import Url

url = Url("https://user:pass@www.example.com:8443/docs/api.html;v=2?q=python&page=2#intro")
print(url.scheme)     # https
print(url.hostname)   # www.example.com
print(url.port)       # 8443
print(url.authority)  # www.example.com:8443
print(url.path)       # /docs/api.html
print(url.query)      # q=python&page=2
print(url.fragment)   # intro
print(url.username, url.password)  # user pass
print(url.path_params)  # v=2
```

Parsing and rendering round-trips:

```python
url_str = "https://www.example.com:8443/docs/api.html?q=python#intro"
assert Url(url_str).as_str() == url_str
```

`as_str()`, `str(url)` and `print(url)` are equivalent ways to render the
URL; `repr(url)` looks like `Url(https://…)` and
[never contains the password](#logging-and-secrets).

## Constructing a URL from parts

All parts can be given as keyword arguments:

```python
from action0.url import Url

url = Url(
    scheme="https",
    hostname="example.com",
    path="index.html",
    query={"a": "b", "foo": ["bar", "baz"]},
    port=1234,
)
print(url)
# https://example.com:1234/index.html?a=b&foo=bar&foo=baz
```

Combining a base URL string with keyword arguments replaces those parts:

```python
url = Url("https://www.example.com/old.html?a=1", path="/new.html", query={"b": "2"})
print(url)
# https://www.example.com/new.html?b=2
```

Hostname and port can also be given as one `authority` string (handy when
that is what your config file contains):

```python
print(Url(scheme="https", authority="example.com:8443"))
# https://example.com:8443
```

## Changing parts

Attributes are plain and mutable — assign and render:

```python
url = Url("https://www.example.com/shop/list.html?sort=price")
url.hostname = "api.example.com"
url.port = 8080
url.path = "/v2/items"
url.fragment = "top"
print(url)
# https://api.example.com:8080/v2/items?sort=price#top

url.authority = "other.org:9000"  # replaces hostname and port at once
print(url)
# https://other.org:9000/v2/items?sort=price#top
```

## Query parameters

`url.query` is a {py:class}`~action0.url.params.Params` instance — a
`MutableMapping` that is aware of multiple values per name. The mapping
view works with a single value per name (the last one); multi-value access
has its own methods:

```python
from action0.url import Url

query = Url("https://example.com/?b=2&a=1&a=3").query
print(query["b"])          # 2
print(query["a"])          # 3
print(query.get_all("a"))  # ['1', '3']
print(query.get("missing", "default"))  # default
print("a" in query, len(query))  # True 2
print(list(query))         # ['b', 'a']
```

### Adding, setting and removing

```python
query["b"] = 5             # replace all values (non-strings are coerced)
query.add("a", "4")        # append another value
query.add("flags", [True, False])  # bools become "true" / "false"
del query["flags"]
query.remove("a", "1")     # remove one value, keep the others
print(query)
# b=5&a=3&a=4
query.update({"a": "9"}, c="new")  # dict.update semantics
print(query)
# b=5&a=9&c=new
```

### Views and conversions

```python
query = Url("https://example.com/?q=a&q=b&page=1").query
print(query.as_dict())
# {'q': ['a', 'b'], 'page': ['1']}
print(list(query.as_single_tuples()))
# [('q', 'a'), ('q', 'b'), ('page', '1')]
print(query.singles())
# {'q': 'b', 'page': '1'}
print(dict(query.items()))  # the mapping view: one (last) value per name
# {'q': 'b', 'page': '1'}
```

### Sorting, blank values and encoding

```python
from action0.url import Params

params = Params("b=2&a=&a=1")   # blank values are kept
print(params.as_str(sort=True))  # sorted output only
# a=&a=1&b=2
params.sort()                    # sorted persistently
print(params)
# a=&a=1&b=2

print(Params({"q": "föhn wind", "page": 1}))
# q=f%C3%B6hn+wind&page=1
```

## Path parameters

The rarely seen `;key=value` parameters after the path work exactly like
the query — `url.path_params` is a `Params` with a `;` separator:

```python
url = Url("https://example.com/session/cart.html;jsessionid=abc123?step=2")
print(url.path_params.as_dict())
# {'jsessionid': ['abc123']}
url.path_params["jsessionid"] = "xyz"
print(url)
# https://example.com/session/cart.html;jsessionid=xyz?step=2
```

`Params` also works standalone:

```python
params = Params({"foo": "bar", "a": ["b", "c"]}, separator=";")
print(params)
# foo=bar;a=b;a=c
```

## Building URLs

### Appending path segments

The `/` operator returns a new `Url` with the segment appended, always
joined with exactly one slash:

```python
api = Url("https://example.com").origin() / "api" / "v2"
print(api / "users")
# https://example.com/api/v2/users
```

### Resolving links

{py:meth}`~action0.url.base.Url.join` resolves a (possibly relative)
reference against the URL, exactly like a browser resolves a link:

```python
base = Url("https://example.com/docs/guide/intro.html")
print(base.join("chapter2.html"))       # https://example.com/docs/guide/chapter2.html
print(base.join("../ref/index.html"))   # https://example.com/docs/ref/index.html
print(base.join("/search?q=x"))         # https://example.com/search?q=x
print(base.join("https://other.org/"))  # https://other.org/
```

### parent, name and suffix

```python
url = Url("https://example.com/docs/guide/intro.html?lang=en")
print(url.name, "|", url.suffix, "|", url.parent)
# intro.html | .html | https://example.com/docs/guide?lang=en
url.name = "outro.html"   # rename the last segment in place
print(url)
# https://example.com/docs/guide/outro.html?lang=en
```

### Deriving variants

{py:meth}`~action0.url.base.Url.copy` returns an independent copy,
optionally with parts replaced:

```python
url = Url("https://example.com:8443/index.html")
print(url.copy(scheme="http", port=None))
# http://example.com/index.html
print(url)  # the original is untouched
# https://example.com:8443/index.html
```

## Comparing and normalizing

Equality compares the parts; the order of query parameter *names* doesn't
matter, the order of multiple values per name does:

```python
print(Url("https://example.com?a=1&b=2") == Url("https://example.com?b=2&a=1"))
# True
print(Url("https://example.com/a?x=1").origin() == Url("https://example.com/b").origin())
# True
```

{py:meth}`~action0.url.base.Url.normalize` returns an RFC 3986-normalized
copy — lowercased scheme and hostname, default ports removed, `.` / `..`
segments resolved:

```python
print(Url("https://example.com:443/a/../b").normalize())
# https://example.com/b
```

## Encoding

Attributes hold percent-decoded ("readable") values; rendering encodes
them again. Non-ASCII hostnames become punycode:

```python
url = Url("https://example.com", path="/reports/2026 Q1.pdf", fragment="§ 2")
print(url)
# https://example.com/reports/2026%20Q1.pdf#%C2%A7%202

parsed = Url("https://example.com/a%20b?q=c%20d")
print(parsed.path, "|", parsed.query["q"])
# /a b | c d

print(Url(scheme="https", hostname="bücher.example"))
# https://xn--bcher-kva.example
```

Note that a `%2F` inside a path segment is decoded like everything else
and therefore becomes a segment separator when rendering again.

## Introspection and interop

```python
url = Url("https://user:pass@example.com:8443/p;v=1?a=1&a=2#f")
print(url.is_absolute(), Url(path="/a").is_relative())
# True True
print(url.as_dict())
# {'scheme': 'https', 'username': 'user', 'password': 'pass', 'hostname': 'example.com', 'port': 8443, 'path': '/p', 'path_params': {'v': ['1']}, 'query': {'a': ['1', '2']}, 'fragment': 'f'}
print(url.as_parse_result())
# ParseResult(scheme='https', netloc='user:pass@example.com:8443', path='/p', params='v=1', query='a=1&a=2', fragment='f')
```

(logging-and-secrets)=
## Logging and secrets

`repr()` — what debuggers, log formatters and tracebacks show — redacts
the password, while `str()` / `as_str()` keep it for real use:

```python
url = Url("https://user:secret@example.com/")
print(repr(url))
# Url(https://user:***@example.com/)
print(str(url))
# https://user:secret@example.com/
```
