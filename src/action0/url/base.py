import copy
import enum
import ipaddress
import re
import string
from typing import Any
from typing import Final
from typing import Self
from urllib.parse import ParseResult
from urllib.parse import SplitResult
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urlparse
from urllib.parse import urlsplit

from action0.url.params import Params
from action0.url.params import ParamTypes
from action0.url.params import _requote


class _Unset(enum.Enum):
    """
    The type of the :py:data:`_UNSET` sentinel. An enum with a single member
    so that type checkers can narrow ``value is _UNSET`` checks.
    """

    UNSET = "unset"

    def __repr__(self) -> str:
        # shows up as the default value in signatures and the API docs
        return "<unset>"


# default of the keyword arguments of the constructor and of copy(): tells
# "not given, keep the part" apart from an explicit None / "" that clears it
_UNSET: Final = _Unset.UNSET

# the default ports normalize() and origin() remove for the respective scheme
_DEFAULT_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443, "ftp": 21}

# the schemes whose last path segment may carry ";key=value" path params
# ("" stands for relative references). The list is the one urllib.parse has
# used for ages (its "uses_params"); it is copied here because that list is
# not a documented API and the behaviour must not depend on the Python version.
_PATH_PARAMS_SCHEMES = frozenset(
    {
        "",
        "ftp",
        "hdl",
        "http",
        "https",
        "imap",
        "mms",
        "prospero",
        "rtsp",
        "rtsps",
        "rtspu",
        "sftp",
        "shttp",
        "sip",
        "sips",
        "tel",
    }
)

# the schemes whose query is form-encoded ("+" stands for a space): the web
# ones and, because they are almost always resolved against a web URL,
# relative references. Everywhere else (mailto, custom schemes, ...) a "+" is
# just a plus sign.
_FORM_ENCODED_SCHEMES = frozenset({"", "http", "https", "ws", "wss"})

# characters that stay raw when percent-encoding a part (on top of quote()'s
# always-safe unreserved characters): RFC 3986 pchar minus the delimiters
# that would change how the URL is parsed back
_PATH_SAFE = "/:@!$&'()*+,;="
_SEGMENT_SAFE = ":@!$&'()*+,;="  # like the path, but a "/" must not split it
_FRAGMENT_SAFE = "/?:@!$&'()*+,;="
_USERINFO_SAFE = "!$&'()*+,;="  # no ":", it separates username and password
_HOSTNAME_SAFE = "!$&'()*+,;="  # RFC 3986 reg-name: unreserved and sub-delims

_UNRESERVED = frozenset(string.ascii_letters + string.digits + "-._~")

_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*")
_ESCAPE_RE = re.compile(r"%([0-9A-Fa-f]{2})")
# RFC 3986 IPvFuture, the content of the brackets in "http://[v1.fe]/"
_IPVFUTURE_RE = re.compile(r"v[0-9A-Fa-f]+\.[A-Za-z0-9\-._~!$&'()*+,;=:]+")
# characters that can never be part of a hostname: URL delimiters (they would
# end the hostname when the URL is parsed again), whitespace and control
# characters
_HOSTNAME_FORBIDDEN_RE = re.compile(r"[\s\x00-\x1f\x7f/?#@\[\]\\]")


def _canonical(encoded: str) -> str:
    """
    The canonical spelling of a percent-encoded string (RFC 3986, section
    6.2.2): escapes of unreserved characters are decoded ("%7E" is "~"), the
    hex digits of all other escapes are uppercased. Strings that are equal
    after this are equivalent; an escaped reserved character like "%2F" is
    deliberately *not* the same as the raw one.

    :param encoded: the percent-encoded string
    :return: the string in canonical spelling
    """

    def replace(match: re.Match[str]) -> str:
        char = chr(int(match.group(1), 16))
        return char if char in _UNRESERVED else f"%{match.group(1).upper()}"

    return _ESCAPE_RE.sub(replace, encoded)


