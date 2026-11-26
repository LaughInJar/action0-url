# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

Nothing yet.

## 0.2.1 — 2026-11-26

### Added

- `Url.request_target`: the target of an HTTP request for the URL in its
  origin-form (RFC 9112) — path, path params and query exactly as
  `as_str()` writes them, without the fragment. Always an absolute path:
  `/` for an empty one, and without the `/.` and `./` prefixes a URL
  string needs for a path that would be read as a host or a scheme.
- `Url.raw_authority`: hostname and port as they are written in the URL
  string — a non-ASCII hostname IDNA-encoded, an IPv6 address in
  brackets, never the userinfo. The encoded twin of `authority`, as
  `raw_path` is of `path`, and the value of an HTTP `Host` header.
  Read-only.

## 0.2.0 — 2026-11-26

### Changed — may require changes in your code

**Parsing and rendering**

- **No default scheme.** `Url()` used to assume `https` for a URL string
  without a scheme, which broke relative references (`Url("/a/b")` rendered
  as `https:///a/b`). A string without a scheme now gives a `Url` without a
  scheme and round-trips unchanged. If you relied on the default, pass the
  scheme: `Url("//example.com/x", scheme="https")`.
- **An unmodified URL is rendered as it was written.** The parts are kept
  percent-encoded internally instead of being decoded and re-encoded, so
  escapes of reserved characters (`%2F`, `%2B`, …), escapes that are not
  valid UTF-8 and the spelling of the query (`?flag`, `%20`, `a=1&&b=2`)
  survive a round trip. Signed URLs are safe to pass through. What is still
  normalized: scheme and hostname are lowercased, characters that are not
  allowed in a URL are percent-encoded, and delimiters without content (a
  trailing `?` or `#`, the `:` of `user:@host`) are left out.
- **`path`, `fragment`, `username` and `password` are decoded views** of
  that encoded form. Reading and assigning them works as before, but
  assigning a value you read (`url.path = url.path`) re-encodes it. The new
  `raw_path` and `raw_fragment` give and take the encoded form.
- **`Params` renders parsed parameters verbatim until they are modified.**
  `Params("flag&q=a%20b").as_str()` is that string again (was
  `flag=&q=a+b`); after the first modification, and with `sort=True`, the
  parameters are written from the pairs in the normalized spelling.
- **The query is only form-encoded for web URLs.** A `+` is read as a space
  (and a space written as `+`) for `http`, `https`, `ws`, `wss` and URLs
  without a scheme. For every other scheme — `mailto:`, custom schemes — a
  `+` is a plus sign and a space is written as `%20`. Set
  `url.query.form_encoding` to override.
- **Path params are not form-encoded** either: in `url.path_params` a `+`
  is a literal plus sign and a space is written as `%20`. They are only
  split off the path for the schemes that use them (`http`, `https`, `ftp`,
  … and URLs without a scheme), and they stay with their segment: `parent`
  drops them, the `/` operator leaves them on the segment they were on.
- **A path that would be read as something else is prefixed** when
  rendering: a relative path with a `:` in its first segment gets a `./`
  (`a:b` would be the scheme `a`), a path starting with `//` on a URL
  without a host gets a `/.` (it would name a host).
- **A password without a username is rendered** (`redis://:secret@localhost`)
  instead of being discarded with a log message. The library no longer logs
  anything.
- **IPv6 hostnames are held without brackets**, like `urllib` does:
  `Url(authority="[::1]:8080").hostname` is `"::1"` (was `"[::1]"`).
  Rendering and the `authority` property add the brackets.
- **An empty authority is kept:** `sqlite:///data.db` and `myapp:///path`
  used to be rendered as `sqlite:/data.db` and `myapp:/path`. Their
  `hostname` is `""`, while it is `None` for a URL without any authority;
  consequently `hostname=""` now means "an empty authority", only `None`
  removes the hostname.
- Rendering no longer goes through `urllib.parse.urlunparse`, whose output
  for URLs without a host differs between Python versions. A URL with a
  scheme but no authority is written without `//` (`https:/x`, was
  `https:///x`); `file:` URLs always get their `//` (`file:///etc/hosts`).

**Validation**

- **Every part is validated when it is set** — by a keyword argument, by
  `copy()` or by assigning to the attribute. A `ValueError` is raised for
  - a scheme that is not a valid scheme (`"https://"`),
  - a hostname with whitespace or one of `/ ? # @ [ ] \`, with a `:` that
    is not part of an IPv6 address (`"localhost:8080"` — use `port=` or
    `authority=`), or one that cannot be IDNA-encoded,
  - a port outside of 0–65535,
  - an `authority` with userinfo, a non-numeric port or an invalid host;

  a `TypeError` for a value of the wrong type, including a `url` that is
  not a string. A URL string whose hostname is invalid after decoding
  (`http://example.com%3A8080/`) raises as well. `scheme` and `hostname`
  are stored in lowercase.
- **Keyword arguments always replace their part.** `None`, `""`, `0` and
  empty mappings used to be ignored when a base URL string was given; now
  only arguments that are left out keep the part of the base URL.
  `Url(base, port=None)` removes the port, `Url(base, query={})` the query.
  Code passing `None` for "no override" has to leave the argument out
  instead. Assigning `None` to an attribute removes the part, too.
