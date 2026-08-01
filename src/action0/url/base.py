import logging
from urllib.parse import ParseResult
from urllib.parse import urlparse
from urllib.parse import urlunparse

from action0.url.params import Params
from action0.url.params import ParamTypes

log = logging.getLogger(__name__)


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
            # split "hostname:port" on the last ":" and only if digits follow it,
            # so IPv6 literals like "[::1]" (colons but no port) stay intact
            host_part, sep, port_part = authority.rpartition(":")
            if sep and port_part.isdigit():
                hostname = host_part
                port = int(port_part)
            else:
                hostname = authority

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

    def __str__(self) -> str:
        return self.as_str()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.as_str()})"
