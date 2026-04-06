import logging
from urllib.parse import ParseResult
from urllib.parse import urlparse
from urllib.parse import urlunparse

from action0.url.params import ParamTypes
from url.params import Params

log = logging.getLogger(__name__)


class Url:
    """
    Python presentation of a parsed URL to allow easy manipulation of its
    parts.

    Example::

        >>> url = Url("https://www.example.com/path/filename.json?foo=bar")
        >>> url.query.set("foo", "baz")
        >>> url.as_str()
        "https://www.example.com/path/filename.json?foo=baz"
        >>> url.query.add("a", "b")
        >>> url.as_str()
        "https://www.example.com/path/filename.json?foo=baz&a=b"
        >>> # allow params with multiple values
        >>> url.query.add("foo", "123")
        >>> url.as_str()
        "https://www.example.com/path/filename.json?foo=baz&foo=123&a=b"
        >>> url.hostname = "action0.com"
        >>> url.port = "8443"
        >>> url.path = "/public/index.html"
        >>> url.username = "user"
        >>> url.password = "pass"
        >>> url.fragment = "fragment"
        >>> url.as_str()
        "https://user:pass@action0.com:8443/public/index.html?foo=baz&foo=123&a=b#fragment"

    Based on the named tuple that :py:meth:`urllib.parse.urlparse` returns.
    """

    def __init__(
        self,
        url: str = None,
        *,
        scheme: str = None,
        hostname: str = None,
        path: str = None,
        query: ParamTypes = None,
        path_params: ParamTypes = None,
        fragment: str = None,
        username: str = None,
        password: str = None,
        port: int = None,
        authority: str = None,
    ):
        """
        If a `url` is given it will use this as base and other
        parameters will replace/overwrite the parts of the url string.

        Example::

            >>> url = Url("https://www.example.com/path/filename.json")
            >>> url.as_str()
            "https://www.example.com/path/filename.json"
            >>> url = Url("https://www.example.com/path/filename.json", path="/hello/world.html")
            >>> url.as_str()
            "https://www.example.com/hello/world.html
            >>> url = Url("https://www.example.com?foo=bar", query={"bar": "baz"})
            >>> url.as_str()
            "https://www.example.com?bar=baz


        :param url: the optional string representation of a URL to use as base
        :param scheme: the url scheme, e.g. https, ftps, etc.
        :param hostname: the hostname (domain incl. subdomain, or IP-Address, etc.)
        :param path: the path to the file (including the file's name)
        :param query: the query parameters
        :param path_params: the file parameters, k=v pairs after the path separeted with a ';'
                       (not commonly used, maybe you saw something like
                       'https://example.com/path/file.html;jsessionid=1234')
        :param fragment: everthing after the '#' usually only interpreted by the client
        :param username: if the username / password is part of the URL, e.g.
                         'https://user:pass@example.com/'
        :param password:  if the username / password is part of the URL, e.g.
                         'https://user:pass@example.com/'
        :param port: the port to connect to
        :param authority: also known as netloc, a combination of hostname and port and
                          hence can't be combined with hostname or port.
        """
        if authority:
            if hostname or port:
                raise ValueError("Cannot specify both authority and hostname or port")
            hostname, post = authority.rsplit(":", 1)

        if url is not None:
            parse_result = urlparse(url, scheme="https")
        else:
            parse_result = ParseResult(
                netloc=None,
                path=None,
                fragment=None,
                username=None,
                password=None,
                scheme=None,
                hostname=None,
                port=None,
                params=None,
                query=None,
            )

        self.scheme = scheme or parse_result.scheme
        self.hostname = hostname or parse_result.hostname
        self.port = port or parse_result.port
        self.path = path or parse_result.path
        self.fragment = fragment or parse_result.fragment
        self.username = username or parse_result.username
        self.password = password or parse_result.password
        self.query = Params(query or parse_result.query or "")
        self.path_params = path_params or parse_result.params or ""

    def as_str(self):
        """

        :return:
        """
        # the authority optionally has the port, username and password
        authority = self.hostname
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
            self.path_params,
            self.query.as_str(),
            self.fragment,
        )
        return str(urlunparse(parts))

    def __str__(self):
        return self.as_str()

    def __repr__(self):
        return f"{self.__class__.__name__}({self.as_str()})"