- **`Url` has `__slots__`:** assigning to an attribute that does not exist
  (`url.host = ...`) raises an `AttributeError`. Subclasses can still add
  attributes.
- **`Params` only accepts what its type hints promise.** Names have to be
  strings; values strings, ints, floats or bools (or an iterable of
  those). `None`, bytes and objects of other types (`Decimal`, `date`, a
  `dict`) raise a `TypeError` — convert them with `str()`. So do a
  separator other than `&` and `;`, an unsupported `params` argument
  (`Params(5)` was silently empty) and an iterable of something else than
  pairs (`Params(["ab"])` was `a=b`).
- **`Params.setdefault()` requires a default** and returns the value as it
  is stored (a string).
- **`Params.update()` takes its first argument positionally only**, so that
  `update(params="x")` sets the parameter named `params`; it is now all or
  nothing, and an empty list of values removes the name like `set()` does.

**Behaviour of methods**

- **Equality compares equivalent URLs** instead of decoded attributes:
  `%7E` equals `~`, a hostname equals its IDNA form and a relative path
  behind a host equals the absolute one it is rendered as — but `/a%2Fb`
  no longer equals `/a/b`.
- **`is_absolute()` / `is_relative()` follow RFC 3986:** absolute means "has
  a scheme" (was: "has a hostname"). `file:///etc/hosts` is absolute now, a
  scheme-less `//example.com/x` is relative.
- **`Url.join()` implements RFC 3986 itself** instead of wrapping
  `urllib.parse.urljoin`. References are now resolved for every scheme
  (`myapp://host/a/b` + `c`) and for relative base URLs. Where `urljoin` is
  lenient, `join()` follows the RFC: a reference with a scheme is never
  relative (`http:g` stays `http:g`), the result has the fragment of the
  reference (none for `""`), and `g//h` keeps its empty segment. `join("?")`
  clears the query. The result always has the class `join()` is called on.
- **`Url.normalize()` keeps relative paths relative** (`a/../b` becomes `b`,
  not `/b`; leading `..` segments are kept), makes the path absolute when
  there is an authority, brings percent escapes into their canonical form
  and no longer treats an escaped `/` as a segment separator.
- **`origin()` leaves out the scheme's default port**, so that
  `https://example.com:443` and `https://example.com` have the same origin.
- **Sorting keeps the order of the values of one name.** `Params.sort()` and
  `as_str(sort=True)` sort by name only (`a=3&a=1` stays in that order), so
  sorting no longer changes what `==` compares.
- **Assigning to `url.query` / `url.path_params` copies** what is assigned;
  two `Url`s never share a `Params` instance.
- **`Url.copy()` only takes the URL parts** as (typed) keyword arguments;
  `copy(url=...)` used to be merged with the copied URL part by part.
- `suffix` is `""` for the dot segments `.` and `..` (`..` had the
  suffix `"."`).

### Fixed

- IPv6 URLs round-trip: `Url("http://[::1]:8080/x")` rendered as
  `http://::1:8080/x`. IPvFuture literals (`http://[v1.fe]/`) keep their
  brackets.
- `authority="other.org"` on top of a base URL kept the port of the base
  URL.
- The port `0` was dropped when rendering.
- Assigning a string or mapping to `url.query` / `url.path_params` broke
  `as_str()` with an `AttributeError`; both are properties now that accept
  everything a `Params` can be built from (or `None`).
- `Params == mapping` raised a `TypeError` for mappings with values a
  `Params` cannot hold; it is `False` now.
- A `;` in the path was percent-encoded even where it cannot be mistaken
  for the start of the path params, and `join()` took `;final.txt` off the
  path of a reference for schemes that have no path params
  (`file:///a/b` + `report;final.txt`).
- `repr()` could raise: for a hostname that cannot be IDNA-encoded, and for
  subclasses with a constructor of their own once a password was set. It
  never raises now.
- The `ValueError` for an unparsable URL could contain the password
  (urllib quotes the netloc in one of its messages).
- `Url / 5` raised an `AttributeError` instead of a `TypeError`, and
  appending a segment to a relative URL without a path made it absolute.
- `copy()`, `origin()`, `join()`, the `/` operator, `parent` and
  `normalize()` return an instance of the subclass they are called on —
  also for subclasses with a different constructor, whose additional
  attributes are copied too.
- `copy.copy()` of a `Url` or a `Params` shared the parameters with the
  original.
- `dict(params)`, `items()`, `values()` and `update()` took quadratic time
  (seconds for a query with tens of thousands of parameters).
- A `(str, Enum)` member given as parameter value was rendered as
  `Color.RED` instead of its value.

### Added

- `Url.raw_path` and `Url.raw_fragment`: the percent-encoded form of path
  and fragment, readable and assignable.
- `Params(..., form_encoding=False)` for parameters outside of a web query.
- `Params.copy()`.

### Documentation

- The documentation site says that it describes the `main` branch, which
  can be ahead of the latest release.
- The round-trip guarantees, the validation rules, the equality semantics
  and the IDNA 2003 behaviour of the hostname encoding are documented.
- The API reference lists all attributes of `Url`.
- New: this changelog.

## 0.1.0 — 2026-08-07

Initial release.
