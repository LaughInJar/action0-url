import logging
from typing import Any
from urllib.parse import ParseResult
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.parse import urlunparse

from action0.url.params import Params
from action0.url.params import ParamTypes

log = logging.getLogger(__name__)

# the default ports normalize() removes for the respective scheme
_DEFAULT_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443, "ftp": 21}

# characters that stay raw when percent-encoding a part (on top of quote()'s
# always-safe unreserved characters): RFC 3986 pchar minus the delimiters
# that would change how the URL is parsed back
_PATH_SAFE = "/:@!$&'()*+,="  # no ";", it starts the path params
_FRAGMENT_SAFE = "/?:@!$&'()*+,;="
_USERINFO_SAFE = "!$&'()*+,;="  # no ":", it separates username and password


def _split_authority(authority: str) -> tuple[str | None, int | None]:
    """
    Split an authority ("hostname" or "hostname:port") into its parts.

    :param authority: the authority string to split
    :return: a tuple of the hostname and the port
    """
    # split on the last ":" and only if digits follow it, so IPv6 literals
    # like "[::1]" (colons but no port) stay intact
    host_part, sep, port_part = authority.rpartition(":")
    if sep and port_part.isdigit():
        return host_part, int(port_part)
    return authority or None, None


def _encode_hostname(hostname: str) -> str:
    """
    IDNA-encode (punycode) a hostname if it contains non-ASCII characters.

    :param hostname: the hostname to encode
    :return: the ASCII representation of the hostname
    :raises UnicodeError: if the hostname cannot be IDNA-encoded
    """
    if hostname.isascii():
        return hostname
    return hostname.encode("idna").decode("ascii")


