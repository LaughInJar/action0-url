import unittest
from typing import Any
from typing import cast
from urllib.parse import ParseResult
from urllib.parse import urljoin

from action0.url import Params
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

    def test_kwargs_with_empty_values_clear_parts(self) -> None:
        """
        Test that every given keyword argument replaces its part, also
        with an empty value (regression: falsy values were ignored).
        """
        base = "https://user:pass@www.example.com:8443/path;v=1?foo=bar#frag"
        url = Url(base, path="", fragment="", query={}, path_params="")
        self.assertEqual(url.as_str(), "https://user:pass@www.example.com:8443")

        url = Url(
            base,
            username=None,
            password=None,
            port=None,
            path=None,
            path_params=None,
            query=None,
            fragment=None,
        )
        self.assertEqual(url.as_str(), "https://www.example.com")
        self.assertIsNone(url.username)
        self.assertIsNone(url.password)
        self.assertIsNone(url.port)
        self.assertEqual(url.path, "")
        self.assertEqual(url.fragment, "")

        url = Url(base, scheme=None, hostname=None, port=None, username="", password="")
        self.assertEqual(url.scheme, "")
        self.assertIsNone(url.hostname)
        self.assertEqual(url.as_str(), "/path;v=1?foo=bar#frag")

    def test_parts_not_given_are_kept(self) -> None:
        """
        Test that keyword arguments which are left out keep the parts of
        the base URL string.
        """
        url = Url("https://user:pass@www.example.com:8443/path;v=1?foo=bar#frag", scheme="http")
        self.assertEqual(
            url.as_str(), "http://user:pass@www.example.com:8443/path;v=1?foo=bar#frag"
        )

    def test_port_zero(self) -> None:
        """
        Test that the (falsy) port 0 is neither dropped when parsing nor
        when given as keyword argument.
        """
        self.assertEqual(Url("https://example.com:0/").as_str(), "https://example.com:0/")
        self.assertEqual(Url("https://example.com:8443/", port=0).port, 0)

    def test_no_default_scheme(self) -> None:
        """
        Test that nothing is assumed about a missing scheme, so relative
        references round-trip (regression: "https" was used as default,
        which rendered "/a/b" as "https:///a/b").
        """
        for reference in ("/a/b", "a/b", "example.com/path", "../x.html", "?a=1", "#top", ""):
            with self.subTest(reference=reference):
                url = Url(reference)
                self.assertEqual(url.scheme, "")
                self.assertIsNone(url.hostname)
                self.assertEqual(url.as_str(), reference)

        self.assertEqual(Url("/a/b"), Url(path="/a/b"))

    def test_scheme_relative_url(self) -> None:
        """
        Test that a "//host/path" reference has a hostname but no scheme.
        """
        url = Url("//example.com/x")
        self.assertEqual(url.scheme, "")
        self.assertEqual(url.hostname, "example.com")
        self.assertEqual(url.as_str(), "//example.com/x")

    def test_ipv6_round_trip(self) -> None:
        """
        Test that an IPv6 host is held without brackets and rendered with
        them (regression: the brackets were lost, "http://::1:8080/x").
        """
        url = Url("http://[::1]:8080/x")
        self.assertEqual(url.hostname, "::1")
        self.assertEqual(url.port, 8080)
        self.assertEqual(url.as_str(), "http://[::1]:8080/x")

        url_str = "http://[2001:db8::1]/x"
        self.assertEqual(Url(url_str).as_str(), url_str)
        self.assertEqual(Url(Url(url_str).as_str()), Url(url_str))

    def test_ipv6_hostname_keyword_and_attribute(self) -> None:
        """
        Test that an IPv6 hostname may be given with or without brackets.
        """
        self.assertEqual(Url(scheme="http", hostname="[::1]").hostname, "::1")
        self.assertEqual(Url(scheme="http", hostname="::1").as_str(), "http://[::1]")
        self.assertEqual(Url(scheme="http", hostname="[::1]"), Url("http://[::1]"))

        # attributes are plain: brackets stay, but are not doubled on output
        url = Url("http://example.com/")
        url.hostname = "[::1]"
        self.assertEqual(url.as_str(), "http://[::1]/")

    def test_invalid_url_raises(self) -> None:
        """
        Test that the ValueErrors of urllib for unparsable URLs surface.
        """
        for invalid in ("https://example.com:abc/", "https://example.com:99999/", "https://[::1/"):
            with self.subTest(url=invalid):
                with self.assertRaises(ValueError):
                    Url(invalid)

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
            url.as_str(), "https://www.example.com/path/filename.json?foo=baz&a=b&foo=123"
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

    def test_password_without_username(self) -> None:
        """
        Test that a password without a username is rendered as
        ":password@" (regression: it was discarded, which broke URLs like
        "redis://:secret@localhost").
        """
        url = Url("https://example.com/", password="secret")
        self.assertEqual(url.as_str(), "https://:secret@example.com/")

        url_str = "redis://:secret@localhost:6379/0"
        url = Url(url_str)
        self.assertIsNone(url.username)
        self.assertEqual(url.password, "secret")
        self.assertEqual(url.as_str(), url_str)


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
        self.assertEqual(url.hostname, "::1")
        self.assertEqual(url.port, 8080)
        self.assertEqual(url.as_str(), "https://[::1]:8080")
        self.assertEqual(url, Url("https://[::1]:8080"))

        url = Url(scheme="https", authority="[::1]")
        self.assertEqual(url.hostname, "::1")
        self.assertIsNone(url.port)

        # without brackets there is no way to tell a port apart
        url = Url(scheme="https", authority="2001:db8::1")
        self.assertEqual(url.hostname, "2001:db8::1")
        self.assertIsNone(url.port)

    def test_authority_replaces_port_of_base_url(self) -> None:
        """
        Test that an authority without a port removes the port of the base
        URL (regression: "other.org" kept the old port).
        """
        url = Url("https://example.com:8443/x", authority="other.org")
        self.assertEqual(url.as_str(), "https://other.org/x")

        url = Url("https://example.com:8443/x", authority=None)
        self.assertIsNone(url.hostname)
        self.assertIsNone(url.port)

    def test_authority_rejects_userinfo(self) -> None:
        """
        Test that userinfo in the authority raises instead of ending up in
        the hostname.
        """
        with self.assertRaises(ValueError):
            Url(scheme="https", authority="user:pass@example.com:8443")

    def test_authority_malformed(self) -> None:
        """
        Test that a non-numeric port and a broken IPv6 literal raise.
        """
        for authority in ("example.com:abc", "[::1", "[::1]8080", "[::1]:x"):
            with self.subTest(authority=authority):
                with self.assertRaises(ValueError):
                    Url(scheme="https", authority=authority)

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

    def test_repr_redacts_password_without_username(self) -> None:
        """
        Test that a password without a username is redacted as well.
        """
        url = Url("redis://:secret@localhost:6379/0")
        self.assertEqual(repr(url), "Url(redis://:***@localhost:6379/0)")

    def test_not_hashable(self) -> None:
        """
        Test that the mutable Url cannot be used as dictionary key.
        """
        with self.assertRaises(TypeError):
            hash(cast(Any, Url("https://example.com")))

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

    def test_join_matches_urljoin(self) -> None:
        """
        Test the reference resolution against the examples of RFC 3986,
        section 5.4, with urllib's urljoin as oracle.
        """
        base = "http://a/b/c/d?q=1"
        references = [
            "g",
            "./g",
            "g/",
            "/g",
            "//g",
            "?y=1",
            "g?y=1",
            "#s",
            "g#s",
            "g?y=1#s",
            "",
            ".",
            "./",
            "..",
            "../",
            "../g",
            "../..",
            "../../",
            "../../g",
            "../../../g",
            "../../../../g",
            "/./g",
            "/../g",
            "g.",
            ".g",
            "g..",
            "..g",
            "./../g",
            "./g/.",
            "g/./h",
            "g/../h",
            "https://other.org/x",
        ]
        for reference in references:
            with self.subTest(reference=reference):
                self.assertEqual(Url(base).join(reference).as_str(), urljoin(base, reference))

    def test_join_path_params(self) -> None:
        """
        Test that the path params belong to the last path segment: they are
        kept for same-document references and replaced otherwise.
        """
        base = Url("http://a/b/c/d;p=1?q=1")
        self.assertEqual(base.join("#s").as_str(), "http://a/b/c/d;p=1?q=1#s")
        self.assertEqual(base.join("?y=1").as_str(), "http://a/b/c/d;p=1?y=1")
        self.assertEqual(base.join("g").as_str(), "http://a/b/c/g")
        self.assertEqual(base.join("g;x=1?y=1").as_str(), "http://a/b/c/g;x=1?y=1")

    def test_join_any_scheme(self) -> None:
        """
        Test that references are resolved for schemes urllib does not know
        (regression: urljoin just returned the reference for those).
        """
        base = Url("myapp://host/a/b")
        self.assertEqual(base.join("c").as_str(), "myapp://host/a/c")
        self.assertEqual(base.join("../c?d=1").as_str(), "myapp://host/c?d=1")
        self.assertEqual(base.join("/x").as_str(), "myapp://host/x")

    def test_join_relative_base(self) -> None:
        """
        Test that joining onto a relative URL stays relative (regression:
        the result got the scheme "https").
        """
        self.assertEqual(Url(path="/a").join("b").as_str(), "/b")
        self.assertEqual(Url("a/b").join("c").as_str(), "a/c")
        self.assertEqual(Url("a/b").join("../../c").as_str(), "../c")

    def test_join_host_without_path(self) -> None:
        """
        Test that a relative path joined onto a bare host becomes absolute.
        """
        self.assertEqual(Url("https://example.com").join("a").as_str(), "https://example.com/a")

    def test_join_keeps_userinfo(self) -> None:
        """
        Test that the userinfo of the base URL survives relative references.
        """
        url = Url("https://user:pass@example.com/a/b").join("c")
        self.assertEqual(url.as_str(), "https://user:pass@example.com/a/c")

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

    def test_relative_url_without_path_stays_relative(self) -> None:
        """
        Test that appending to a URL without host and path does not make
        the path absolute.
        """
        self.assertEqual((Url() / "api" / "v2").as_str(), "api/v2")
        self.assertEqual((Url(path="/") / "api").as_str(), "/api")
        self.assertEqual((Url("?a=1") / "/api").as_str(), "api?a=1")

    def test_non_string_segment(self) -> None:
        """
        Test that a non-string operand is rejected with a TypeError
        (regression: it raised an AttributeError).
        """
        with self.assertRaises(TypeError):
            _ = Url("https://example.com") / cast(Any, 5)

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

    def test_ipv6(self) -> None:
        """
        Test that an IPv6 hostname is bracketed in the authority and that
        the brackets are removed again when assigning.
        """
        url = Url("http://[::1]:8080/x")
        self.assertEqual(url.authority, "[::1]:8080")

        url.authority = "[2001:db8::1]:9000"
        self.assertEqual(url.hostname, "2001:db8::1")
        self.assertEqual(url.port, 9000)
        self.assertEqual(url.as_str(), "http://[2001:db8::1]:9000/x")

    def test_get_is_readable(self) -> None:
        """
        Test that the authority shows the readable hostname, not punycode.
        """
        url = Url(scheme="https", hostname="bücher.example", port=8443)
        self.assertEqual(url.authority, "bücher.example:8443")

    def test_set_rejects_userinfo(self) -> None:
        """
        Test that assigning an authority with userinfo raises.
        """
        url = Url("https://example.com/")
        with self.assertRaises(ValueError):
            url.authority = "user@other.org"

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

    def test_copy_rejects_base_url(self) -> None:
        """
        Test that the base url string is not accepted as an override
        (regression: it was merged part by part with the copied URL).
        """
        with self.assertRaises(TypeError):
            Url("https://example.com/a").copy(url="http://other.org/b")

    def test_copy_removes_parts(self) -> None:
        """
        Test that empty override values remove the part.
        """
        url = Url("https://user:pass@example.com:8443/p;v=1?a=1#f")
        copied = url.copy(
            username=None, password=None, port=None, query=None, path_params={}, fragment=""
        )
        self.assertEqual(copied.as_str(), "https://example.com/p")

    def test_copy_keeps_path_params_encoding(self) -> None:
        """
        Test that the path params of a copy are path-encoded as well.
        """
        url = Url("https://example.com/p;v=1+2?q=1+2")
        self.assertEqual(url.copy().as_str(), "https://example.com/p;v=1+2?q=1+2")
        self.assertEqual(url.copy().path_params["v"], "1+2")

    def test_subclass_is_preserved(self) -> None:
        """
        Test that the methods deriving a new Url return the subclass.
        """

        class MyUrl(Url):
            pass

        url = MyUrl("https://example.com/a/b?x=1")
        self.assertIsInstance(url.copy(), MyUrl)
        self.assertIsInstance(url.origin(), MyUrl)
        self.assertIsInstance(url / "c", MyUrl)
        self.assertIsInstance(url.join("c"), MyUrl)
        self.assertIsInstance(url.parent, MyUrl)
        self.assertIsInstance(url.normalize(), MyUrl)


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

    def test_path_semicolon_in_inner_segment_kept(self) -> None:
        """
        Test that a ";" in a segment before the last one stays raw: only
        the last segment can have path params (regression: it was encoded).
        """
        url_str = "https://example.com/a;x=1/b;y=2"
        url = Url(url_str)
        self.assertEqual(url.path, "/a;x=1/b")
        self.assertEqual(url.path_params.as_dict(), {"y": ["2"]})
        self.assertEqual(url.as_str(), url_str)

    def test_path_semicolon_kept_without_params_scheme(self) -> None:
        """
        Test that a ";" stays raw for schemes urllib does not split path
        params for, as it is part of the path there.
        """
        url_str = "ws://example.com/a;b=1"
        url = Url(url_str)
        self.assertEqual(url.path, "/a;b=1")
        self.assertEqual(url.as_str(), url_str)

    def test_path_params_are_not_form_encoded(self) -> None:
        """
        Test that in path params a "+" is a literal plus sign and a space
        is written as "%20" (regression: they were treated like a query).
        """
        url = Url("https://example.com/a;v=1+2?q=1+2")
        self.assertEqual(url.path_params["v"], "1+2")
        self.assertEqual(url.query["q"], "1 2")
        self.assertEqual(url.as_str(), "https://example.com/a;v=1+2?q=1+2")

        url.path_params["v"] = "a b;c/d"
        self.assertEqual(url.as_str(), "https://example.com/a;v=a%20b%3Bc%2Fd?q=1+2")
        self.assertEqual(Url(url.as_str()).path_params["v"], "a b;c/d")

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
        Test that ASCII hostnames stay as they are.
        """
        self.assertEqual(Url("https://example.com/x").as_str(), "https://example.com/x")
        self.assertEqual(
            Url("https://my_host-1.example.com/x").as_str(), "https://my_host-1.example.com/x"
        )
        # an already IDNA-encoded hostname is not touched either
        self.assertEqual(Url("https://xn--bcher-kva.example").hostname, "xn--bcher-kva.example")

    def test_hostname_decoded_on_parse(self) -> None:
        """
        Test that a percent-encoded hostname is decoded like the other parts.
        """
        url = Url("https://b%C3%BCcher.example/")
        self.assertEqual(url.hostname, "bücher.example")
        self.assertEqual(url.as_str(), "https://xn--bcher-kva.example/")

    def test_hostname_cannot_inject_other_parts(self) -> None:
        """
        Test that delimiters in a hostname are encoded instead of starting
        a path or query (regression: the hostname was emitted verbatim).
        """
        url = Url(scheme="https", hostname="evil.com/x?y#z")
        self.assertEqual(url.as_str(), "https://evil.com%2Fx%3Fy%23z")
        self.assertEqual(Url(url.as_str()).path, "")

    def test_non_utf8_escapes_are_replaced(self) -> None:
        """
        Test the documented lossy case: percent escapes that are not valid
        UTF-8 become the replacement character.
        """
        self.assertEqual(Url("https://example.com/a%FFb").path, "/a\ufffdb")


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

    def test_relative_path_stays_relative(self) -> None:
        """
        Test that the path of a URL without hostname is not made absolute
        and that unresolvable ".." segments are kept (regression: "a/../b"
        became "/b" and "../a" became "a").
        """
        cases = {
            "a/../b": "b",
            "a/./b": "a/b",
            "../a": "../a",
            "../../a/../b": "../../b",
            "a/b/..": "a/",
            "a/..": "./",
            ".": "./",
            "..": "../",
            "a/../..": "../",
            "": "",
            "/a/../b": "/b",
            "/a/b/../..": "/",
            "/..": "/",
            "/a//../b": "/a/b",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(Url(path=path).normalize().path, expected)

    def test_path_becomes_absolute_with_hostname(self) -> None:
        """
        Test that a path without leading slash is made absolute if there
        is a hostname, like it is rendered.
        """
        url = Url(scheme="https", hostname="example.com", path="a/../index.html")
        self.assertEqual(url.normalize().path, "/index.html")
        self.assertEqual(url.normalize(), Url("https://example.com/index.html"))

    def test_strips_ipv6_brackets(self) -> None:
        """
        Test that brackets of an assigned IPv6 hostname are normalized away.
        """
        url = Url("http://example.com:80/")
        url.hostname = "[::1]"
        self.assertEqual(url.normalize(), Url("http://[::1]/"))
        self.assertEqual(url.normalize().as_str(), "http://[::1]/")

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
        self.assertEqual(Url("https://example.com/a/.hidden.txt").suffix, ".txt")
        self.assertEqual(Url("https://example.com/a/dir/").suffix, "")
        # dot segments are no file names (regression: ".." had the suffix ".")
        self.assertEqual(Url("https://example.com/a/..").suffix, "")
        self.assertEqual(Url("https://example.com/a/.").suffix, "")
        # like pathlib (3.14+), a trailing dot is a suffix
        self.assertEqual(Url("https://example.com/a/file.").suffix, ".")


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
        Test that absolute means "has a scheme" (RFC 3986).
        """
        self.assertTrue(Url("https://example.com/x").is_absolute())
        self.assertFalse(Url("https://example.com/x").is_relative())

        relative = Url(path="/a/b")
        self.assertFalse(relative.is_absolute())
        self.assertTrue(relative.is_relative())

        # absolute URLs without a hostname
        self.assertTrue(Url("file:///etc/hosts").is_absolute())
        self.assertTrue(Url("mailto:me@example.com").is_absolute())
        # a hostname alone does not make a URL absolute
        self.assertTrue(Url("//example.com/x").is_relative())
        self.assertTrue(Url(hostname="example.com").is_relative())