def _text(value: str | None, part: str) -> str:
    """
    Check the value of a string part of the URL.

    :param value: the value given by the user
    :param part: the name of the part, for the error message
    :return: the value, "" for ``None``
    :raises TypeError: if the value is not a string
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"{part} must be a str or None, not {type(value).__name__}")
    return value


def _check_scheme(scheme: str | None) -> str:
    """
    Validate a scheme (RFC 3986: a letter followed by letters, digits, "+",
    "-" or ".") and lowercase it, schemes being case-insensitive.

    :param scheme: the scheme given by the user
    :return: the lowercased scheme, "" for ``None``
    :raises TypeError: if the scheme is not a string
    :raises ValueError: if the scheme contains characters it cannot have
    """
    scheme = _text(scheme, "scheme")
    if scheme and not _SCHEME_RE.fullmatch(scheme):
        raise ValueError(
            f"Invalid scheme {scheme!r}: a scheme is a letter followed by letters, "
            'digits, "+", "-" or "." (pass "https", not "https://")'
        )
    return scheme.lower()


def _check_hostname(hostname: str | None) -> str | None:
    """
    Validate a hostname and bring it into the form it is stored in:
    lowercased (hostnames are case-insensitive) and, for an IPv6 address,
    without the brackets it has inside a URL.

    :param hostname: the hostname given by the user
    :return: the hostname to store: ``None`` (no authority) and "" (an
             empty authority, as in "file:///etc/hosts") are kept apart
    :raises TypeError: if the hostname is not a string
    :raises ValueError: if the hostname contains characters a hostname cannot
                        have, a ":" without being an IPv6 address, or cannot
                        be IDNA-encoded
    """
    if hostname is None:
        return None
    if not isinstance(hostname, str):
        raise TypeError(f"hostname must be a str or None, not {type(hostname).__name__}")
    if not hostname:
        return ""

    host = hostname
    bracketed = host.startswith("[") and host.endswith("]")
    if bracketed:
        host = host[1:-1]
        if _IPVFUTURE_RE.fullmatch(host):
            # the only kind of host that is stored with its brackets: without
            # them "v1.fe" could not be told apart from a DNS name
            return f"[{host.lower()}]"

    if bracketed or ":" in host:
        address, percent, zone = host.partition("%")
        try:
            ipaddress.IPv6Address(address)
        except ValueError:
            reason = (
                "not an IPv6 address"
                if bracketed
                else "a ':' is only allowed in an IPv6 address (pass a port as "
                "port=... or use authority=...)"
            )
            raise ValueError(f"Invalid hostname {hostname!r}: {reason}") from None
        if percent and (not zone or _HOSTNAME_FORBIDDEN_RE.search(zone)):
            raise ValueError(f"Invalid hostname {hostname!r}: invalid IPv6 zone")
        # the zone identifier is case-sensitive, the address is not
        return f"{address.lower()}{percent}{zone}"

    if _HOSTNAME_FORBIDDEN_RE.search(host):
        raise ValueError(
            f"Invalid hostname {hostname!r}: a hostname cannot contain whitespace "
            'or any of "/", "?", "#", "@", "[", "]", "\\"'
        )
    host = host.lower()
    if not host.isascii():
        # checked here so that rendering can never fail later on
        try:
            host.encode("idna")
        except UnicodeError as error:
            raise ValueError(f"Invalid hostname {hostname!r}: {error}") from None
    return host


def _check_port(port: int | None) -> int | None:
    """
    Validate a port.

    :param port: the port given by the user
    :return: the port
    :raises TypeError: if the port is not an integer
    :raises ValueError: if the port is not in the range 0-65535
    """
    if port is None:
        return None
    # bool is an int, but True is certainly not meant as port 1
    if isinstance(port, bool) or not isinstance(port, int):
        raise TypeError(f"port must be an int or None, not {type(port).__name__}")
    if not 0 <= port <= 65535:
        raise ValueError(f"Port out of range 0-65535: {port}")
    return port


def _split_authority(authority: str) -> tuple[str, int | None]:
    """
    Split an authority ("hostname" or "hostname:port") into its parts. An
    IPv6 literal is expected in brackets ("[::1]:8080"). The hostname is
    returned as it was written; it is validated when it is assigned.

    :param authority: the authority string to split
    :return: a tuple of the hostname and the port
    :raises ValueError: if the authority contains userinfo, an unclosed
                        bracket or a non-numeric port
    """
    if "@" in authority:
        raise ValueError(
            "authority is 'hostname[:port]' only, pass the userinfo as username / password"
        )

    if authority.startswith("["):
        # IPv6 literal: the port, if any, follows the closing bracket
        end = authority.find("]")
        rest = authority[end + 1 :]
        if end == -1 or (rest and not rest.startswith(":")):
            raise ValueError(f"Invalid IPv6 authority: {authority!r}")
        host_part, port_part = authority[: end + 1], rest[1:]
    elif authority.count(":") > 1:
        # an IPv6 literal without brackets cannot have a port: there is no
        # way to tell it apart from the last group of the address
        host_part, port_part = authority, ""
    else:
        host_part, _, port_part = authority.partition(":")

    if port_part and not (port_part.isascii() and port_part.isdigit()):
        raise ValueError(f"Port could not be cast to integer value as {port_part!r}")
    return host_part, int(port_part) if port_part else None


def _encode_hostname(hostname: str) -> str:
    """
    The representation of a (validated) hostname inside a URL: an IPv6
    literal is put in brackets, a hostname with non-ASCII characters is
    IDNA-encoded (punycode) and the few characters that are allowed in the
    attribute but not raw in a URL are percent-encoded.

    :param hostname: the hostname as it is stored
    :return: the ASCII representation of the hostname
    """
    if hostname.startswith("["):
        # IPvFuture literals are stored with their brackets
        return hostname
    if ":" in hostname:
        # only IPv6 literals contain colons; the "%" of a zone becomes "%25"
        return f"[{quote(hostname, safe=':')}]"
    if not hostname.isascii():
        hostname = hostname.encode("idna").decode("ascii")
    return quote(hostname, safe=_HOSTNAME_SAFE)


def _split_path_params(path: str) -> tuple[str, str]:
    """
    Split the path params (";key=value") off the last segment of a path.

    :param path: the raw path
    :return: a tuple of the path without the params and the params
    """
    semicolon = path.find(";", path.rfind("/") + 1)
    if semicolon == -1:
        return path, ""
    return path[:semicolon], path[semicolon + 1 :]


def _redact_userinfo(message: str, url: str) -> str:
    """
    Replace the password of a URL inside an error message about that URL,
    so that it cannot leak into logs and tracebacks.

    :param message: the error message, possibly quoting parts of the URL
    :param url: the URL the message is about
    :return: the message without the password
    """
    netloc = url.partition("//")[2]
    for delimiter in "/?#":
        netloc = netloc.partition(delimiter)[0]
    userinfo, at, _ = netloc.rpartition("@")
    username, colon, password = userinfo.partition(":")
    if not (at and colon and password):
        return message
    message = message.replace(f"{userinfo}@", f"{username}:***@")
    # in case the message quotes the password in another form
    return message.replace(password, "***")


# what urllib strips from the start of a URL, respectively removes anywhere
# in it, before it looks for the scheme
_LEADING_JUNK = "".join(map(chr, range(0x21)))
_REMOVED_CHARACTERS = str.maketrans("", "", "\t\r\n")


def _has_empty_authority(url: str, split: SplitResult) -> bool:
    """
    Whether a URL has an authority that is empty, like "file:///etc/hosts"
    or "sqlite:///data.db" — urllib reports the same empty netloc for those
    as for a URL without any authority ("file:/etc/hosts").

    :param url: the URL string
    :param split: what urllib made of it
    :return: whether there is a "//" directly followed by the path
    """
    if split.netloc:
        return False
    cleaned = url.lstrip(_LEADING_JUNK).translate(_REMOVED_CHARACTERS)
    start = len(split.scheme) + 1 if split.scheme else 0
    return cleaned.startswith("//", start)


def _split_url(url: str, context_scheme: str) -> tuple[SplitResult, str, str]:
    """
    Split a URL string into its raw (still encoded) parts.

    :param url: the URL string
    :param context_scheme: the scheme a URL without one is going to get; it
                           decides whether its path can have path params
    :return: the split result, the path without path params and the
             path params
    :raises ValueError: if urllib cannot parse the URL (invalid port, broken
                        IPv6 literal, ...); the message never contains the
                        password
    """
    try:
        split = urlsplit(url)
        # urllib validates the port only when it is asked for it
        _ = split.port
    except ValueError as error:
        # "from None": the original error may quote the password
        raise ValueError(_redact_userinfo(str(error), url)) from None

    if (split.scheme or context_scheme) in _PATH_PARAMS_SCHEMES:
        path, params = _split_path_params(split.path)
    else:
        path, params = split.path, ""
    return split, path, params


def _remove_dot_segments(path: str) -> str:
    """
    Remove "." and ".." segments exactly as described in RFC 3986, section
    5.2.4. Meant for the path of an absolute URL: a ".." that cannot be
    resolved is dropped.

    :param path: the path to resolve
    :return: the path without any "." or ".." segments
    """
    input_ = path
    output: list[str] = []
    while input_:
        if input_.startswith("../"):
            input_ = input_[3:]
        elif input_.startswith("./"):
            input_ = input_[2:]
        elif input_.startswith("/./"):
            input_ = "/" + input_[3:]
        elif input_ == "/.":
            input_ = "/"
        elif input_.startswith("/../"):
            input_ = "/" + input_[4:]
            if output:
                output.pop()
        elif input_ == "/..":
            input_ = "/"
            if output:
                output.pop()
        elif input_ in (".", ".."):
            input_ = ""
        else:
            # move the first segment (incl. its leading "/") to the output
            start = 1 if input_.startswith("/") else 0
            next_slash = input_.find("/", start)
            if next_slash == -1:
                output.append(input_)
                input_ = ""
            else:
                output.append(input_[:next_slash])
                input_ = input_[next_slash:]
    return "".join(output)


def _resolve_dot_segments(path: str) -> str:
    """
    Remove "." and ".." segments from a path without changing what it refers
    to. For absolute paths the result is the one of RFC 3986, section 5.2.4
    (a ".." cannot climb above the root). Relative paths stay relative:
    leading ".." segments are kept as there is nothing to resolve them
    against, and a path that resolves to the current directory becomes "./"
    (not "", which would refer to the document itself).

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
    if resolved.startswith("/"):
        # an empty first segment is left ("a/..//b" is ".//b"): without the
        # "./" the relative path would have become an absolute one
        return "./" + resolved
    return resolved or ("./" if path else "")


