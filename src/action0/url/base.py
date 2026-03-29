from urllib.parse import ParseResult
from urllib.parse import urlparse

from action0.url.params import ParamTypes
from url.params import Params


class URL:
    """
    Python presentation of a parsed URL.

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
        params: ParamTypes = None,
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
        :param params: the file parameters, k=v pairs after the path separeted with a ';'
                       (not commonly used, maybe you saw something like
                       'https://example.com/path/file.html;jsessionid=1234?foo=bar')
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
        self.params = Params(params or parse_result.params or "")