class UrlParamsAssignmentTestCase(unittest.TestCase):
    """
    tests for assigning to the query / path_params properties of
    :py:class:`action0.url.base.Url`
    """

    def test_assign_query(self) -> None:
        """
        Test that everything a Params can be built from may be assigned
        (regression: a string broke as_str() with an AttributeError).
        """
        url = Url("https://example.com/?old=1")

        url.query = "a=1&b=2"
        self.assertIsInstance(url.query, Params)
        self.assertEqual(url.as_str(), "https://example.com/?a=1&b=2")

        url.query = {"c": [3, 4]}
        self.assertEqual(url.as_str(), "https://example.com/?c=3&c=4")

        url.query = [("d", "5")]
        self.assertEqual(url.as_str(), "https://example.com/?d=5")

        url.query = None
        self.assertEqual(url.as_str(), "https://example.com/")

    def test_assign_query_params_instance(self) -> None:
        """
        Test that an assigned Params instance is used as it is.
        """
        url = Url("https://example.com/")
        params = Params("a=1")
        url.query = params
        self.assertIs(url.query, params)
        params.add("b", 2)
        self.assertEqual(url.as_str(), "https://example.com/?a=1&b=2")

    def test_assign_path_params(self) -> None:
        """
        Test that assigned path params are rendered with ";" and without
        form encoding, whatever they were given as.
        """
        url = Url("https://example.com/p")

        url.path_params = {"v": "1 2", "w": "+"}
        self.assertEqual(url.path_params.separator, ";")
        self.assertEqual(url.as_str(), "https://example.com/p;v=1%202;w=+")

        # a query-style Params instance is converted, not used as it is
        params = Params("a=1&b=2")
        url.path_params = params
        self.assertIsNot(url.path_params, params)
        self.assertEqual(url.as_str(), "https://example.com/p;a=1;b=2")

        url.path_params = None
        self.assertEqual(url.as_str(), "https://example.com/p")

    def test_constructor_does_not_share_params(self) -> None:
        """
        Test that the constructor copies a given Params instance.
        """
        params = Params("a=1")
        url = Url("https://example.com/", query=params)
        params.add("b", 2)
        self.assertEqual(url.as_str(), "https://example.com/?a=1")


if __name__ == "__main__":
    unittest.main()
