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

A URL you don't modify is rendered the way it was written — percent
escapes, the order and spelling of the query, all of it — so signed URLs
and hand-crafted ones are safe to pass through:

```python
signed = "https://bucket.example/k%2Fey?X-Signature=ab%2Bc%2f&flag&x=a%20b"
assert Url(signed).as_str() == signed
```

Only these things are normalized: scheme and hostname are lowercased,
characters that are not allowed in a URL are percent-encoded
(`/a b` becomes `/a%20b`), and delimiters without content are left out
(a trailing `?` or `#`, the `:` of `user:@host`). How the parts you
*change* are encoded is described under [Encoding](#encoding).

An unparsable URL — a non-numeric or out-of-range port, a broken IPv6
address, a hostname with impossible characters — raises a `ValueError`
(which never contains the password, see
[Logging and secrets](#logging-and-secrets)).

### Relative URLs

Nothing is assumed about parts the string doesn't have: no scheme in, no
scheme out. Relative references therefore round-trip as well:

```python
url = Url("/docs/index.html?lang=en")
print(repr(url.scheme), url.hostname)  # '' None
print(url)                             # /docs/index.html?lang=en
```

As in {py:func}`urllib.parse.urlsplit`, a hostname is only recognized
after `//` — without it the text is a relative path, and a `:` early on
makes what is in front of it a scheme:

```python
print(Url("//example.com/x").hostname)  # example.com
print(Url("example.com/x").hostname)    # None
print(Url("example.com/x").path)        # example.com/x
print(repr(Url("localhost:8080").scheme), Url("localhost:8080").path)  # 'localhost' 8080
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

(validation)=
### Validation

Every part is checked when it is set — by a keyword argument, by `copy()`
or by assigning to the attribute — so a `Url` can always be rendered. A
value the part cannot have raises a `ValueError`, a value of the wrong type
a `TypeError`:

```python
for arguments in (
    {"scheme": "https://"},        # the scheme only, please
    {"hostname": "localhost:8080"},  # the port is a part of its own
    {"hostname": "example.com/x"},
    {"port": 99999},
    {"port": "8080"},
    {"path": 5},
):
    try:
        Url(**arguments)
    except (ValueError, TypeError) as error:
        print(arguments, "->", type(error).__name__)
# {'scheme': 'https://'} -> ValueError
# {'hostname': 'localhost:8080'} -> ValueError
# {'hostname': 'example.com/x'} -> ValueError
# {'port': 99999} -> ValueError
# {'port': '8080'} -> TypeError
# {'path': 5} -> TypeError
```

The messages say what is wrong and, where there is an obvious fix, what
to do instead:

```python
try:
    Url(scheme="http", hostname="localhost:8080")
except ValueError as error:
    print(error)
# Invalid hostname 'localhost:8080': a ':' is only allowed in an IPv6 address (pass a port as port=... or use authority=...)
```

Scheme and hostname are case-insensitive and stored in lowercase.

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

Username and password are *not* touched when hostname or authority are
replaced — remove them too if the new host must not get the credentials:

```python
print(Url("https://user:secret@example.com/x", authority="other.org"))
# https://user:secret@other.org/x
print(Url("https://user:secret@example.com/x", authority="other.org", username=None, password=None))
# https://other.org/x
```

## Changing parts

Every part is an attribute — assign and render. Assignments are
[validated](#validation) and `None` removes a part:

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
url.fragment = None
print(url)
# https://other.org:9000/v2/items?sort=price
url.fragment = "top"
```

A misspelled attribute is an error, not a silent no-op:

```python
try:
    url.host = "example.com"
except AttributeError as error:
    print(error)
# 'Url' object has no attribute 'host' and no __dict__ for setting new attributes
```

`url.query` and `url.path_params` can be assigned as well — anything a
`Params` can be built from, or `None` to remove them all. What you assign
is copied, two `Url`s never share their parameters:

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

### URLs without a host

Some URLs have an authority that is empty — the `//` is there, but nothing
follows: `file:///etc/hosts`, `sqlite:///data.db`. Their `hostname` is `""`,
while it is `None` for a URL that has no authority at all. The two are
different URLs, so the difference is kept:

```python
print(repr(Url("sqlite:///data.db").hostname), repr(Url("sqlite:/data.db").hostname))
# '' None
print(Url(scheme="sqlite", hostname="", path="/data.db"))
# sqlite:///data.db
print(Url("sqlite:////var/lib/app/data.db").path)   # an absolute file path
# //var/lib/app/data.db
```

(`file:` URLs always get their `//`, also when built without a hostname.)

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

Names are strings; values are strings, ints, floats and bools — the
numbers are written the way Python prints them, bools become `"true"` /
`"false"`. Everything else (`None`, bytes, dates, decimals, ...) raises a
`TypeError` instead of being guessed at; convert it yourself:

```python
import datetime

try:
    query["since"] = datetime.date(2026, 1, 31)
except TypeError as error:
    print(error)
# parameter values must be str, int, float or bool (or an iterable of those), not date; convert other objects with str()
query["since"] = str(datetime.date(2026, 1, 31))
print(query["since"])  # 2026-01-31
del query["since"]
```

`update()` is all or nothing: if one value is rejected, nothing changes.

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

When parsing a string, pass the bare query without the leading `?`.
Parsed parameters are rendered exactly as they were written until you
modify them; from then on they are written from the pairs, in a normalized
spelling:

```python
params = Params("flag&a=1&&b=x%20y")
print(params)        # reading changes nothing
# flag&a=1&&b=x%20y
params.add("c", 3)   # "=" added, empty pair dropped, "%20" -> "+"
print(params)
# flag=&a=1&b=x+y&c=3
```

(parameters-and-plus)=
### `+` and spaces

In the query of a web URL a space is written as `+` (form encoding), so a
`+` *read* from such a query is a space. That is a convention of the web,
not of URLs in general: in a `mailto:` URL, in most custom schemes and in
path parameters a `+` is a plus sign. `Url` therefore treats the query as
form-encoded for `http`, `https`, `ws`, `wss` and for URLs without a scheme,
and as plain percent-encoded for everything else:

```python
print(Url("https://example.com/?q=1+1").query["q"])        # 1 1
print(Url("mailto:me@example.com?body=1+1").query["body"])  # 1+1
print(Url(scheme="mailto", path="me@example.com", query={"body": "a b"}))
# mailto:me@example.com?body=a%20b
```

It is the scheme the URL has when the query is parsed or assigned that
decides; `url.query.form_encoding = True` (or `False`) overrides it.

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

Only the last path segment can have parameters, and only for the schemes
that are known to use them (`http`, `https`, `ftp` and a few more, plus
URLs without a scheme); a `;` anywhere else is simply part of the path.
The parameters stay with their segment when the path changes:

```python
url = Url("https://example.com/a/b;v=1")
print(url / "c")    # https://example.com/a/b;v=1/c
print(url.parent)   # https://example.com/a
print(Url("file:///a/report;final.txt").path)  # /a/report;final.txt
```

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
reference against the URL, the way a link on a page is resolved
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
print(Url("https://example.com/list?filter=x").join("?"))  # https://example.com/list
```

It follows the RFC to the letter where `urljoin` is lenient: a reference
with a scheme is never relative (`http:g` stays `http:g`), and the result
has the fragment of the reference — none, if it has none. The result is
always an instance of the class `join()` is called on.

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
instance of the same class, so subclasses of `Url` stay what they are —
also subclasses with a constructor of their own, and with the attributes
they add. `copy.copy()` and `copy.deepcopy()` work as well.

(comparing-and-normalizing)=
## Comparing and normalizing

Two `Url`s are equal if they are *equivalent*, i.e. rendered the same
apart from the spelling of percent escapes. The order of query (and path)
parameter *names* doesn't matter, the order of multiple values per name
does:

```python
print(Url("https://example.com?a=1&b=2") == Url("https://example.com?b=2&a=1"))
# True
print(Url("https://example.com/%7Euser") == Url("https://example.com/~user"))
# True
print(Url("https://bücher.example/") == Url("https://xn--bcher-kva.example/"))
# True
print(Url("https://example.com/a%2Fb") == Url("https://example.com/a/b"))  # one segment vs. two
# False
```

{py:meth}`~action0.url.base.Url.origin` reduces a URL to scheme, hostname
and port — without the scheme's default port — for same-origin checks:

```python
print(Url("https://example.com:443/a?x=1").origin() == Url("https://example.com/b").origin())
# True
print(Url("https://example.com:443/a?x=1").origin())
# https://example.com
```

Being mutable and compared by their parts, `Url` and `Params` are not
hashable — use `str(url)` as dictionary key or set member.

{py:meth}`~action0.url.base.Url.normalize` returns an RFC 3986-normalized
copy — default ports removed, percent escapes in their canonical form,
`.` / `..` segments resolved and, if there is a hostname, the path made
absolute (an empty one becomes `/`):

```python
print(Url("https://example.com:443/a/../b").normalize())
# https://example.com/b
print(Url("https://example.com/%7euser/%c3%a4").normalize())
# https://example.com/~user/%C3%A4
print(Url("https://example.com").normalize())
# https://example.com/
```

The path of a relative URL stays relative; `..` segments with nothing to
resolve them against are kept:

```python
print(Url("a/./b/../c").normalize())  # a/c
print(Url("a/../../b").normalize())   # ../b
```

(encoding)=
## Encoding

Inside a `Url` the parts are kept the way they are written in a URL —
percent-encoded — which is what makes parsing and rendering an exact round
trip. The attributes show and take the decoded, readable values; what you
assign is encoded as needed. Non-ASCII hostnames become punycode:

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

The decoded view is convenient but cannot tell everything apart: an
escaped `/` (`%2F`, part of a segment) reads like a real one (a segment
separator), and escapes that are not valid UTF-8 read as the replacement
character. Where that matters, `raw_path` and `raw_fragment` give — and
take — the encoded form:

```python
url = Url("https://example.com/files/a%2Fb.txt")
print(url.path, "|", url.raw_path)
# /files/a/b.txt | /files/a%2Fb.txt
print(url.name)        # the last segment, split on real slashes
# a/b.txt
url.raw_path = "/files/c%2Fd.txt"
print(url)
# https://example.com/files/c%2Fd.txt
url.path = "/files/100% c%2Fd"   # decoded: a "%" is a percent sign
print(url)
# https://example.com/files/100%25%20c%252Fd
```

Assigning the decoded value you just read (`url.path = url.path`)
therefore re-encodes it and turns `%2F` into `/`.

A path that would be read as something else is prefixed when rendering:
a relative path with a `:` in its first segment gets a `./` (it would be a
scheme), a path starting with `//` on a URL without a host a `/.` (it
would be a host):

```python
print(Url(path="javascript:alert(1)"), "|", Url(path="//evil.example/x"))
# ./javascript:alert(1) | /.//evil.example/x
```

The IDNA encoding is the one of Python's standard library (IDNA 2003). It
differs from current browsers (IDNA 2008 / UTS 46) for a few characters —
`straße.de` becomes `strasse.de` instead of `xn--strae-oqa.de`. If that
matters, assign the punycode form as hostname; ASCII hostnames are never
touched.

### The parts of an HTTP request

An HTTP request does not carry the URL as one string: the request line
has the *request target* — path and query —, and the host travels in the
`Host` header. Both are the URL's own spelling, and there is a property
for each:

```python
url = Url("https://user:secret@bücher.example:8443/k%2Fey;v=1?sig=ab%2Bc&flag#top")
print(url.request_target)
# /k%2Fey;v=1?sig=ab%2Bc&flag
print(url.raw_authority, "|", url.authority)
# xn--bcher-kva.example:8443 | bücher.example:8443
```

`request_target` is the origin-form of RFC 9112: path, path params and
query exactly as `as_str()` writes them — escapes are neither decoded nor
re-encoded, so the target of a signed URL is the one that was signed —,
without the fragment. It is always an absolute path: `/` stands in for an
empty one, and a relative path gets the `/` it is written with behind a
host. The prefixes that keep a path from being read as a host or a scheme
in a URL string are not needed in a request line and not part of it:

```python
print(Url("https://example.com?page=2").request_target, "|", Url("items/5").request_target)
# /?page=2 | /items/5
print(Url(path="//files/x"), "|", Url(path="//files/x").request_target)
# /.//files/x | //files/x
```

`raw_authority` is to `authority` what `raw_path` is to `path`: hostname
and port as the URL string has them — a non-ASCII hostname IDNA-encoded,
an IPv6 address in brackets — and, like the authority, never the
userinfo. It is read-only; `authority` takes the encoded form as well.

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

The errors raised for an unparsable URL don't quote the password either:

```python
try:
    Url("https://user:secret@example.com:port/")
except ValueError as error:
    print(error)
# Port could not be cast to integer value as 'port'
```

Only the password part is redacted. A token given as *username*
(`https://token@github.com/…`) or inside the query is shown by `repr()` —
keep such URLs out of the logs yourself.