def _normalize_path(path: str, *, strict: bool, last_is_literal: bool) -> str:
    """
    Remove the dot segments of a path.

    :param path: the raw path
    :param strict: use the algorithm of RFC 3986 to the letter (for absolute
                   URLs) instead of the one that keeps relative paths relative
    :param last_is_literal: the last segment has path params and hence is
                            not a dot segment even if it reads "." or ".."
                            ("/a/..;v=1")
    :return: the path without the dot segments that can be resolved
    """
    resolve = _remove_dot_segments if strict else _resolve_dot_segments
    if not last_is_literal:
        return resolve(path)
    head, slash, last = path.rpartition("/")
    resolved_head = resolve(head + slash)
    if resolved_head == "./":
        # only there to mark the current directory, the last segment does that
        resolved_head = ""
    return resolved_head + last


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

    Every part is an attribute that can be read and assigned. Assignments
    are validated: a value a part cannot have raises a ``ValueError`` (or a
    ``TypeError`` for a wrong type) right away, so a Url can always be
    rendered. ``None`` removes a part.

    Internally the parts are kept the way they are written in a URL, i.e.
    percent-encoded, which is what makes parsing and rendering an exact
    round trip. The attributes (``path``, ``fragment``, ``username``,
    ``password``) show and take the decoded, readable values;
    :py:attr:`raw_path` and :py:attr:`raw_fragment` give access to the
    encoded form where the difference matters.

    Urls are mutable and compare by their parts (see :py:meth:`__eq__`),
    hence they are not hashable: use ``str(url)`` as a dictionary key or
    set member.
    """

    # no __dict__: assigning to a misspelled attribute ("url.host = ...")
    # raises instead of silently doing nothing
    __slots__ = (
        "_fragment",
        "_hostname",
        "_password",
        "_path",
        "_path_params",
        "_port",
        "_query",
        "_scheme",
        "_username",
    )

    # the string parts hold the percent-encoded form
    _scheme: str
    _hostname: str | None
    _port: int | None
    _path: str
    _fragment: str
    _username: str | None
    _password: str | None
    _query: Params
    _path_params: Params

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
        Mind that, as in :py:func:`urllib.parse.urlsplit`, a hostname is only
        recognized after "//": "example.com/path" is a relative path, use
        "//example.com/path" or "https://example.com/path" — and
        "localhost:8080" is the scheme "localhost" with the path "8080".

        The parts of the `url` are kept as they are written, so rendering an
        unmodified Url gives the original string (see :py:meth:`as_str` for
        the few exceptions). The keyword arguments, like the attributes,
        take decoded, readable values ("my file.html", not "my%20file.html")
        without their delimiter (no leading "?" for the query, no "#" for
        the fragment) and are validated like an assignment to the attribute.

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
                         an IPv6 address is stored without its brackets. An
                         empty string stands for an empty authority
                         ("sqlite:///data.db"), ``None`` for none at all.
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
                            a part has a value it cannot have (see the
                            attributes), or if `url` cannot be parsed (invalid
                            port, broken IPv6 address, invalid hostname). The
                            message never contains the password.
        :raises TypeError: if `url` or a part is of the wrong type
        """
        if url is not None and not isinstance(url, str):
            hint = " (use its copy() method)" if isinstance(url, Url) else ""
            raise TypeError(f"url must be a str or None, not {type(url).__name__}{hint}")
        if authority is not _UNSET and (hostname is not _UNSET or port is not _UNSET):
            raise ValueError("Cannot specify both authority and hostname or port")

        # a scheme given as keyword argument also decides how a base url
        # without a scheme is read (path params, form encoding of the query)
        context_scheme = "" if scheme is _UNSET else _check_scheme(scheme)
        self._load(url or "", context_scheme)

        # the properties validate; the scheme goes first because the query
        # setter looks at it
        if scheme is not _UNSET:
            self.scheme = scheme
        if authority is not _UNSET:
            # replaces hostname and port: an authority without a port
            # removes the port of the base url
            self.authority = authority
        if hostname is not _UNSET:
            self.hostname = hostname
        if port is not _UNSET:
            self.port = port
        if path is not _UNSET:
            self.path = path
        if fragment is not _UNSET:
            self.fragment = fragment
        if username is not _UNSET:
            self.username = username
        if password is not _UNSET:
            self.password = password
        if query is not _UNSET:
            self.query = query
        if path_params is not _UNSET:
            self.path_params = path_params

    def _load(self, url: str, context_scheme: str) -> None:
        """
        Set all parts from a URL string.

        :param url: the URL string to parse
        :param context_scheme: the scheme the URL is going to get if it has
                               none itself, see :py:func:`_split_url`
        :raises ValueError: if the URL cannot be parsed
        """
        split, raw_path, raw_params = _split_url(url, context_scheme)

        # urllib only recognizes valid schemes and lowercases them
        self._scheme = split.scheme

        hostname = split.hostname
        if hostname:
            # urllib strips the brackets of IP literals: an IPv6 address is
            # recognizable by its colons, an IPvFuture literal is not
            if "[" in split.netloc and ":" not in hostname:
                hostname = f"[{hostname}]"
            else:
                hostname = unquote(hostname)
        elif _has_empty_authority(url, split):
            hostname = ""
        else:
            # urllib gives "" for a netloc that only has userinfo or a port
            hostname = None
        self._hostname = _check_hostname(hostname)
        self._port = split.port

        # the encoded form is kept; _requote only repairs what could not be
        # rendered (spaces, non-ASCII characters, stray "%")
        self._path = _requote(raw_path, _PATH_SAFE)
        self._fragment = _requote(split.fragment, _FRAGMENT_SAFE)
        self._username = _requote(split.username, _USERINFO_SAFE) if split.username else None
        self._password = _requote(split.password, _USERINFO_SAFE) if split.password else None

        form_encoding = (split.scheme or context_scheme) in _FORM_ENCODED_SCHEMES
        self._query = Params(split.query, form_encoding=form_encoding)
        # path params use ";" to separate the k=v pairs from the path and
        # each other and, being part of the path, no form encoding
        self._path_params = Params(raw_params, separator=";", form_encoding=False)

    @property
    def scheme(self) -> str:
        """
        The scheme ("https", "ftp", ...), "" if the URL has none. Always
        lowercase; assigning ``None`` removes it.

        :raises ValueError: when assigning something that is not a valid
                            scheme, e.g. "https://"
        """
        return self._scheme

    @scheme.setter
    def scheme(self, value: str | None) -> None:
        self._scheme = _check_scheme(value)

    @property
    def hostname(self) -> str | None:
        """
        The hostname, ``None`` if the URL has none. Always lowercase and
        readable (not IDNA-encoded); an IPv6 address is held without the
        brackets it has inside a URL ("::1", not "[::1]"). Assigning
        ``None`` removes it.

        An empty string is an *empty authority*: the "//" is there, but no
        host — as in "file:///etc/hosts" or "sqlite:///data.db", which are
        not the same as "file:/etc/hosts" and "sqlite:/data.db" (hostname
        ``None``).

        Replacing the hostname keeps username and password — remove them as
        well if the new host must not receive the credentials.

        :raises ValueError: when assigning a hostname with characters it
                            cannot have (whitespace, "/", "?", "#", "@"), a
                            ":" that is not part of an IPv6 address (a port
                            belongs in :py:attr:`port`), or one that cannot
                            be IDNA-encoded
        """
        return self._hostname

    @hostname.setter
    def hostname(self, value: str | None) -> None:
        self._hostname = _check_hostname(value)

    @property
    def port(self) -> int | None:
        """
        The port, ``None`` if the URL has none.

        :raises TypeError: when assigning something that is not an int
        :raises ValueError: when assigning a port outside of 0-65535
        """
        return self._port

    @port.setter
    def port(self, value: int | None) -> None:
        self._port = _check_port(value)

    @property
    def path(self) -> str:
        """
        The decoded path, "" if the URL has none. Assigning takes a decoded
        path as well and encodes it; ``None`` removes it.

        Decoding is convenient but not reversible: an escaped "/" ("%2F",
        part of a segment) reads like a real one (a segment separator), and
        escapes that are not valid UTF-8 read as the replacement character.
        Use :py:attr:`raw_path` where that matters.
        """
        return unquote(self._path)

    @path.setter
    def path(self, value: str | None) -> None:
        self._path = quote(_text(value, "path"), safe=_PATH_SAFE)

    @property
    def raw_path(self) -> str:
        """
        The path as it is written in the URL, i.e. percent-encoded
        ("/a%2Fb/my%20file"). Assigning takes an encoded path: its escapes
        are kept as they are, characters that cannot be raw in a path are
        encoded.
        """
        return self._path

    @raw_path.setter
    def raw_path(self, value: str | None) -> None:
        self._path = _requote(_text(value, "raw_path"), _PATH_SAFE)

    @property
    def fragment(self) -> str:
        """
        The decoded fragment (without the "#"), "" if the URL has none.
        Assigning takes a decoded fragment as well; ``None`` removes it.
        """
        return unquote(self._fragment)

    @fragment.setter
    def fragment(self, value: str | None) -> None:
        self._fragment = quote(_text(value, "fragment"), safe=_FRAGMENT_SAFE)

    @property
    def raw_fragment(self) -> str:
        """
        The fragment as it is written in the URL, i.e. percent-encoded.
        Assigning takes an encoded fragment and keeps its escapes.
        """
        return self._fragment

    @raw_fragment.setter
    def raw_fragment(self, value: str | None) -> None:
        self._fragment = _requote(_text(value, "raw_fragment"), _FRAGMENT_SAFE)

    @property
    def username(self) -> str | None:
        """
        The decoded username, ``None`` if the URL has none. Assigning
        ``None`` or "" removes it.
        """
        return None if self._username is None else unquote(self._username)

    @username.setter
    def username(self, value: str | None) -> None:
        self._username = quote(_text(value, "username"), safe=_USERINFO_SAFE) or None

    @property
    def password(self) -> str | None:
        """
        The decoded password, ``None`` if the URL has none. It may be set
        without a username ("redis://:secret@localhost"). Assigning ``None``
        or "" removes it.
        """
        return None if self._password is None else unquote(self._password)

    @password.setter
    def password(self, value: str | None) -> None:
        self._password = quote(_text(value, "password"), safe=_USERINFO_SAFE) or None

    @property
    def query(self) -> Params:
        """
        The query parameters as a :py:class:`~action0.url.params.Params`
        instance; manipulate it in place. Assigning anything a Params can be
        built from (a query string, a mapping, an iterable of tuples,
        another Params) or ``None`` replaces all query parameters; the
        assigned value is copied, never shared.

        The query is form-encoded ("+" stands for a space) for the web
        schemes "http", "https", "ws" and "wss" and for URLs without a
        scheme. For every other scheme — "mailto" for example — a "+" is a
        plus sign and a space is written as "%20". That is decided by the
        scheme the URL has when the query is parsed or assigned; set
        ``url.query.form_encoding`` to override it.

        :raises TypeError: when assigning something a Params cannot be
                           built from
        """
        return self._query

    @query.setter
    def query(self, value: ParamTypes | None) -> None:
        self._query = Params(value, form_encoding=self._scheme in _FORM_ENCODED_SCHEMES)

    @property
    def path_params(self) -> Params:
        """
        The path parameters (";key=value" after the path) as a
        :py:class:`~action0.url.params.Params` instance with a ";" separator
        and without form encoding; manipulate it in place. Assigning anything
        a Params can be built from or ``None`` replaces all path parameters;
        the assigned value is copied, never shared.

        They belong to the last path segment. When a URL string is parsed
        they are only split off the path for the schemes that are known to
        use them ("http", "https", "ftp", ... and URLs without a scheme);
        for all other schemes a ";" is simply part of the path.

        :raises TypeError: when assigning something a Params cannot be
                           built from
        """
        return self._path_params

    @path_params.setter
    def path_params(self, value: ParamTypes | None) -> None:
        self._path_params = Params(value, separator=";", form_encoding=False)

    @property
    def authority(self) -> str:
        """
        The "hostname:port" combination, just the hostname if no port is
        set. Unlike urllib's netloc it never contains the userinfo. The
        hostname is the readable one of :py:attr:`hostname` (not IDNA-encoded),
        an IPv6 address is in brackets ("[::1]:8080"). Assigning a string of
        the same form replaces hostname and port, ``None`` removes both (an
        empty string gives an empty authority, see :py:attr:`hostname`).

        Like for :py:attr:`hostname`, username and password are kept when
        the authority is replaced.

        :raises ValueError: when assigning a string with userinfo, or with
                            a hostname or port that is not valid (see
                            :py:attr:`hostname` and :py:attr:`port`)
        """
        host = self._hostname or ""
        if ":" in host and not host.startswith("["):
            # an IPv6 address, the brackets keep its colons apart from the
            # port separator
            host = f"[{host}]"
        if self._port is not None:
            return f"{host}:{self._port}"
        return host

    @authority.setter
    def authority(self, value: str | None) -> None:
        if value is None:
            self._hostname, self._port = None, None
            return
        if not isinstance(value, str):
            raise TypeError(f"authority must be a str or None, not {type(value).__name__}")
        hostname, port = _split_authority(value)
        # both are checked before the first one is assigned
        checked_hostname, checked_port = _check_hostname(hostname), _check_port(port)
        self._hostname, self._port = checked_hostname, checked_port

    @property
    def raw_authority(self) -> str:
        """
        The :py:attr:`authority` as it is written in the URL string — what
        :py:attr:`raw_path` is to :py:attr:`path`: a non-ASCII hostname is
        IDNA-encoded (punycode), an IPv6 address is in brackets, and the
        port follows if one is set. Like the authority it never contains
        the userinfo. This is the value of the ``Host`` header of an HTTP
        request for the URL.

        >>> url = Url("https://user:secret@bücher.example:8443/x")
        >>> url.authority
        'bücher.example:8443'
        >>> url.raw_authority
        'xn--bcher-kva.example:8443'

        It is "" for a URL without a hostname and port. Read-only: assign
        to :py:attr:`authority`, which takes the encoded form as well.
        """
        return self._encoded_authority()

    @property
    def request_target(self) -> str:
        """
        The target of an HTTP request for this URL in its usual form, the
        origin-form (:rfc:`9112`, section 3.2.1): the path, the path
        params and the query, spelled exactly as :py:meth:`as_str` spells
        them — percent escapes are neither decoded nor re-encoded, so the
        target of a signed URL is the one that was signed. Scheme,
        authority and fragment are not part of it.

        >>> Url("https://example.com/a%2Fb;v=1?sig=x%2By&flag#top").request_target
        '/a%2Fb;v=1?sig=x%2By&flag'

        The target is always an absolute path: "/" stands in for an empty
        path, and a relative path gets the "/" it would get behind a host.

        >>> Url("https://example.com?page=2").request_target
        '/?page=2'
        >>> Url("items/5").request_target
        '/items/5'

        It is the path as it is written behind an authority, whether the
        URL has one or not: the prefixes :py:meth:`as_str` puts in front
        of a path that would be read as a host or a scheme ("/.", "./")
        are not needed in a request line and not written.

        >>> Url(path="//files/x").as_str(), Url(path="//files/x").request_target
        ('/.//files/x', '//files/x')
        """
        parts = [self._encoded_path(with_authority=True) or "/"]
        path_params = self._path_params.as_str()
        if path_params:
            parts.append(f";{path_params}")
        query = self._query.as_str()
        if query:
            parts.append(f"?{query}")
        return "".join(parts)

    @property
    def parent(self) -> Self:
        """
        A copy of this URL with the last path segment — and the path params,
        which belong to it — removed; the other parts (also query and
        fragment) are kept. Like in pathlib, a trailing slash is ignored
        ("/a/b/" has the parent "/a") and the parent of the root is the root.
        """
        parent_path, slash, _ = self._path.rstrip("/").rpartition("/")
        if slash:
            new_path = parent_path or "/"
        else:
            # no slash left: the parent of a bare relative segment is empty,
            # the parent of the root stays the root
            new_path = "/" if self._path.startswith("/") else ""
        parent = self.copy(path_params=None)
        parent._path = new_path
        return parent

    @property
    def name(self) -> str:
        """
        The decoded last path segment (usually the file name); "" if the
        path is empty or ends with a "/" — unlike pathlib, a trailing slash
        is significant in a URL: "/a/b/" is a directory and has no file name.
        Assigning replaces the last segment; a "/" in the new name is
        encoded, as the name is a single segment.
        """
        return unquote(self._path.rpartition("/")[2])

    @name.setter
    def name(self, value: str) -> None:
        base, slash, _ = self._path.rpartition("/")
        self._path = f"{base}{slash}{quote(_text(value, 'name'), safe=_SEGMENT_SAFE)}"

    @property
    def suffix(self) -> str:
        """
        The file extension of :py:attr:`name` including the "."; "" if
        there is none. Follows :py:attr:`pathlib.PurePath.suffix` as of
        Python 3.14 (where a trailing dot counts as suffix: "." for "a.")
        on every Python version.
        """
        # leading dots are not a suffix: neither a dotfile (".hidden") nor
        # the dot segments "." and ".." have one
        name = self.name.lstrip(".")
        dot_index = name.rfind(".")
        return name[dot_index:] if dot_index >= 0 else ""

    def _has_authority(self) -> bool:
        """
        :return: whether any part of the authority (hostname, port,
                 username, password) is set
        """
        return (
            self._hostname is not None
            or self._port is not None
            or self._username is not None
            or self._password is not None
        )

    def _encoded_authority(self) -> str:
        """
        :return: hostname and port the way they are written in the URL
                 string, without the userinfo; "" if neither is set
        """
        authority = _encode_hostname(self._hostname) if self._hostname else ""
        if self._port is not None:
            authority = f"{authority}:{self._port}"
        return authority

    def _implies_authority(self) -> bool:
        """
        :return: whether the URL is rendered with an (empty) authority
                 although it has none: a file URL always has one, usually
                 an empty one ("file:///etc/hosts")
        """
        return self._scheme == "file" and (not self._path or self._path.startswith("/"))

    def _encoded_path(self, with_authority: bool) -> str:
        """
        The path as it has to be written so that the URL is parsed back the
        way it is meant.

        :param with_authority: whether the path follows an authority
        :return: the percent-encoded path
        """
        path = self._path
        if self._scheme in _PATH_PARAMS_SCHEMES:
            # a ";" in the last segment would be read as the start of the
            # path params
            head, slash, last = path.rpartition("/")
            if ";" in last:
                path = f"{head}{slash}{last.replace(';', '%3B')}"

        if with_authority:
            # behind an authority every path is absolute
            if path and not path.startswith("/"):
                path = f"/{path}"
        elif path.startswith("//"):
            # would be read as the start of an authority ("//evil.com/x")
            path = f"/.{path}"
        elif not self._scheme and ":" in path.partition("/")[0]:
            # the first segment of a relative path would be read as a scheme
            # ("javascript:alert(1)"), RFC 3986 section 4.2
            path = f"./{path}"
        return path

    def _render(self, *, redact_password: bool) -> str:
        """
        Assemble the URL string (RFC 3986, section 5.3).

        :param redact_password: write "***" instead of the password
        :return: the URL string
        """
        with_authority = self._has_authority() or self._implies_authority()
        authority = self._encoded_authority()
        # a password does not need a username ("redis://:secret@localhost")
        if self._username or self._password:
            userinfo = self._username or ""
            if self._password:
                userinfo = f"{userinfo}:{'***' if redact_password else self._password}"
            authority = f"{userinfo}@{authority}"

        path = self._encoded_path(with_authority)
        path_params = self._path_params.as_str()
        if path_params and with_authority and not path:
            # without the "/" the params would be read as part of the host
            path = "/"
        query = self._query.as_str()

        parts: list[str] = []
        if self._scheme:
            parts.append(f"{self._scheme}:")
        if with_authority:
            parts.append(f"//{authority}")
        parts.append(path)
        if path_params:
            parts.append(f";{path_params}")
        if query:
            parts.append(f"?{query}")
        if self._fragment:
            parts.append(f"#{self._fragment}")
        return "".join(parts)

    def as_str(self) -> str:
        """
        Assemble the (possibly modified) parts back into a URL string.

        A URL that was parsed from a string and not modified is rendered as
        it was written — escapes, the order and spelling of the query, all
        of it. Only these things are normalized: scheme and hostname are
        lowercased, characters that are not allowed in a URL are
        percent-encoded, and delimiters without content ("?", "#", the ":"
        of "user:@host") are left out. Parts that were assigned are encoded
        as needed.

        A non-ASCII hostname is IDNA-encoded (punycode) and an IPv6 address
        is put in brackets. The IDNA encoding is the one of Python's
        standard library (IDNA 2003), which differs from current browsers
        (IDNA 2008 / UTS 46) for a few characters: "straße.de" becomes
        "strasse.de". Assign the punycode form as hostname if that matters.

        A path that would be mistaken for something else is prefixed: a
        relative path with a ":" in its first segment gets a "./" ("a:b"
        would be the scheme "a") and a path starting with "//" on a URL
        without a host gets a "/." (it would name a host).

        :return: the string representation of the URL
        """
        return self._render(redact_password=False)

    def join(self, other: "str | Url") -> Self:
        """
        Resolve another, possibly relative, URL against this one — the way
        a link on a page is resolved. Implements the reference resolution
        of RFC 3986, section 5.2 and, unlike
        :py:func:`urllib.parse.urljoin`, works for every scheme.

        Example::

            >>> Url("https://example.com/a/b").join("c")
            Url(https://example.com/a/c)
            >>> Url("https://example.com/a/b").join("/x")
            Url(https://example.com/x)
            >>> Url("myapp://host/a/b").join("../c?d=1")
            Url(myapp://host/c?d=1)
            >>> Url("https://example.com/list?filter=x").join("?")
            Url(https://example.com/list)

        A reference given as string is read in the context of this URL: it
        is this URL's scheme that decides whether a ";" starts path params
        and whether its query is form-encoded.

        :param other: the URL to resolve against this one
        :return: a new Url of the same class as this one, this instance is
                 not modified
        :raises TypeError: if `other` is neither a string nor a Url
        :raises ValueError: if `other` is a string that cannot be parsed
        """
        if isinstance(other, Url):
            reference = other
            # an instance cannot tell an empty query from no query
            has_query = bool(reference._query)
            has_path = bool(reference._path or reference._path_params)
        elif isinstance(other, str):
            reference = Url.__new__(Url)
            reference._load(other, self._scheme)
            before_fragment = other.partition("#")[0]
            # "?" alone is a (present, empty) query that replaces this one
            has_query = "?" in before_fragment
            has_path = bool(reference._path) or ";" in before_fragment.partition("?")[0]
        else:
            raise TypeError(f"can only join a str or a Url, not {type(other).__name__}")

        target = self.copy()
        if reference._scheme or reference._has_authority():
            # an absolute URL replaces this one entirely, "//host/path"
            # keeps only the scheme
            if reference._scheme:
                target._scheme = reference._scheme
            target._hostname = reference._hostname
            target._port = reference._port
            target._username = reference._username
            target._password = reference._password
            path = reference._path
        elif not has_path:
            # "?query" / "#fragment" / "": same document
            if has_query:
                target._query = reference._query.copy()
            target._fragment = reference._fragment
            return target
        elif reference._path.startswith("/"):
            path = reference._path
        elif self._has_authority() and not self._path:
            path = f"/{reference._path}"
        else:
            # replace everything after the last "/" of this path
            path = self._path[: self._path.rfind("/") + 1] + reference._path

        target._path = _normalize_path(
            path,
            # the path of an absolute URL cannot keep unresolvable ".."
            strict=bool(target._scheme),
            last_is_literal=bool(reference._path_params),
        )
        target._path_params = reference._path_params.copy()
        target._query = reference._query.copy()
        target._fragment = reference._fragment
        return target

    def __truediv__(self, segment: str) -> Self:
        """
        Return a copy with the segment(s) appended to the path, always
        joined with exactly one "/". The other parts (also query and
        fragment) are kept; path params stay with the segment they belong
        to. A relative URL without a path stays relative.

        Example::

            >>> Url("https://example.com") / "api" / "v2"
            Url(https://example.com/api/v2)
            >>> Url() / "api" / "v2"
            Url(api/v2)

        :param segment: the (decoded) path segment(s) to append
        :return: a new Url, this instance is not modified
        """
        if not isinstance(segment, str):
            return NotImplemented
        appended = self.copy()
        base = self._path
        if self._path_params:
            # they belong to the segment that is the last one no more; in an
            # inner segment a ";" is plain text
            base = f"{base};{self._path_params.as_str()}"
            appended.path_params = None
        encoded = quote(segment.lstrip("/"), safe=_PATH_SAFE)
        if base or self._has_authority():
            appended._path = f"{base.rstrip('/')}/{encoded}"
        else:
            # nothing to append to: a leading "/" would make the path absolute
            appended._path = encoded
        return appended

    def copy(
        self,
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
    ) -> Self:
        """
        An independent copy of this URL, optionally with parts replaced.
        ``None`` (or "" / an empty mapping) as value removes the part. The
        replacements are validated like assignments to the attributes.

        Example::

            >>> url = Url("https://example.com:8443/index.html")
            >>> url.copy(scheme="http", port=None)
            Url(http://example.com/index.html)

        The copy is made without calling the constructor, so it also works
        for subclasses with a different constructor; attributes a subclass
        adds are copied (shallowly) as well.

        :return: a new Url of the same class, this instance is not modified
        :raises ValueError: if authority is combined with hostname or port,
                            or a part has a value it cannot have
        :raises TypeError: if a part is of the wrong type
        """
        if authority is not _UNSET and (hostname is not _UNSET or port is not _UNSET):
            raise ValueError("Cannot specify both authority and hostname or port")

        cls = type(self)
        copied = cls.__new__(cls)
        # attributes of subclasses without __slots__
        instance_dict: dict[str, Any] | None = getattr(self, "__dict__", None)
        if instance_dict:
            copied.__dict__.update(instance_dict)
        copied._scheme = self._scheme
        copied._hostname = self._hostname
        copied._port = self._port
        copied._path = self._path
        copied._fragment = self._fragment
        copied._username = self._username
        copied._password = self._password
        copied._query = self._query.copy()
        copied._path_params = self._path_params.copy()

        if scheme is not _UNSET:
            copied.scheme = scheme
        if authority is not _UNSET:
            copied.authority = authority
        if hostname is not _UNSET:
            copied.hostname = hostname
        if port is not _UNSET:
            copied.port = port
        if path is not _UNSET:
            copied.path = path
        if fragment is not _UNSET:
            copied.fragment = fragment
        if username is not _UNSET:
            copied.username = username
        if password is not _UNSET:
            copied.password = password
        if query is not _UNSET:
            copied.query = query
        if path_params is not _UNSET:
            copied.path_params = path_params
        return copied

    def __copy__(self) -> Self:
        # a shallow copy sharing the Params would not be a usable Url
        return self.copy()

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        copied = self.copy()
        instance_dict: dict[str, Any] | None = getattr(self, "__dict__", None)
        if instance_dict:
            copied.__dict__.update(copy.deepcopy(instance_dict, memo))
        return copied

    def origin(self) -> Self:
        """
        The origin — scheme, hostname and port only — e.g. for same-origin
        comparisons or as a base to build new URLs on. The default port of
        the scheme is left out, so that "https://example.com:443/a" and
        "https://example.com/b" have the same origin.

        :return: a new Url of the same class with only scheme, hostname and
                 port set
        """
        origin = self.copy(
            username=None, password=None, path=None, path_params=None, query=None, fragment=None
        )
        if origin._port is not None and _DEFAULT_PORTS.get(origin._scheme) == origin._port:
            origin._port = None
        return origin

    def normalize(self) -> Self:
        """
        A normalized copy of this URL (RFC 3986, section 6.2.2 and 6.2.3):
        the scheme's default port removed, percent escapes brought into
        their canonical form (escapes of unreserved characters decoded, hex
        digits uppercased), "." and ".." path segments resolved, and the
        path made absolute if there is an authority (an empty path becomes
        "/"). Scheme and hostname are always lowercase anyway. The path of a
        relative URL stays relative: "a/../b" becomes "b", leading ".."
        segments are kept. An escaped "/" ("%2F") is not a segment
        separator and never takes part in resolving ".." segments.

        Example::

            >>> Url("https://example.com:443/a/./b/../c").normalize()
            Url(https://example.com/a/c)

        :return: a new Url, this instance is not modified
        """
        normalized = self.copy()
        if (
            normalized._port is not None
            and _DEFAULT_PORTS.get(normalized._scheme) == normalized._port
        ):
            normalized._port = None

        # canonical first: "%2E%2E" is a ".." segment as well
        path = _canonical(self._path)
        # decided before the port is removed: the URL had an authority
        if (self._has_authority() or self._implies_authority()) and not path.startswith("/"):
            # behind an authority every path is absolute, as_str() renders it so
            path = f"/{path}"
        normalized._path = _normalize_path(
            path, strict=False, last_is_literal=bool(self._path_params)
        )
        normalized._fragment = _canonical(self._fragment)
        if self._username is not None:
            normalized._username = _canonical(self._username)
        if self._password is not None:
            normalized._password = _canonical(self._password)
        return normalized

    def as_dict(self) -> dict[str, Any]:
        """
        The URL parts as a plain dictionary (query and path params as
        dictionaries of value lists), e.g. for debugging or serialization.
        The values are the decoded ones of the attributes. Contains the real
        password — use repr() for a redacted view.

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
        return bool(self._scheme)

    def is_relative(self) -> bool:
        """
        :return: whether the URL has no scheme, i.e. is a relative reference
                 that needs a base URL (see :py:meth:`join`) to be resolved
        """
        return not self.is_absolute()

    def _comparison_key(self) -> tuple[object, ...]:
        """
        :return: the parts in the form two equivalent URLs have in common
        """
        with_authority = self._has_authority() or self._implies_authority()
        if self._hostname is not None:
            # the form the hostname has in the URL: IDNA-encoded
            hostname: str | None = _encode_hostname(self._hostname)
        else:
            # "" (an empty authority) is not the same as None (no authority)
            hostname = "" if with_authority and not self._has_authority() else None
        return (
            self._scheme,
            None if self._username is None else _canonical(self._username),
            None if self._password is None else _canonical(self._password),
            hostname,
            self._port,
            # the form the path has in the URL, e.g. absolute behind a host
            _canonical(self._encoded_path(with_authority)),
            _canonical(self._fragment),
        )

    def __eq__(self, other: object) -> bool:
        """
        Two Urls are equal if all their parts are equivalent, which they are
        if they are rendered the same apart from the spelling of percent
        escapes: "%7E" equals "~" and "%c3%a4" equals "%C3%A4", a hostname
        equals its IDNA-encoded form. An escaped reserved character does
        *not* equal the raw one — "/a%2Fb" (one segment) is a different path
        than "/a/b" (two segments).

        The order of the names of query and path parameters doesn't matter
        (``?a=1&b=2`` equals ``?b=2&a=1``), the order of multiple values of
        the same name does. Nothing else is normalized: use
        :py:meth:`normalize` first to compare regardless of default ports
        or dot segments.

        :param other: the Url to compare with
        :return: whether the URLs are equal
        """
        if not isinstance(other, Url):
            return NotImplemented
        return (
            self._comparison_key() == other._comparison_key()
            and self._path_params == other._path_params
            and self._query == other._query
        )

    def __str__(self) -> str:
        return self.as_str()

    def __repr__(self) -> str:
        """
        Like the URL string, but with the password replaced by ``***`` so that
        it does not leak into logs and tracebacks. Only the password part is
        redacted: a token given as *username*
        ("https://token@github.com/...") or inside the query is shown.
        """
        try:
            rendered = self._render(redact_password=True)
        except Exception:  # repr() must never raise, whatever state a subclass got into
            rendered = "<unrenderable>"
        return f"{self.__class__.__name__}({rendered})"
