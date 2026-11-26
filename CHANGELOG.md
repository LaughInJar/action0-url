# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed — may require changes in your code

- **No default scheme.** `Url()` used to assume `https` for a URL string
  without a scheme, which broke relative references (`Url("/a/b")` rendered
  as `https:///a/b`). A string without a scheme now gives a `Url` without a
  scheme and round-trips unchanged. If you relied on the default, pass the
  scheme: `Url("//example.com/x", scheme="https")`.
- **Keyword arguments always replace their part.** `None`, `""`, `0` and
  empty mappings used to be ignored when a base URL string was given; now
  only arguments that are left out keep the part of the base URL.
  `Url(base, port=None)` removes the port, `Url(base, query={})` the query.
  Code passing `None` for "no override" has to leave the argument out
  instead.
- **A password without a username is rendered** (`redis://:secret@localhost`)
  instead of being discarded with a log message. The library no longer logs
  anything.
- **IPv6 hostnames are held without brackets**, like `urllib` does:
  `Url(authority="[::1]:8080").hostname` is `"::1"` (was `"[::1]"`).
  Rendering and the `authority` property add the brackets.
- **`is_absolute()` / `is_relative()` follow RFC 3986:** absolute means "has
  a scheme" (was: "has a hostname"). `file:///etc/hosts` is absolute now, a
  scheme-less `//example.com/x` is relative.
- **Sorting keeps the order of the values of one name.** `Params.sort()` and
  `as_str(sort=True)` sort by name only (`a=3&a=1` stays in that order), so
  sorting no longer changes what `==` compares.
- **Path params are not form-encoded:** in `url.path_params` a `+` is a
  literal plus sign and a space is written as `%20`. The query is unchanged.
- **`Url.join()` implements RFC 3986 itself** instead of wrapping
  `urllib.parse.urljoin`. Results are the same for the schemes `urljoin`
  knows; references are now also resolved for all other schemes
  (`myapp://host/a/b` + `c`) and for relative base URLs.
- **`Url.normalize()` keeps relative paths relative** (`a/../b` becomes `b`,
  not `/b`; leading `..` segments are kept) and makes the path absolute when
  there is a hostname.
- **The `authority` argument and setter are strict:** userinfo
  (`user@host`), a non-numeric port or a malformed IPv6 literal raise a
  `ValueError` instead of ending up in the hostname.
- **`Params.update()` takes its first argument positionally only**, so that
  `update(params="x")` sets the parameter named `params`.
- **`Url.copy(url=...)` raises a `TypeError`**; it used to merge the given
  URL with the copied one part by part.
- `suffix` is `""` for the dot segments `.` and `..` (`..` had the
  suffix `"."`).

### Fixed

- IPv6 URLs round-trip: `Url("http://[::1]:8080/x")` rendered as
  `http://::1:8080/x`.
- `authority="other.org"` on top of a base URL kept the port of the base
  URL.
- The port `0` was dropped when rendering.
- Assigning a string or mapping to `url.query` / `url.path_params` broke
  `as_str()` with an `AttributeError`; both are properties now that accept
  everything a `Params` can be built from (or `None`).
- `Params == mapping` raised a `TypeError` for mappings with values a
  `Params` cannot hold; it is `False` now.
- Parameter values of other types than `str`, `int`, `float` and `bool`:
  objects like `Decimal`, `date` or `UUID` are converted with `str()`
  (they raised "object is not iterable"), bytes raise a `TypeError` (they
  were silently split into one value per byte) and `None` raises a
  `TypeError` with a helpful message.
- A hostname containing URL delimiters (`/`, `?`, `#`, `@`) was rendered
  verbatim and could spill over into other parts of the URL; such
  characters are percent-encoded now. Percent-encoded hostnames are decoded
  when parsing.
- A `;` in the path was percent-encoded even where it cannot be mistaken
  for the start of the path params (in all but the last segment, and for
  schemes without path params such as `ws`), which changed URLs like
  `https://example.com/a;x=1/b` on a round trip.
- `Url / 5` raised an `AttributeError` instead of a `TypeError`, and
  appending a segment to a relative URL without a path made it absolute.
- `copy()`, `origin()`, `join()`, the `/` operator, `parent` and
  `normalize()` return an instance of the subclass they are called on.

### Added

- `Params(..., form_encoding=False)` for parameters outside of a query.

### Documentation

- The round-trip guarantees are stated precisely (what is preserved, what
  is normalized, what is lossy), and the IDNA 2003 behaviour of the
  hostname encoding is documented.
- The API reference lists the attributes of `Url` and names the mapping
  methods `Params` inherits.
- New: this changelog.

## 0.1.0 — 2026-08-07

Initial release.
