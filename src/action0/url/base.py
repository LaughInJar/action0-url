import enum
from typing import Any
from typing import Final
from urllib.parse import ParseResult
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urlparse
from urllib.parse import urlunparse
from urllib.parse import uses_params

from action0.url.params import Params
from action0.url.params import ParamTypes


class _Unset(enum.Enum):
    """
    The type of the :py:data:`_UNSET` sentinel. An enum with a single member
    so that type checkers can narrow ``value is _UNSET`` checks.
    """

    UNSET = "unset"

    def __repr__(self) -> str:
        # shows up as the default value in signatures and the API docs
        return "<unset>"


# default of the constructor's keyword arguments: tells "not given, take the
# part from the base URL" apart from an explicit None / "" that clears the part
_UNSET: Final = _Unset.UNSET

# the default ports normalize() removes for the respective scheme
_DEFAULT_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443, "ftp": 21}

# characters that stay raw when percent-encoding a part (on top of quote()'s
# always-safe unreserved characters): RFC 3986 pchar minus the delimiters
# that would change how the URL is parsed back
_PATH_SAFE = "/:@!$&'()*+,="  # no ";", it starts the path params
_FRAGMENT_SAFE = "/?:@!$&'()*+,;="
_USERINFO_SAFE = "!$&'()*+,;="  # no ":", it separates username and password
_HOSTNAME_SAFE = "!$&'()*+,;="  # RFC 3986 reg-name: unreserved and sub-delims


def _split_authority(authority: str) -> tuple[str | None, int | None]:
    """
    Split an authority ("hostname" or "hostname:port") into its parts. An
    IPv6 literal is expected in brackets ("[::1]:8080") and is returned
    without them.

    :param authority: the authority string to split
    :return: a tuple of the hostname and the port
    :raises ValueError: if the authority contains userinfo, a malformed
                        IPv6 literal or a non-numeric port
    """
    if "@" in authority:
        raise ValueError(
            "authority is 'hostname[:port]' only, pass the userinfo as username / password"
        )

    if authority.startswith("["):
        # IPv6 literal: the port, if any, follows the closing bracket
        host_part, bracket, rest = authority[1:].partition("]")
        if not bracket or (rest and not rest.startswith(":")):
            raise ValueError(f"Invalid IPv6 authority: {authority!r}")
        port_part = rest[1:]
    elif authority.count(":") > 1:
        # an IPv6 literal without brackets cannot have a port: there is no
        # way to tell it apart from the last group of the address
        host_part, port_part = authority, ""
    else:
        host_part, _, port_part = authority.partition(":")

    if port_part and not (port_part.isascii() and port_part.isdigit()):
        raise ValueError(f"Port could not be cast to integer value as {port_part!r}")
    return host_part or None, int(port_part) if port_part else None


def _strip_brackets(hostname: str) -> str:
    """
    Remove the brackets of an IPv6 literal ("[::1]" becomes "::1"), hostnames
    are stored without them.

    :param hostname: the hostname, possibly a bracketed IPv6 literal
    :return: the hostname without surrounding brackets
    """
    if hostname.startswith("[") and hostname.endswith("]"):
        return hostname[1:-1]
    return hostname


def _encode_hostname(hostname: str) -> str:
    """
    The representation of a hostname inside a URL: an IPv6 literal is put
    in brackets, a hostname with non-ASCII characters is IDNA-encoded
    (punycode) and characters that are not allowed in a hostname are
    percent-encoded, so that a hostname can never spill over into other
    parts of the URL.

    :param hostname: the hostname to encode
    :return: the ASCII representation of the hostname
    :raises UnicodeError: if the hostname cannot be IDNA-encoded
    """
    if ":" in hostname:
        # only IPv6 literals contain colons
        return f"[{quote(_strip_brackets(hostname), safe=':')}]"
    if not hostname.isascii():
        hostname = hostname.encode("idna").decode("ascii")
    return quote(hostname, safe=_HOSTNAME_SAFE)


def _encode_path(path: str, scheme: str) -> str:
    """
    Percent-encode a path. A ";" stays raw unless it would be mistaken for
    the start of the path params when the URL is parsed again, which is only
    the case in the last segment and for schemes urllib splits params for.

    :param path: the decoded path
    :param scheme: the scheme of the URL the path belongs to
    :return: the percent-encoded path
    """
    if scheme not in uses_params:
        return quote(path, safe=_PATH_SAFE + ";")
    head, slash, last_segment = path.rpartition("/")
    return quote(head + slash, safe=_PATH_SAFE + ";") + quote(last_segment, safe=_PATH_SAFE)


