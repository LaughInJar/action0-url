# Guide

The examples build on each other: run them top to bottom in one session
(imports are shown once, where a name is first used). The `#` comments
show the exact output.

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

All parts and their order survive; what can change is the *spelling* of an
equivalent URL: the hostname is lowercased, percent escapes are written in
their canonical form and a query parameter without `=` gets one (`?flag`
becomes `?flag=`). The two lossy corners are listed under
[Encoding](#encoding).

An unparsable URL — a non-numeric or out-of-range port, a broken IPv6
address — raises a `ValueError`.

### Relative URLs

Nothing is assumed about parts the string doesn't have: no scheme in, no
scheme out. Relative references therefore round-trip as well:

```python
url = Url("/docs/index.html?lang=en")
print(repr(url.scheme), url.hostname)  # '' None
print(url)                             # /docs/index.html?lang=en
```

As in {py:func}`urllib.parse.urlparse`, a hostname is only recognized
after `//` — without it the text is a relative path:

```python
print(Url("//example.com/x").hostname)  # example.com
print(Url("example.com/x").hostname)    # None
print(Url("example.com/x").path)        # example.com/x
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

Every argument that is given replaces its part — also with an empty
value: `None` (or `""`, or an empty mapping) removes the part, only
arguments that are left out keep the one of the base URL:

```python
print(Url("https://user:pw@www.example.com:8443/a?b=1#c", password=None, port=None, query=None))
# https://user@www.example.com/a#c
```

Values are given unencoded and without their delimiter: no leading `?`
for the query, no `#` for the fragment.

Hostname and port can also be given as one `authority` string (handy when
that is what your config file contains):

```python
print(Url(scheme="https", authority="example.com:8443"))
# https://example.com:8443
```

The authority is `hostname[:port]` only — unlike urllib's `netloc` it has
no userinfo (that goes in `username` / `password`, a string containing an
`@` raises a `ValueError`). Given together with a base URL it replaces
hostname *and* port:

```python
print(Url("https://example.com:8443/x", authority="other.org"))
# https://other.org/x
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

`url.query` and `url.path_params` can be assigned as well — anything a
`Params` can be built from, or `None` to remove them all:

```python
url.query = "sort=name&page=2"
print(url)
# https://other.org:9000/v2/items?sort=name&page=2#top
url.query = None
print(url)
# https://other.org:9000/v2/items#top
```

### IPv6 hosts

`hostname` holds an IPv6 address without the brackets it needs inside a
URL; rendering and `authority` add them:

```python
url = Url("http://[::1]:8080/status")
print(url.hostname)   # ::1
print(url.authority)  # [::1]:8080
print(url)            # http://[::1]:8080/status
print(Url(scheme="http", hostname="2001:db8::1", port=8080))
# http://[2001:db8::1]:8080
```

### Credentials

A username can come without a password and a password without a username
(as in Redis URLs):

```python
url = Url("redis://:secret@localhost:6379/0")
print(url.username, url.password)  # None secret
print(url)                         # redis://:secret@localhost:6379/0
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

Values that are not strings are converted: bools become `"true"` /
`"false"`, numbers and any other object go through `str()`. `None` and
bytes have no obvious string form and raise a `TypeError`:

```python
import datetime

query["since"] = datetime.date(2026, 1, 31)
print(query["since"])  # 2026-01-31
try:
    query["broken"] = None
except TypeError as error:
    print(error)
# parameter values must be str, int, float or bool (or an iterable of those), not NoneType
del query["since"]
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

params = Params("b=2&a=9&a=&a=1")  # blank values are kept
print(params.as_str(sort=True))    # sorted output only
# a=9&a=&a=1&b=2
params.sort()                      # sorted persistently
print(params)
# a=9&a=&a=1&b=2

print(Params({"q": "föhn wind", "page": 1}))
# q=f%C3%B6hn+wind&page=1
```

Sorting is by name only: the values of one name keep their order (it can
be meaningful, and it is what [equality](#comparing-and-normalizing)
compares), so a sorted `Params` still equals the unsorted one.

When parsing a string, pass the bare query without the leading `?`. The
spelling is normalized on the way through:

```python
print(Params("flag&a=1&&b=x%20y"))  # "=" added, empty pair dropped, "%20" -> "+"
# flag=&a=1&b=x+y
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

One difference: being part of the path they are not form-encoded. A `+`
is a literal plus sign (in a query it stands for a space) and a space is
written as `%20`:

```python
url = Url("https://example.com/calc;expr=1+2?q=1+2")
print(url.path_params["expr"], "|", url.query["q"])
# 1+2 | 1 2
url.path_params["expr"] = "a b"
print(url)
# https://example.com/calc;expr=a%20b?q=1+2
```

Only the last path segment can have parameters (and only for the schemes
urllib knows them for, e.g. `http`, `https`, `ftp`); a `;` anywhere else
is simply part of the path.

`Params` also works standalone:

```python
params = Params({"foo": "bar", "a": ["b", "c"]}, separator=";")
print(params)
# foo=bar;a=b;a=c
print(Params({"q": "a b"}), "|", Params({"q": "a b"}, form_encoding=False))
# q=a+b | q=a%20b
```

## Building URLs

### Appending path segments

The `/` operator returns a new `Url` with the segment appended, always
joined with exactly one slash:

```python
api = Url("https://example.com").origin() / "api" / "v2"
print(api / "users")
# https://example.com/api/v2/users
print(Url() / "api" / "v2")  # a relative URL stays relative
# api/v2
```

### Resolving links

{py:meth}`~action0.url.base.Url.join` resolves a (possibly relative)
reference against the URL, exactly like a browser resolves a link
(RFC 3986, section 5.2):

```python
base = Url("https://example.com/docs/guide/intro.html")
print(base.join("chapter2.html"))       # https://example.com/docs/guide/chapter2.html
print(base.join("../ref/index.html"))   # https://example.com/docs/ref/index.html
print(base.join("/search?q=x"))         # https://example.com/search?q=x
print(base.join("https://other.org/"))  # https://other.org/
```

Unlike {py:func}`urllib.parse.urljoin` this works for every scheme, and
for relative base URLs:

```python
print(Url("myapp://host/a/b").join("../c?d=1"))  # myapp://host/c?d=1
print(Url("docs/guide/intro.html").join("../ref.html"))  # docs/ref.html
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

A trailing slash is significant in a URL: `/docs/guide/` is a directory
without a file name, so its `name` is `""`. `parent` follows pathlib and
ignores it — the parent of `/docs/guide/` is `/docs`. `suffix` follows
pathlib too (`.gz` for `archive.tar.gz`, none for `.hidden`).

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

`copy()`, `origin()`, `join()`, `/`, `parent` and `normalize()` return an
instance of the same class, so subclasses of `Url` stay what they are.

(comparing-and-normalizing)=
## Comparing and normalizing

Equality compares the parts; the order of query parameter *names* doesn't
matter, the order of multiple values per name does:

```python
print(Url("https://example.com?a=1&b=2") == Url("https://example.com?b=2&a=1"))
# True
print(Url("https://example.com/a?x=1").origin() == Url("https://example.com/b").origin())
# True
```

Being mutable and compared by their parts, `Url` and `Params` are not
hashable — use `str(url)` as dictionary key or set member.

{py:meth}`~action0.url.base.Url.normalize` returns an RFC 3986-normalized
copy — lowercased scheme and hostname, default ports removed, `.` / `..`
segments resolved and, if there is a hostname, the path made absolute:

```python
print(Url("https://example.com:443/a/../b").normalize())
# https://example.com/b
print(Url(scheme="HTTPS", hostname="Example.COM", path="index.html").normalize())
# https://example.com/index.html
```

The path of a relative URL stays relative; `..` segments with nothing to
resolve them against are kept:

```python
print(Url("a/./b/../c").normalize())  # a/c
print(Url("a/../../b").normalize())   # ../b
```

(encoding)=
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

Decoding has two lossy corners:

- a `%2F` inside a path segment is decoded like everything else and
  therefore becomes a segment separator when rendering again;
- percent escapes that are not valid UTF-8 (`%FF`) are replaced by the
  Unicode replacement character.

Hostnames are decoded and encoded too. Characters that cannot be part of a
hostname are percent-encoded, so an assigned hostname can never spill over
into the path or query:

```python
print(Url(scheme="https", hostname="example.com/admin?x"))
# https://example.com%2Fadmin%3Fx
```

The IDNA encoding is the one of Python's standard library (IDNA 2003). It
differs from current browsers (IDNA 2008 / UTS 46) for a few characters —
`straße.de` becomes `strasse.de` instead of `xn--strae-oqa.de`. If that
matters, assign the punycode form as hostname; ASCII hostnames are never
touched.

## Introspection and interop

```python
url = Url("https://user:pass@example.com:8443/p;v=1?a=1&a=2#f")
print(url.is_absolute(), Url(path="/a").is_relative())
# True True
print(Url("file:///etc/hosts").is_absolute(), Url("//example.com/a").is_absolute())
# True False
print(url.as_dict())
# {'scheme': 'https', 'username': 'user', 'password': 'pass', 'hostname': 'example.com', 'port': 8443, 'path': '/p', 'path_params': {'v': ['1']}, 'query': {'a': ['1', '2']}, 'fragment': 'f'}
print(url.as_parse_result())
# ParseResult(scheme='https', netloc='user:pass@example.com:8443', path='/p', params='v=1', query='a=1&a=2', fragment='f')
```

"Absolute" means that the URL has a scheme (RFC 3986): `file:///etc/hosts`
is absolute although it has no hostname, the scheme-less
`//example.com/a` is a relative reference.

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
print(repr(Url("redis://:secret@localhost:6379/0")))
# Url(redis://:***@localhost:6379/0)
```