def _resolve_dot_segments(path: str) -> str:
    """
    Remove "." and ".." segments from a path as described in
    RFC 3986, section 5.2.4.

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


class Url:
    """
    Python presentation of a parsed URL to allow easy manipulation of its
    parts.

    Example::

        >>> url = Url("https://www.example.com/path/filename.json?foo=bar")
        >>> url.query.set("foo", "baz")
        >>> url.as_str()
        'https://www.example.com/path/filename.json?foo=baz'
        >>> url.query.add("a", "b")
        >>> url.as_str()
        'https://www.example.com/path/filename.json?foo=baz&a=b'
        >>> # allow params with multiple values
        >>> url.query.add("foo", "123")
        >>> url.as_str()
        'https://www.example.com/path/filename.json?foo=baz&foo=123&a=b'
        >>> url.hostname = "action0.com"
        >>> url.port = 8443
        >>> url.path = "/public/index.html"
        >>> url.username = "user"
        >>> url.password = "pass"
        >>> url.fragment = "fragment"
        >>> url.as_str()
        'https://user:pass@action0.com:8443/public/index.html?foo=baz&foo=123&a=b#fragment'

    Based on the named tuple that :py:meth:`urllib.parse.urlparse` returns.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        scheme: str | None = None,
        hostname: str | None = None,
        path: str | None = None,
        query: ParamTypes | None = None,
        path_params: ParamTypes | None = None,
        fragment: str | None = None,
        username: str | None = None,
        password: str | None = None,
        port: int | None = None,
        authority: str | None = None,
    ) -> None:
        """
        If a `url` is given it will use this as base and other
        parameters will replace/overwrite the parts of the url string.

        The parts of a parsed `url` are stored percent-decoded, i.e. the
        attributes hold the readable values ("my file.html", not
        "my%20file.html") and :py:meth:`as_str` encodes them again; values
        given as keyword arguments are expected to be unencoded as well.
        Be aware that an encoded "/" (%2F) inside a path segment is decoded
        like everything else and hence becomes a segment separator when the
        URL is rendered again.

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


        :param url: the optional string representation of a URL to use as base
        :param scheme: the url scheme, e.g. https, ftps, etc.
        :param hostname: the hostname (domain incl. subdomain, or IP-Address, etc.)
        :param path: the path to the file (including the file's name)
        :param query: the query parameters
        :param path_params: the file parameters, k=v pairs after the path separated with a ';'
                       (not commonly used, maybe you saw something like
                       'https://example.com/path/file.html;jsessionid=1234')
        :param fragment: everything after the '#' usually only interpreted by the client
        :param username: if the username / password is part of the URL, e.g.
                         'https://user:pass@example.com/'
        :param password:  if the username / password is part of the URL, e.g.
                         'https://user:pass@example.com/'
        :param port: the port to connect to
        :param authority: also known as netloc, a combination of hostname and port and
                          hence can't be combined with hostname or port.
        :raises ValueError: if authority is combined with hostname or port
        """
        if authority:
            if hostname or port:
                raise ValueError("Cannot specify both authority and hostname or port")
            hostname, port = _split_authority(authority)

        if url is not None:
            parse_result = urlparse(url, scheme="https")
        else:
            # an all-empty parse result so the lookups below fall through to
            # the keyword arguments (and "" for the unset string parts)
            parse_result = ParseResult(
                scheme="", netloc="", path="", params="", query="", fragment=""
            )

        self.scheme = scheme or parse_result.scheme
        self.hostname = hostname or parse_result.hostname
        self.port = port or parse_result.port
        # parsed parts are percent-decoded here and re-encoded in as_str();
        # the attributes always hold the readable values
        self.path = path or unquote(parse_result.path)
        self.fragment = fragment or unquote(parse_result.fragment)
        parsed_username = parse_result.username
        self.username = username or (unquote(parsed_username) if parsed_username else None)
        parsed_password = parse_result.password
        self.password = password or (unquote(parsed_password) if parsed_password else None)
        self.query = Params(query or parse_result.query or "")
        # path params use ";" to separate the k=v pairs from the path and each other
        self.path_params = Params(path_params or parse_result.params or "", separator=";")

    @property
    def authority(self) -> str:
        """
        The "hostname:port" combination (also known as netloc), just the
        hostname if no port is set. Assigning a string of the same form
        replaces hostname and port.
        """
        host = self.hostname or ""
        if self.port:
            return f"{host}:{self.port}"
        return host

    @authority.setter
    def authority(self, value: str) -> None:
        self.hostname, self.port = _split_authority(value)

    @property
    def parent(self) -> "Url":
        """
        A copy of this URL with the last path segment removed; the other
        parts are kept. Like in pathlib, the parent of the root is the root.
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
        empty or ends with a "/". Assigning replaces the last segment.
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
        "" if there is none.
        """
        name = self.name
        dot_index = name.rfind(".")
        # a name that is only a dotfile (".hidden") has no suffix
        return name[dot_index:] if dot_index > 0 else ""

    def as_str(self) -> str:
        """
        Assemble the (possibly modified) parts back into a URL string.
        The parts are percent-encoded as needed and a non-ASCII hostname
        is IDNA-encoded (punycode).

        :return: the string representation of the URL
        :raises UnicodeError: if the hostname cannot be IDNA-encoded
        """
        # the authority optionally has the port, username and password
        authority = _encode_hostname(self.hostname) if self.hostname else ""
        if self.port:
            authority = f"{authority}:{self.port}"

        if self.username:
            userinfo = quote(self.username, safe=_USERINFO_SAFE)
            if self.password:
                userinfo = f"{userinfo}:{quote(self.password, safe=_USERINFO_SAFE)}"
            authority = f"{userinfo}@{authority}"
        elif self.password:
            log.warning("password given but no username, password is discarded!")

        # urlunparse seems to be badly supported by the type-checker
        parts = (
            self.scheme,
            authority,
            quote(self.path, safe=_PATH_SAFE),
            self.path_params.as_str(),
            self.query.as_str(),
            quote(self.fragment, safe=_FRAGMENT_SAFE),
        )
        return str(urlunparse(parts))

    def join(self, other: "str | Url") -> "Url":
        """
        Resolve another, possibly relative, URL against this one — like a
        browser resolves a link on a page — wrapping
        :py:func:`urllib.parse.urljoin`.

        Example::

            >>> Url("https://example.com/a/b").join("c")
            Url(https://example.com/a/c)
            >>> Url("https://example.com/a/b").join("/x")
            Url(https://example.com/x)

        :param other: the URL to resolve against this one
        :return: a new Url, this instance is not modified
        """
        return Url(urljoin(self.as_str(), str(other)))

    def __truediv__(self, segment: str) -> "Url":
        """
        Return a copy with the segment(s) appended to the path, always
        joined with exactly one "/".

        Example::

            >>> Url("https://example.com") / "api" / "v2"
            Url(https://example.com/api/v2)

        :param segment: the path segment(s) to append
        :return: a new Url, this instance is not modified
        """
        copied = self.copy()
        copied.path = f"{self.path.rstrip('/')}/{segment.lstrip('/')}"
        return copied

    def copy(self, **overrides: Any) -> "Url":
        """
        An independent copy of this URL, optionally with parts replaced.

        Example::

            >>> url = Url("https://example.com:8443/index.html")
            >>> url.copy(scheme="http", port=None)
            Url(http://example.com/index.html)

        :param overrides: any URL part accepted by the constructor
        :return: a new Url, this instance is not modified
        :raises TypeError: on part names the constructor does not know
        :raises ValueError: if authority is combined with hostname or port
        """
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
        return Url(**parts)

    def origin(self) -> "Url":
        """
        The origin — scheme, hostname and port only — e.g. for same-origin
        comparisons or as a base to build new URLs on.

        :return: a new Url with only scheme, hostname and port set
        """
        return Url(scheme=self.scheme, hostname=self.hostname, port=self.port)

    def normalize(self) -> "Url":
        """
        A normalized copy of this URL (RFC 3986 style): scheme and hostname
        lowercased, the scheme's default port removed, "." and ".." path
        segments resolved, and an empty path becomes "/" if there is a
        hostname.

        Example::

            >>> Url("https://example.com:443/a/./b/../c").normalize()
            Url(https://example.com/a/c)

        :return: a new Url, this instance is not modified
        """
        scheme = self.scheme.lower()
        hostname = self.hostname.lower() if self.hostname else self.hostname
        port = self.port
        if port is not None and _DEFAULT_PORTS.get(scheme) == port:
            port = None
        path = _resolve_dot_segments(self.path)
        if hostname and not path:
            path = "/"
        return self.copy(scheme=scheme, hostname=hostname, port=port, path=path)

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
        :return: whether the URL has a hostname
        """
        return self.hostname is not None

    def is_relative(self) -> bool:
        """
        :return: whether the URL has no hostname
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
