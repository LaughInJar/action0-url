import unittest

from action0.url import Url


class UrlParseTestCase(unittest.TestCase):
    """
    tests for parsing a URL string with :py:class:`action0.url.base.Url`
    """

    def test_full_url_parts(self) -> None:
        """
        Test that every part of a URL ends up in the right attribute.
        """
        url = Url("https://user:pass@www.example.com:8443/path/file.json;v=1?foo=bar#frag")
        self.assertEqual(url.scheme, "https")
        self.assertEqual(url.username, "user")
        self.assertEqual(url.password, "pass")
        self.assertEqual(url.hostname, "www.example.com")
        self.assertEqual(url.port, 8443)
        self.assertEqual(url.path, "/path/file.json")
        self.assertEqual(url.path_params.as_dict(), {"v": ["1"]})
        self.assertEqual(url.query.as_dict(), {"foo": ["bar"]})
        self.assertEqual(url.fragment, "frag")

    def test_round_trip(self) -> None:
        """
        Test that parsing and re-assembling reproduces the original string.
        """
        url_str = "https://user:pass@www.example.com:8443/path/file.json;v=1?foo=bar#frag"
        self.assertEqual(Url(url_str).as_str(), url_str)

    def test_kwargs_override_url_parts(self) -> None:
        """
        Test that keyword arguments replace the corresponding parts of the
        base URL string.
        """
        url = Url("https://www.example.com/path/filename.json", path="/hello/world.html")
        self.assertEqual(url.as_str(), "https://www.example.com/hello/world.html")

        url = Url("https://www.example.com?foo=bar", query={"bar": "baz"})
        self.assertEqual(url.as_str(), "https://www.example.com?bar=baz")

    def test_query_manipulation(self) -> None:
        """
        Test the query manipulation flow from the README.
        """
        url = Url("https://www.example.com/path/filename.json?foo=bar")
        url.query.set("foo", "baz")
        self.assertEqual(url.as_str(), "https://www.example.com/path/filename.json?foo=baz")
        url.query.add("a", "b")
        self.assertEqual(url.as_str(), "https://www.example.com/path/filename.json?foo=baz&a=b")
        url.query.add("foo", "123")
        self.assertEqual(
            url.as_str(), "https://www.example.com/path/filename.json?foo=baz&foo=123&a=b"
        )

    def test_attribute_assignment(self) -> None:
        """
        Test that assigning to the part attributes changes the output.
        """
        url = Url("https://www.example.com/path/filename.json?foo=bar")
        url.hostname = "action0.com"
        url.port = 8443
        url.path = "/public/index.html"
        url.username = "user"
        url.password = "pass"
        url.fragment = "fragment"
        self.assertEqual(
            url.as_str(), "https://user:pass@action0.com:8443/public/index.html?foo=bar#fragment"
        )


class UrlConstructTestCase(unittest.TestCase):
    """
    tests for constructing a :py:class:`action0.url.base.Url` from parts
    """

    def test_from_parts(self) -> None:
        """
        Test the construction flow from the README.
        """
        url = Url(
            scheme="https",
            hostname="example.com",
            path="index.html",
            query={"a": "b", "foo": ["bar", "baz"]},
            port=1234,
        )
        self.assertEqual(url.as_str(), "https://example.com:1234/index.html?a=b&foo=bar&foo=baz")

        url.username = "myuser"
        url.port = None
        self.assertEqual(url.as_str(), "https://myuser@example.com/index.html?a=b&foo=bar&foo=baz")

    def test_empty(self) -> None:
        """
        Test that a Url without any parts renders as an empty string.
        """
        self.assertEqual(str(Url()), "")

    def test_username_without_password(self) -> None:
        """
        Test that a username alone is rendered without a ":".
        """
        url = Url("https://example.com/", username="user")
        self.assertEqual(url.as_str(), "https://user@example.com/")

    def test_password_without_username_is_discarded(self) -> None:
        """
        Test that a password without a username is left out and logged.
        """
        url = Url("https://example.com/", password="secret")
        with self.assertLogs("action0.url.base", level="WARNING") as logs:
            self.assertEqual(url.as_str(), "https://example.com/")
        self.assertIn("password given but no username", logs.output[0])


class UrlAuthorityTestCase(unittest.TestCase):
    """
    tests for the authority keyword of :py:class:`action0.url.base.Url`
    """

    def test_authority_with_port(self) -> None:
        """
        Test that "hostname:port" is split into both attributes
        (regression: the port used to be dropped by a typo).
        """
        url = Url(scheme="https", authority="example.com:8080")
        self.assertEqual(url.hostname, "example.com")
        self.assertEqual(url.port, 8080)
        self.assertEqual(url.as_str(), "https://example.com:8080")

    def test_authority_without_port(self) -> None:
        """
        Test that an authority without a port is used as hostname as-is
        (regression: this used to raise a ValueError while splitting).
        """
        url = Url(scheme="https", authority="example.com")
        self.assertEqual(url.hostname, "example.com")
        self.assertIsNone(url.port)
        self.assertEqual(url.as_str(), "https://example.com")

    def test_authority_ipv6(self) -> None:
        """
        Test that the colons of an IPv6 literal are not mistaken for a
        port separator.
        """
        url = Url(scheme="https", authority="[::1]:8080")
        self.assertEqual(url.hostname, "[::1]")
        self.assertEqual(url.port, 8080)

        url = Url(scheme="https", authority="[::1]")
        self.assertEqual(url.hostname, "[::1]")
        self.assertIsNone(url.port)

    def test_authority_conflicts(self) -> None:
        """
        Test that authority cannot be combined with hostname or port.
        """
        with self.assertRaises(ValueError):
            Url(authority="example.com:8080", hostname="example.com")
        with self.assertRaises(ValueError):
            Url(authority="example.com:8080", port=8080)


class UrlDunderTestCase(unittest.TestCase):
    """
    tests for __str__ and __repr__ of :py:class:`action0.url.base.Url`
    """

    def test_str(self) -> None:
        """
        Test that str() matches as_str().
        """
        url = Url("https://example.com/index.html")
        self.assertEqual(str(url), url.as_str())

    def test_repr(self) -> None:
        """
        Test that repr() wraps the URL in the class name.
        """
        url = Url("https://example.com/index.html")
        self.assertEqual(repr(url), "Url(https://example.com/index.html)")


if __name__ == "__main__":
    unittest.main()
