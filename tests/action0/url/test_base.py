import unittest
from urllib.parse import ParseResult

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

    def test_repr_redacts_password(self) -> None:
        """
        Test that repr() never leaks the password (e.g. into logs).
        """
        url = Url("https://user:secret@example.com/")
        self.assertEqual(repr(url), "Url(https://user:***@example.com/)")

    def test_str_keeps_password(self) -> None:
        """
        Test that str() still serializes the real password.
        """
        url = Url("https://user:secret@example.com/")
        self.assertEqual(str(url), "https://user:secret@example.com/")


class UrlJoinTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.base.Url.join`
    """

    def test_join_relative(self) -> None:
        """
        Test resolving relative references like a browser would.
        """
        url = Url("https://example.com/a/b")
        self.assertEqual(url.join("c").as_str(), "https://example.com/a/c")
        self.assertEqual(url.join("../x").as_str(), "https://example.com/x")

    def test_join_absolute_path(self) -> None:
        """
        Test that an absolute path replaces path and query.
        """
        url = Url("https://example.com/a/b?q=1")
        self.assertEqual(url.join("/x").as_str(), "https://example.com/x")

    def test_join_full_url(self) -> None:
        """
        Test that a full URL replaces everything.
        """
        url = Url("https://example.com/a")
        self.assertEqual(url.join("https://other.org/p").as_str(), "https://other.org/p")

    def test_join_url_instance(self) -> None:
        """
        Test that another Url instance can be joined as well.
        """
        url = Url("https://example.com/a")
        self.assertEqual(url.join(Url("https://other.org/p")).as_str(), "https://other.org/p")

    def test_join_does_not_modify(self) -> None:
        """
        Test that join() returns a new Url and keeps the original.
        """
        url = Url("https://example.com/a/b")
        url.join("c")
        self.assertEqual(url.as_str(), "https://example.com/a/b")


class UrlTruedivTestCase(unittest.TestCase):
    """
    tests for building paths with the "/" operator
    """

    def test_append_segment(self) -> None:
        """
        Test appending a segment to a URL without a path.
        """
        url = Url("https://example.com")
        self.assertEqual((url / "api").as_str(), "https://example.com/api")

    def test_chaining(self) -> None:
        """
        Test appending multiple segments by chaining.
        """
        url = Url("https://example.com") / "api" / "v2" / "users"
        self.assertEqual(url.as_str(), "https://example.com/api/v2/users")

    def test_slash_handling(self) -> None:
        """
        Test that segments are always joined with exactly one slash.
        """
        self.assertEqual((Url("https://example.com/a/") / "/b").path, "/a/b")
        self.assertEqual((Url("https://example.com/a") / "b/c").path, "/a/b/c")

    def test_query_and_fragment_kept(self) -> None:
        """
        Test that the other URL parts are kept when appending.
        """
        url = Url("https://example.com/a?q=1#frag") / "b"
        self.assertEqual(url.as_str(), "https://example.com/a/b?q=1#frag")

    def test_does_not_modify(self) -> None:
        """
        Test that "/" returns a new Url and keeps the original.
        """
        url = Url("https://example.com/a")
        _ = url / "b"
        self.assertEqual(url.path, "/a")


class UrlAuthorityPropertyTestCase(unittest.TestCase):
    """
    tests for the authority property of :py:class:`action0.url.base.Url`
    """

    def test_get(self) -> None:
        """
        Test reading the authority with and without a port.
        """
        self.assertEqual(Url("https://example.com/x").authority, "example.com")
        self.assertEqual(Url("https://example.com:8443/x").authority, "example.com:8443")

    def test_get_excludes_userinfo(self) -> None:
        """
        Test that username and password are not part of the authority.
        """
        self.assertEqual(Url("https://user:pass@example.com/x").authority, "example.com")

    def test_set(self) -> None:
        """
        Test that assigning an authority replaces hostname and port.
        """
        url = Url("https://example.com:8443/x")
        url.authority = "other.org:9000"
        self.assertEqual(url.hostname, "other.org")
        self.assertEqual(url.port, 9000)
        self.assertEqual(url.as_str(), "https://other.org:9000/x")

    def test_set_without_port(self) -> None:
        """
        Test that assigning an authority without a port clears the port.
        """
        url = Url("https://example.com:8443/x")
        url.authority = "other.org"
        self.assertEqual(url.hostname, "other.org")
        self.assertIsNone(url.port)


class UrlOriginTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.base.Url.origin`
    """

    def test_origin(self) -> None:
        """
        Test that the origin keeps only scheme, hostname and port.
        """
        url = Url("https://user:pass@example.com:8443/path?q=1#frag")
        origin = url.origin()
        self.assertEqual(origin.as_str(), "https://example.com:8443")
        self.assertEqual(origin, Url(scheme="https", hostname="example.com", port=8443))

    def test_origin_comparison(self) -> None:
        """
        Test same-origin comparisons.
        """
        self.assertEqual(
            Url("https://example.com/a?x=1").origin(), Url("https://example.com/b#f").origin()
        )
        self.assertNotEqual(
            Url("https://example.com/a").origin(), Url("https://example.com:8443/a").origin()
        )

    def test_origin_as_base(self) -> None:
        """
        Test using the origin as a base to build new URLs on.
        """
        origin = Url("https://example.com/deep/path?q=1").origin()
        self.assertEqual((origin / "healthz").as_str(), "https://example.com/healthz")


class UrlEqualityTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.base.Url.__eq__`
    """

    def test_equal(self) -> None:
        """
        Test that two Urls parsed from the same string are equal.
        """
        url_str = "https://user:pass@example.com:8443/path;v=1?a=1#frag"
        self.assertEqual(Url(url_str), Url(url_str))

    def test_query_key_order_ignored(self) -> None:
        """
        Test that the order of query parameter names does not matter.
        """
        self.assertEqual(Url("https://example.com?a=1&b=2"), Url("https://example.com?b=2&a=1"))

    def test_query_value_order_matters(self) -> None:
        """
        Test that the order of multiple values of one name does matter.
        """
        self.assertNotEqual(Url("https://example.com?a=1&a=2"), Url("https://example.com?a=2&a=1"))

    def test_not_equal(self) -> None:
        """
        Test that differing parts make Urls unequal.
        """
        self.assertNotEqual(Url("https://example.com"), Url("https://example.com:8443"))
        self.assertNotEqual(Url("https://example.com/a"), Url("https://example.com/b"))

    def test_not_equal_to_string(self) -> None:
        """
        Test that comparison with other types is False, not an error.
        """
        self.assertNotEqual(Url("https://example.com"), "https://example.com")


class UrlCopyTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.base.Url.copy`
    """

    def test_copy_equal_but_independent(self) -> None:
        """
        Test that the copy is equal but shares no mutable state.
        """
        url = Url("https://example.com/path?a=1")
        copied = url.copy()
        self.assertEqual(copied, url)
        self.assertIsNot(copied, url)

        copied.query.add("b", "2")
        copied.path = "/other"
        self.assertEqual(url.as_str(), "https://example.com/path?a=1")

    def test_copy_with_overrides(self) -> None:
        """
        Test replacing parts while copying.
        """
        url = Url("https://example.com:8443/index.html")
        self.assertEqual(url.copy(scheme="http").as_str(), "http://example.com:8443/index.html")
        self.assertEqual(url.copy(port=None).as_str(), "https://example.com/index.html")

    def test_copy_with_authority_override(self) -> None:
        """
        Test that the authority override replaces hostname and port.
        """
        url = Url("https://example.com:8443/x")
        self.assertEqual(url.copy(authority="other.org:9000").as_str(), "https://other.org:9000/x")

    def test_copy_unknown_part(self) -> None:
        """
        Test that an unknown part name raises a TypeError.
        """
        with self.assertRaises(TypeError):
            Url("https://example.com").copy(nonsense="x")


class UrlEncodingTestCase(unittest.TestCase):
    """
    tests for the percent-/IDNA-encoding behavior of
    :py:class:`action0.url.base.Url`
    """

    def test_path_encoded_on_output(self) -> None:
        """
        Test that spaces and non-ASCII characters in the path are
        percent-encoded when rendering.
        """
        url = Url(scheme="https", hostname="example.com", path="/my files/päper.pdf")
        self.assertEqual(url.as_str(), "https://example.com/my%20files/p%C3%A4per.pdf")

    def test_path_decoded_on_parse(self) -> None:
        """
        Test that an encoded path is stored decoded and re-encoded losslessly.
        """
        url = Url("https://example.com/a%20b/c%C3%A4")
        self.assertEqual(url.path, "/a b/cä")
        self.assertEqual(url.as_str(), "https://example.com/a%20b/c%C3%A4")

    def test_no_double_encoding(self) -> None:
        """
        Test that an encoded "%" round-trips without double encoding.
        """
        url = Url("https://example.com/a%2520b")
        self.assertEqual(url.path, "/a%20b")
        self.assertEqual(url.as_str(), "https://example.com/a%2520b")

    def test_path_keeps_sub_delims(self) -> None:
        """
        Test that characters which may appear raw in a path stay raw.
        """
        url = Url(scheme="https", hostname="example.com", path="/a(1),b/c+d:e@f")
        self.assertEqual(url.as_str(), "https://example.com/a(1),b/c+d:e@f")

    def test_path_semicolon_encoded(self) -> None:
        """
        Test that a literal ";" in the path is encoded (it would start the
        path params otherwise) and survives a round trip.
        """
        url = Url(scheme="https", hostname="example.com", path="/a;b")
        self.assertEqual(url.as_str(), "https://example.com/a%3Bb")
        self.assertEqual(Url(url.as_str()).path, "/a;b")

    def test_fragment_encoding(self) -> None:
        """
        Test that the fragment is encoded and decoded like the path.
        """
        url = Url("https://example.com/x", fragment="see § 2")
        self.assertEqual(url.as_str(), "https://example.com/x#see%20%C2%A7%202")
        self.assertEqual(Url(url.as_str()).fragment, "see § 2")

    def test_userinfo_encoding(self) -> None:
        """
        Test that reserved characters in username and password are encoded.
        """
        url = Url("https://example.com/", username="user name", password="p@ss:word")
        self.assertEqual(url.as_str(), "https://user%20name:p%40ss%3Aword@example.com/")

    def test_userinfo_decoded_on_parse(self) -> None:
        """
        Test that encoded userinfo is stored decoded and round-trips.
        """
        url = Url("https://user%40mail:pa%3Ass@example.com/")
        self.assertEqual(url.username, "user@mail")
        self.assertEqual(url.password, "pa:ss")
        self.assertEqual(url.as_str(), "https://user%40mail:pa%3Ass@example.com/")

    def test_hostname_punycode(self) -> None:
        """
        Test that a non-ASCII hostname is IDNA-encoded on output while the
        attribute keeps the readable value.
        """
        url = Url(scheme="https", hostname="bücher.example", path="/x")
        self.assertEqual(url.as_str(), "https://xn--bcher-kva.example/x")
        self.assertEqual(url.hostname, "bücher.example")

    def test_ascii_hostname_untouched(self) -> None:
        """
        Test that ASCII hostnames (incl. IPv6 literals) stay as they are.
        """
        self.assertEqual(Url("https://example.com/x").as_str(), "https://example.com/x")
        self.assertEqual(Url(scheme="https", authority="[::1]:8080").hostname, "[::1]")


class UrlNormalizeTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.base.Url.normalize`
    """

    def test_lowercases_scheme_and_hostname(self) -> None:
        """
        Test that scheme and hostname are lowercased.
        """
        url = Url(scheme="HTTPS", hostname="Example.COM", path="/X")
        normalized = url.normalize()
        self.assertEqual(normalized.scheme, "https")
        self.assertEqual(normalized.hostname, "example.com")
        # the path's case is meaningful and untouched
        self.assertEqual(normalized.path, "/X")

    def test_removes_default_port(self) -> None:
        """
        Test that the scheme's default port is removed, others are kept.
        """
        self.assertIsNone(Url("https://example.com:443/x").normalize().port)
        self.assertIsNone(Url("http://example.com:80/x").normalize().port)
        self.assertIsNone(Url("ftp://example.com:21/x").normalize().port)
        self.assertIsNone(Url("wss://example.com:443/x").normalize().port)
        self.assertEqual(Url("https://example.com:8443/x").normalize().port, 8443)
        self.assertEqual(Url("http://example.com:443/x").normalize().port, 443)

    def test_resolves_dot_segments(self) -> None:
        """
        Test that "." and ".." segments are resolved (RFC 3986, 5.2.4).
        """
        self.assertEqual(Url("https://example.com/a/./b/../c").normalize().path, "/a/c")
        self.assertEqual(Url("https://example.com/../a").normalize().path, "/a")
        self.assertEqual(Url("https://example.com/a/b/..").normalize().path, "/a/")
        self.assertEqual(Url("https://example.com/a/b/.").normalize().path, "/a/b/")

    def test_empty_path_becomes_root(self) -> None:
        """
        Test that an empty path becomes "/" when there is a hostname.
        """
        self.assertEqual(Url("https://example.com").normalize().as_str(), "https://example.com/")

    def test_does_not_modify(self) -> None:
        """
        Test that normalize() returns a new Url and keeps the original.
        """
        url = Url("https://example.com:443/a/./b")
        url.normalize()
        self.assertEqual(url.as_str(), "https://example.com:443/a/./b")


class UrlPathHelpersTestCase(unittest.TestCase):
    """
    tests for the parent, name and suffix helpers of
    :py:class:`action0.url.base.Url`
    """

    def test_parent(self) -> None:
        """
        Test that parent drops the last path segment and keeps the rest.
        """
        url = Url("https://example.com/a/b/file.html?q=1")
        self.assertEqual(url.parent.as_str(), "https://example.com/a/b?q=1")
        self.assertEqual(Url("https://example.com/a/b/").parent.path, "/a")
        self.assertEqual(Url("https://example.com/a").parent.path, "/")

    def test_parent_of_root_is_root(self) -> None:
        """
        Test that the parent of the root is the root.
        """
        self.assertEqual(Url("https://example.com/").parent.path, "/")

    def test_parent_does_not_modify(self) -> None:
        """
        Test that parent returns a new Url and keeps the original.
        """
        url = Url("https://example.com/a/b")
        self.assertEqual(url.parent.path, "/a")
        self.assertEqual(url.path, "/a/b")

    def test_name(self) -> None:
        """
        Test reading the last path segment.
        """
        self.assertEqual(Url("https://example.com/a/file.html").name, "file.html")
        self.assertEqual(Url("https://example.com/a/").name, "")
        self.assertEqual(Url("https://example.com").name, "")

    def test_name_setter(self) -> None:
        """
        Test that assigning a name replaces the last path segment.
        """
        url = Url("https://example.com/docs/old.html?q=1")
        url.name = "new.html"
        self.assertEqual(url.as_str(), "https://example.com/docs/new.html?q=1")

    def test_suffix(self) -> None:
        """
        Test reading the file extension of the name.
        """
        self.assertEqual(Url("https://example.com/a/file.html").suffix, ".html")
        self.assertEqual(Url("https://example.com/a/archive.tar.gz").suffix, ".gz")
        self.assertEqual(Url("https://example.com/a/file").suffix, "")
        self.assertEqual(Url("https://example.com/a/.hidden").suffix, "")
        self.assertEqual(Url("https://example.com/a/dir/").suffix, "")


class UrlIntrospectionTestCase(unittest.TestCase):
    """
    tests for as_dict, as_parse_result and is_absolute/is_relative of
    :py:class:`action0.url.base.Url`
    """

    def test_as_dict(self) -> None:
        """
        Test that all parts appear in the dictionary as plain types.
        """
        url = Url("https://user:pass@example.com:8443/p;v=1?a=1&a=2#f")
        self.assertEqual(
            url.as_dict(),
            {
                "scheme": "https",
                "username": "user",
                "password": "pass",
                "hostname": "example.com",
                "port": 8443,
                "path": "/p",
                "path_params": {"v": ["1"]},
                "query": {"a": ["1", "2"]},
                "fragment": "f",
            },
        )

    def test_as_parse_result(self) -> None:
        """
        Test the conversion into the stdlib ParseResult named tuple.
        """
        url = Url("https://user:pass@example.com:8443/p?a=1#f")
        result = url.as_parse_result()
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.scheme, "https")
        self.assertEqual(result.netloc, "user:pass@example.com:8443")
        self.assertEqual(result.path, "/p")
        self.assertEqual(result.query, "a=1")
        self.assertEqual(result.fragment, "f")

    def test_is_absolute_and_relative(self) -> None:
        """
        Test that absolute means "has a hostname".
        """
        self.assertTrue(Url("https://example.com/x").is_absolute())
        self.assertFalse(Url("https://example.com/x").is_relative())

        relative = Url(path="/a/b")
        self.assertFalse(relative.is_absolute())
        self.assertTrue(relative.is_relative())


if __name__ == "__main__":
    unittest.main()