def _resolve_dot_segments(path: str) -> str:
    """
    Remove "." and ".." segments from a path. For absolute paths this is the
    algorithm of RFC 3986, section 5.2.4 (a ".." cannot climb above the
    root). Relative paths stay relative: leading ".." segments are kept as
    there is nothing to resolve them against, and a path that resolves to
    the current directory becomes "./" (not "", which would refer to the
    document itself).

    :param path: the path to resolve
    :return: the path without any resolvable "." or ".." segments
    """
    absolute = path.startswith("/")
    segments = path.split("/")
    if absolute:
        # drop the empty segment in front of the leading slash
        segments = segments[1:]

    output: list[str] = []
    last_index = len(segments) - 1
    for index, segment in enumerate(segments):
        if segment == ".":
            pass
        elif segment == "..":
            if output and output[-1] != "..":
                output.pop()
            elif not absolute:
                output.append("..")
        else:
            output.append(segment)
            continue
        # a trailing dot segment refers to a directory: keep the trailing slash
        if index == last_index:
            output.append("")

    resolved = "/".join(output)
    if absolute:
        return "/" + resolved
    return resolved or ("./" if path else "")


class Url:
    """
    Python representation of a parsed URL to allow easy manipulation of its
    parts.

    Example::

        >>> url = Url("https://www.example.com/path/filename.json?foo=bar")
        >>> url.query.set("foo", "baz")
        >>> url.as_str()
        'https://www.example.com/path/filename.json?foo=baz'
        >>> url.query.add("a", "b")
        >>> url.as_str()
        'https://www.example.com/path/filename.json?foo=baz&a=b'
        >>> # allow params with multiple values (added at the end)
        >>> url.query.add("foo", "123")
        >>> url.as_str()
        'https://www.example.com/path/filename.json?foo=baz&a=b&foo=123'
        >>> url.hostname = "action0.com"
        >>> url.port = 8443
        >>> url.path = "/public/index.html"
        >>> url.username = "user"
        >>> url.password = "pass"
        >>> url.fragment = "fragment"
        >>> url.as_str()
        'https://user:pass@action0.com:8443/public/index.html?foo=baz&a=b&foo=123#fragment'

    Based on the named tuple that :py:func:`urllib.parse.urlparse` returns.

    Urls are mutable and compare by their parts (see :py:meth:`__eq__`),
    hence they are not hashable: use ``str(url)`` as a dictionary key or
    set member.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        scheme: str | None | _Unset = _UNSET,
        hostname: str | None | _Unset = _UNSET,
        path: str | None | _Unset = _UNSET,
        query: ParamTypes | None | _Unset = _UNSET,
        path_params: ParamTypes | None | _Unset = _UNSET,
        fragment: str | None | _Unset = _UNSET,
        username: str | None | _Unset = _UNSET,
        password: str | None | _Unset = _UNSET,
        port: int | None | _Unset = _UNSET,
        authority: str | None | _Unset = _UNSET,
    ) -> None:
        """
        If a `url` is given it will use this as base and other
        parameters will replace/overwrite the parts of the url string.
        Every keyword argument that is given replaces its part, also with
        an "empty" value: ``None``, ``""`` or an empty mapping remove the
        part of the base URL, only arguments that are left out keep it.

        The `url` is taken as it is, nothing is assumed about missing parts:
        a string without a scheme results in a Url without a scheme, so
        relative references like "/path?a=1" or "../file.html" round-trip.
        Mind that, as in :py:func:`urllib.parse.urlparse`, a hostname is only
        recognized after "//": "example.com/path" is a relative path, use
        "//example.com/path" or "https://example.com/path".

        The parts of a parsed `url` are stored percent-decoded, i.e. the
        attributes hold the readable values ("my file.html", not
        "my%20file.html") and :py:meth:`as_str` encodes them again; values
        given as keyword arguments are expected to be unencoded as well and
        without their delimiter (no leading "?" for the query, no "#" for
        the fragment). Be aware that an encoded "/" (%2F) inside a path
        segment is decoded like everything else and hence becomes a segment
        separator when the URL is rendered again, and that percent escapes
        which are not valid UTF-8 are replaced by the replacement character.

        Example::

            >>> url = Url("https://www.example.com/path/filename.json")
            >>> url.as_str()
            'https://www.example.com/path/filename.json'
            >>> url = Url("https://www.example.com/path/filename.json", path="/hello/world.html")
            >>> url.as_str()
            'https://www.example.com/hello/world.html'
            >>> url = Url("https://www.example.com?foo=bar", query={"bar": "baz"})
            >>> url.as_str()
            'https://www.example.com?bar=baz'
            >>> url = Url("https://www.example.com:8443/path?foo=bar#top", port=None, query=None)
            >>> url.as_str()
            'https://www.example.com/path#top'


        :param url: the optional string representation of a URL to use as base
        :param scheme: the url scheme, e.g. https, ftps, etc.
        :param hostname: the hostname (domain incl. subdomain, or IP-Address, etc.);
                         an IPv6 address is stored without its brackets
        :param path: the path to the file (including the file's name)
        :param query: the query parameters
        :param path_params: the path parameters, k=v pairs after the path separated with a ';'
                       (not commonly used, maybe you saw something like
                       'https://example.com/path/file.html;jsessionid=1234')
        :param fragment: everything after the '#' usually only interpreted by the client
        :param username: if the username / password is part of the URL, e.g.
                         'https://user:pass@example.com/'
        :param password:  if the username / password is part of the URL, e.g.
                         'https://user:pass@example.com/'
        :param port: the port to connect to
        :param authority: the combination of hostname and port ("example.com:8443",
                          "[::1]:8080"), hence it can't be combined with hostname or
                          port. Unlike urllib's netloc it has no userinfo part.
        :raises ValueError: if authority is combined with hostname or port, if
                            authority contains userinfo or is malformed, or if
                            the port or an IPv6 address in `url` is invalid
        :raises TypeError: if a query or path parameter value is ``None`` or bytes
        """
        if authority is not _UNSET:
            if hostname is not _UNSET or port is not _UNSET:
                raise ValueError("Cannot specify both authority and hostname or port")
            # both are given now: an authority without a port removes the
            # port of the base url
            hostname, port = _split_authority(authority or "")

        if url is not None:
            parse_result = urlparse(url)
        else:
            # an all-empty parse result so the lookups below fall through to
            # the keyword arguments (and "" for the unset string parts)
            parse_result = ParseResult(
                scheme="", netloc="", path="", params="", query="", fragment=""
            )

        # parsed parts are percent-decoded here and re-encoded in as_str();
        # the attributes always hold the readable values

        #: The scheme ("https", "ftp", ...), "" if the URL has none.
        self.scheme: str = parse_result.scheme if scheme is _UNSET else (scheme or "")

        #: The hostname, ``None`` if the URL has none. An IPv6 address is held
        #: without the brackets it has inside a URL ("::1", not "[::1]").
        self.hostname: str | None
        if hostname is _UNSET:
            # urllib lowercases the hostname and strips IPv6 brackets
            parsed_hostname = parse_result.hostname
            self.hostname = unquote(parsed_hostname) if parsed_hostname else None
        else:
            self.hostname = _strip_brackets(hostname) if hostname else None

        #: The port, ``None`` if the URL has none.
        self.port: int | None = parse_result.port if port is _UNSET else port

        #: The percent-decoded path, "" if the URL has none.
        self.path: str = unquote(parse_result.path) if path is _UNSET else (path or "")

        #: The percent-decoded fragment (without the "#"), "" if the URL has none.
        self.fragment: str = (
            unquote(parse_result.fragment) if fragment is _UNSET else (fragment or "")
        )

        #: The percent-decoded username, ``None`` if the URL has none.
        self.username: str | None
        if username is _UNSET:
            parsed_username = parse_result.username
            self.username = unquote(parsed_username) if parsed_username else None
        else:
            self.username = username or None

        #: The percent-decoded password, ``None`` if the URL has none. It may
        #: be set without a username ("redis://:secret@localhost").
        self.password: str | None
        if password is _UNSET:
            parsed_password = parse_result.password
            self.password = unquote(parsed_password) if parsed_password else None
        else:
            self.password = password or None

        # always fresh Params instances: a Url never shares them with the
        # arguments it was built from (copy() relies on that)
        self._query = Params(parse_result.query if query is _UNSET else query)
        # path params use ";" to separate the k=v pairs from the path and
        # each other and, being part of the path, no form encoding
        self._path_params = Params(
            parse_result.params if path_params is _UNSET else path_params,
            separator=";",
            form_encoding=False,
        )

    @property
    def query(self) -> Params:
        """
        The query parameters as a :py:class:`~action0.url.params.Params`
        instance; manipulate it in place. Assigning anything a Params can be
        built from (a query string, a mapping, an iterable of tuples) or
        ``None`` replaces all query parameters.
        """
        return self._query

    @query.setter
    def query(self, value: ParamTypes | None) -> None:
        if isinstance(value, Params) and value.separator == "&" and value.form_encoding:
            # a fitting instance is used as it is, like a plain attribute would
            self._query = value
        else:
            self._query = Params(value)

    @property
    def path_params(self) -> Params:
        """
        The path parameters (";key=value" after the path) as a
        :py:class:`~action0.url.params.Params` instance with a ";" separator
        and without form encoding; manipulate it in place. Assigning anything
        a Params can be built from or ``None`` replaces all path parameters.
        """
        return self._path_params

    @path_params.setter
    def path_params(self, value: ParamTypes | None) -> None:
        if isinstance(value, Params) and value.separator == ";" and not value.form_encoding:
            self._path_params = value
        else:
            self._path_params = Params(value, separator=";", form_encoding=False)

    @property
    def authority(self) -> str:
        """
        The "hostname:port" combination, just the hostname if no port is
        set. Unlike urllib's netloc it never contains the userinfo. The
        hostname is the readable one of :py:attr:`hostname` (not IDNA-encoded),
        an IPv6 address is in brackets ("[::1]:8080"). Assigning a string of
        the same form replaces hostname and port.

        :raises ValueError: when assigning a string with userinfo, a
                            malformed IPv6 literal or a non-numeric port
        """
        host = self.hostname or ""
        if ":" in host:
            # only IPv6 literals contain colons, the brackets keep them
            # apart from the port separator
            host = f"[{_strip_brackets(host)}]"
        if self.port is not None:
            return f"{host}:{self.port}"
        return host

    @authority.setter
    def authority(self, value: str) -> None:
        self.hostname, self.port = _split_authority(value)

    @property
    def parent(self) -> "Url":
        """
        A copy of this URL with the last path segment removed; the other
        parts (also query and fragment) are kept. Like in pathlib, a
        trailing slash is ignored ("/a/b/" has the parent "/a") and the
        parent of the root is the root.
        """
        parent_path, sep, _ = self.path.rstrip("/").rpartition("/")
        if sep:
            new_path = parent_path or "/"
        else:
            # no slash left: the parent of a bare relative segment is empty,
            # the parent of the root stays the root
            new_path = "/" if self.path.startswith("/") else ""
        return self.copy(path=new_path)

    @property
    def name(self) -> str:
        """
        The last path segment (usually the file name); "" if the path is
        empty or ends with a "/" — unlike pathlib, a trailing slash is
        significant in a URL: "/a/b/" is a directory and has no file name.
        Assigning replaces the last segment.
        """
        return self.path.rpartition("/")[2]

    @name.setter
    def name(self, value: str) -> None:
        base, sep, _ = self.path.rpartition("/")
        self.path = f"{base}{sep}{value}"

    @property
    def suffix(self) -> str:
        """
        The file extension of :py:attr:`name` including the ".";
        "" if there is none. Follows :py:attr:`pathlib.PurePath.suffix`.
        """
        # leading dots are not a suffix: neither a dotfile (".hidden") nor
        # the dot segments "." and ".." have one
        name = self.name.lstrip(".")
        dot_index = name.rfind(".")
        return name[dot_index:] if dot_index >= 0 else ""

    def as_str(self) -> str:
        """
        Assemble the (possibly modified) parts back into a URL string.
        The parts are percent-encoded as needed, a non-ASCII hostname
        is IDNA-encoded (punycode) and an IPv6 address is put in brackets.

        The IDNA encoding is the one of Python's standard library (IDNA
        2003), which differs from current browsers (IDNA 2008 / UTS 46) for
        a few characters: "straße.de" becomes "strasse.de". Assign the
        punycode form as hostname if that matters.

        :return: the string representation of the URL
        :raises UnicodeError: if the hostname cannot be IDNA-encoded
        """
        # the authority optionally has the port, username and password
        authority = _encode_hostname(self.hostname) if self.hostname else ""
        if self.port is not None:
            authority = f"{authority}:{self.port}"

        # a password does not need a username ("redis://:secret@localhost")
        if self.username or self.password:
            userinfo = quote(self.username or "", safe=_USERINFO_SAFE)
            if self.password:
                userinfo = f"{userinfo}:{quote(self.password, safe=_USERINFO_SAFE)}"
            authority = f"{userinfo}@{authority}"

        # urlunparse seems to be badly supported by the type-checker
        parts = (
            self.scheme,
            authority,
            _encode_path(self.path, self.scheme),
            self.path_params.as_str(),
            self.query.as_str(),
            quote(self.fragment, safe=_FRAGMENT_SAFE),
        )
        return str(urlunparse(parts))

    def join(self, other: "str | Url") -> "Url":
        """
        Resolve another, possibly relative, URL against this one — like a
        browser resolves a link on a page. Implements the reference
        resolution of RFC 3986, section 5.2 and, unlike
        :py:func:`urllib.parse.urljoin`, works for every scheme.

        Example::

            >>> Url("https://example.com/a/b").join("c")
            Url(https://example.com/a/c)
            >>> Url("https://example.com/a/b").join("/x")
            Url(https://example.com/x)
            >>> Url("myapp://host/a/b").join("../c?d=1")
            Url(myapp://host/c?d=1)

        :param other: the URL to resolve against this one
        :return: a new Url, this instance is not modified
        """
        reference = other if isinstance(other, Url) else type(self)(other)

        if reference.scheme:
            # an absolute URL replaces this one entirely
            target = reference.copy()
        elif reference._has_authority():
            # "//host/path": only the scheme is inherited
            target = reference.copy(scheme=self.scheme)
        elif not reference.path and not reference.path_params:
            # "?query" / "#fragment" / "": same document
            return self.copy(
                query=reference.query if reference.query else self.query,
                fragment=reference.fragment,
            )
        else:
            if reference.path.startswith("/"):
                path = reference.path
            elif self._has_authority() and not self.path:
                path = f"/{reference.path}"
            else:
                # replace everything after the last "/" of this path
                path = self.path[: self.path.rfind("/") + 1] + reference.path
            target = self.copy(
                path=path,
                path_params=reference.path_params,
                query=reference.query,
                fragment=reference.fragment,
            )

        target.path = _resolve_dot_segments(target.path)
        return target

    def _has_authority(self) -> bool:
        """
        :return: whether any part of the authority (hostname, port,
                 username, password) is set
        """
        return (
            self.hostname is not None
            or self.port is not None
            or self.username is not None
            or self.password is not None
        )

    def __truediv__(self, segment: str) -> "Url":
        """
        Return a copy with the segment(s) appended to the path, always
        joined with exactly one "/". The other parts (also query and
        fragment) are kept. A relative URL without a path stays relative.

        Example::

            >>> Url("https://example.com") / "api" / "v2"
            Url(https://example.com/api/v2)
            >>> Url() / "api" / "v2"
            Url(api/v2)

        :param segment: the path segment(s) to append
        :return: a new Url, this instance is not modified
        """
        if not isinstance(segment, str):
            return NotImplemented
        if self.path or self._has_authority():
            path = f"{self.path.rstrip('/')}/{segment.lstrip('/')}"
        else:
            # nothing to append to: a leading "/" would make the path absolute
            path = segment.lstrip("/")
        return self.copy(path=path)

    def copy(self, **overrides: Any) -> "Url":
        """
        An independent copy of this URL, optionally with parts replaced.
        ``None`` (or "" / an empty mapping) as value removes the part.

        Example::

            >>> url = Url("https://example.com:8443/index.html")
            >>> url.copy(scheme="http", port=None)
            Url(http://example.com/index.html)

        :param overrides: any URL part accepted by the constructor as keyword
                          argument (not the base `url` string)
        :return: a new Url of the same class, this instance is not modified
        :raises TypeError: on part names the constructor does not know
        :raises ValueError: if authority is combined with hostname or port
        """
        if "url" in overrides:
            # would be parsed as a base url and then be overwritten part by part
            raise TypeError("copy() got an unexpected keyword argument 'url'")
        parts: dict[str, Any] = {
            "scheme": self.scheme,
            "hostname": self.hostname,
            "port": self.port,
            "path": self.path,
            "query": self.query,
            "path_params": self.path_params,
            "fragment": self.fragment,
            "username": self.username,
            "password": self.password,
        }
        if "authority" in overrides:
            # the constructor rejects authority combined with hostname / port
            del parts["hostname"]
            del parts["port"]
        parts.update(overrides)
        return type(self)(**parts)

    def origin(self) -> "Url":
        """
        The origin — scheme, hostname and port only — e.g. for same-origin
        comparisons or as a base to build new URLs on.

        :return: a new Url of the same class with only scheme, hostname and
                 port set
        """
        return type(self)(scheme=self.scheme, hostname=self.hostname, port=self.port)

    def normalize(self) -> "Url":
        """
        A normalized copy of this URL (RFC 3986 style): scheme and hostname
        lowercased, the scheme's default port removed, "." and ".." path
        segments resolved, and the path made absolute if there is a hostname
        (an empty path becomes "/"). The path of a relative URL stays
        relative: "a/../b" becomes "b", leading ".." segments are kept.

        Example::

            >>> Url("https://example.com:443/a/./b/../c").normalize()
            Url(https://example.com/a/c)

        :return: a new Url, this instance is not modified
        """
        scheme = self.scheme.lower()
        hostname = _strip_brackets(self.hostname.lower()) if self.hostname else None
        port = self.port
        if port is not None and _DEFAULT_PORTS.get(scheme) == port:
            port = None
        path = self.path
        if hostname and not path.startswith("/"):
            # behind a hostname every path is absolute, as_str() renders it so
            path = f"/{path}"
        return self.copy(
            scheme=scheme, hostname=hostname, port=port, path=_resolve_dot_segments(path)
        )

    def as_dict(self) -> dict[str, Any]:
        """
        The URL parts as a plain dictionary (query and path params as
        dictionaries of value lists), e.g. for debugging or serialization.
        Contains the real password — use repr() for a redacted view.

        :return: a dictionary of all URL parts
        """
        return {
            "scheme": self.scheme,
            "username": self.username,
            "password": self.password,
            "hostname": self.hostname,
            "port": self.port,
            "path": self.path,
            "path_params": self.path_params.as_dict(),
            "query": self.query.as_dict(),
            "fragment": self.fragment,
        }

    def as_parse_result(self) -> ParseResult:
        """
        The URL as the named tuple :py:func:`urllib.parse.urlparse` returns,
        for interoperability with stdlib-based code. The parts are
        percent-encoded like in :py:meth:`as_str`.

        :return: the ParseResult of the assembled URL string
        """
        return urlparse(self.as_str())

    def is_absolute(self) -> bool:
        """
        :return: whether the URL has a scheme, the definition of an absolute
                 URL in RFC 3986 ("file:///etc/hosts" and "mailto:me@example.com"
                 are absolute, "//example.com/path" and "/path" are not)
        """
        return bool(self.scheme)

    def is_relative(self) -> bool:
        """
        :return: whether the URL has no scheme, i.e. is a relative reference
                 that needs a base URL (see :py:meth:`join`) to be resolved
        """
        return not self.is_absolute()

    def __eq__(self, other: object) -> bool:
        """
        Two Urls are equal if all their parts are equal. The order of query
        parameter names doesn't matter (``?a=1&b=2`` equals ``?b=2&a=1``),
        the order of multiple values of the same name does.

        :param other: the Url to compare with
        :return: whether the URLs are equal
        """
        if not isinstance(other, Url):
            return NotImplemented
        return (
            self.scheme == other.scheme
            and self.hostname == other.hostname
            and self.port == other.port
            and self.path == other.path
            and self.path_params == other.path_params
            and self.query == other.query
            and self.fragment == other.fragment
            and self.username == other.username
            and self.password == other.password
        )

    def __str__(self) -> str:
        return self.as_str()

    def __repr__(self) -> str:
        # don't leak credentials into logs and tracebacks
        url = self.copy(password="***") if self.password else self
        return f"{self.__class__.__name__}({url.as_str()})"
