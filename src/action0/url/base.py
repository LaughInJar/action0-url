import logging
from typing import Any
from urllib.parse import ParseResult
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.parse import urlunparse

from action0.url.params import Params
from action0.url.params import ParamTypes

log = logging.getLogger(__name__)


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
        self.path = path or parse_result.path
        self.fragment = fragment or parse_result.fragment
        self.username = username or parse_result.username
        self.password = password or parse_result.password
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

    def as_str(self) -> str:
        """
        Assemble the (possibly modified) parts back into a URL string.

        :return: the string representation of the URL
        """
        # the authority optionally has the port, username and password
        authority = self.hostname or ""
        if self.port:
            authority = f"{authority}:{self.port}"

        if self.username:
            if self.password:
                authority = f"{self.username}:{self.password}@{authority}"
            else:
                authority = f"{self.username}@{authority}"
        elif self.password:
            log.warning("password given but no username, password is discarded!")

        # urlunparse seems to be badly supported by the type-checker
        parts = (
            self.scheme,
            authority,
            self.path,
            self.path_params.as_str(),
            self.query.as_str(),
            self.fragment,
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
