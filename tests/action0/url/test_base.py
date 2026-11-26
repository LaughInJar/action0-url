import copy
import pickle
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
            cast(Any, Url("https://example.com")).copy(nonsense="x")

    def test_copy_rejects_base_url(self) -> None:
        """
        Test that the base url string is not accepted as an override
        (regression: it was merged part by part with the copied URL).
        """
        with self.assertRaises(TypeError):
            cast(Any, Url("https://example.com/a")).copy(url="http://other.org/b")

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
        Test that a hostname with URL delimiters is rejected instead of
        starting a path or query (regression: it was emitted verbatim).
        """
        for hostname in ("evil.com/x", "evil.com?y", "evil.com#z", "user@evil.com", "a b", "a\\b"):
            with self.subTest(hostname=hostname):
                with self.assertRaises(ValueError):
                    Url(scheme="https", hostname=hostname)

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
        Test that an assigned Params instance is copied, never shared
        (regression: a "fitting" instance was used as it is, so that
        ``b.query = a.query`` tied two Urls together).
        """
        url = Url("https://example.com/")
        params = Params("a=1")
        url.query = params
        self.assertIsNot(url.query, params)
        params.add("b", 2)
        self.assertEqual(url.as_str(), "https://example.com/?a=1")

        other = Url("https://other.example/")
        other.query = url.query
        other.query.add("c", 3)
        self.assertEqual(url.as_str(), "https://example.com/?a=1")
        self.assertEqual(other.as_str(), "https://other.example/?a=1&c=3")

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


class UrlHazardousPathTestCase(unittest.TestCase):
    """
    tests for paths that would be read as another part of the URL when it
    is parsed again, see :py:meth:`action0.url.base.Url.as_str`
    """

    def test_colon_in_first_relative_segment(self) -> None:
        """
        Test that a relative path cannot be mistaken for a scheme
        (regression: ``Url(path="javascript:alert(1)")`` rendered as a
        URL with the scheme "javascript").
        """
        url = Url(path="javascript:alert(1)")
        self.assertEqual(url.as_str(), "./javascript:alert(1)")
        self.assertEqual(Url(url.as_str()).scheme, "")
        self.assertEqual(Url(url.as_str()), url)

        self.assertEqual((Url() / "a:b").as_str(), "./a:b")
        # normalizing does not strip the protection again
        self.assertEqual(Url("./a:b").normalize().as_str(), "./a:b")
        self.assertEqual(Url("x/../y:z").normalize().as_str(), "./y:z")

    def test_colon_is_fine_elsewhere(self) -> None:
        """
        Test that the prefix is only added where the colon is ambiguous.
        """
        for url_str in ("a/b:c", "/a:b", "https://example.com/a:b", "//example.com/a:b", "x:a:b"):
            with self.subTest(url=url_str):
                self.assertEqual(Url(url_str).as_str(), url_str)
        url = Url(scheme="https", hostname="example.com", path="a:b")
        self.assertEqual(url.as_str(), "https://example.com/a:b")

    def test_double_slash_without_host(self) -> None:
        """
        Test that a path starting with "//" cannot be mistaken for a host
        (regression: ``join("..//evil.com/x")`` gave a path a browser reads
        as the host evil.com).
        """
        cases = [
            Url(path="//evil.com/x"),
            Url("/app/page").join("..//evil.com/x"),
            Url("/a/..//evil.com/x").normalize(),
        ]
        for url in cases:
            with self.subTest(url=url):
                self.assertEqual(url.as_str(), "/.//evil.com/x")
                self.assertIsNone(Url(url.as_str()).hostname)
                self.assertEqual(Url(url.as_str()), url)

        url = Url(scheme="https", path="//evil.com/x")
        self.assertEqual(url.as_str(), "https:/.//evil.com/x")
        self.assertIsNone(Url(url.as_str()).hostname)

    def test_double_slash_behind_a_host_is_kept(self) -> None:
        """
        Test that empty segments behind a host are left alone.
        """
        self.assertEqual(Url("https://example.com//a//b").as_str(), "https://example.com//a//b")

    def test_path_params_without_path_behind_a_host(self) -> None:
        """
        Test that path params cannot run into the host.
        """
        url = Url("https://example.com", path_params="v=1")
        self.assertEqual(url.as_str(), "https://example.com/;v=1")
        self.assertEqual(Url(url.as_str()).hostname, "example.com")


class UrlValidationTestCase(unittest.TestCase):
    """
    tests for the validation when assigning the parts of
    :py:class:`action0.url.base.Url` (attributes, keyword arguments, copy())
    """

    def test_scheme(self) -> None:
        """
        Test that a scheme is validated and lowercased (regression:
        ``scheme="https://evil.com/?"`` rewrote the whole URL).
        """
        for scheme in ("https://", "https://evil.com/?", "my scheme", "1abc", "a_b", ":"):
            with self.subTest(scheme=scheme):
                with self.assertRaises(ValueError):
                    Url("http://example.com/x", scheme=scheme)
                with self.assertRaises(ValueError):
                    Url("http://example.com/x").scheme = scheme

        url = Url(scheme="HTTPS", hostname="example.com")
        self.assertEqual(url.scheme, "https")
        url.scheme = "Git+SSH"
        self.assertEqual(url.scheme, "git+ssh")

    def test_uppercase_scheme_keeps_semicolon_escaping(self) -> None:
        """
        Test the regression that a non-lowercase scheme let a ";" of the
        path spill into the path params.
        """
        url = Url(scheme="HTTPS", hostname="example.com", path="/a;b=1")
        self.assertEqual(url.as_str(), "https://example.com/a%3Bb=1")
        self.assertEqual(Url(url.as_str()).path, "/a;b=1")
        self.assertEqual(Url(url.as_str()), url)

    def test_hostname_with_port(self) -> None:
        """
        Test that a hostname with a port is rejected with a hint
        (regression: "localhost:8080" was rendered as "[localhost:8080]").
        """
        with self.assertRaisesRegex(ValueError, "port="):
            Url(scheme="http", hostname="localhost:8080")
        with self.assertRaises(ValueError):
            Url("http://example.com/").hostname = "example.com:8080"
        # a URL that hides the colon cannot be parsed either
        with self.assertRaises(ValueError):
            Url("http://example.com%3A8080/")
        self.assertEqual(Url(scheme="http", authority="localhost:8080").port, 8080)

    def test_hostname_invalid(self) -> None:
        """
        Test that hostnames with impossible content are rejected.
        """
        for hostname in ("[zz]", "[::1", "::1]", "1:2", " example.com", "exa mple.com", "a\tb"):
            with self.subTest(hostname=hostname):
                with self.assertRaises(ValueError):
                    Url(scheme="http", hostname=hostname)

    def test_hostname_idna_checked_on_assignment(self) -> None:
        """
        Test that a hostname that cannot be IDNA-encoded is rejected when
        it is assigned, not when the URL is rendered (regression: str() and
        even repr() raised later on).
        """
        for hostname in ("bü..de", "ü" * 70 + ".de"):
            with self.subTest(hostname=hostname):
                with self.assertRaises(ValueError):
                    Url(scheme="https", hostname=hostname)
        url = Url("https://example.com/")
        with self.assertRaises(ValueError):
            url.hostname = "bü..de"
        self.assertEqual(repr(url), "Url(https://example.com/)")

    def test_hostname_is_lowercased(self) -> None:
        """
        Test that hostnames are case-insensitive: stored in lowercase.
        """
        url = Url(scheme="https", hostname="EXAMPLE.Com")
        self.assertEqual(url.hostname, "example.com")
        url.authority = "Other.ORG:8443"
        self.assertEqual(url.hostname, "other.org")
        self.assertEqual(Url(scheme="https", hostname="BÜCHER.example").hostname, "bücher.example")

    def test_port(self) -> None:
        """
        Test that a port has to be an int in the valid range.
        """
        for port in (-1, 65536, 99999):
            with self.subTest(port=port):
                with self.assertRaises(ValueError):
                    Url(scheme="http", hostname="example.com", port=port)
        for no_port in ("8080", "80/evil", True, 80.0):
            with self.subTest(port=no_port):
                with self.assertRaises(TypeError):
                    Url(scheme="http", hostname="example.com", port=cast(Any, no_port))
        url = Url("http://example.com:8080/")
        with self.assertRaises(ValueError):
            url.port = 70000
        self.assertEqual(url.port, 8080)
        url.port = 65535
        self.assertEqual(url.as_str(), "http://example.com:65535/")

    def test_authority_is_strict(self) -> None:
        """
        Test that everything that is not "hostname[:port]" is rejected.
        """
        invalid = [
            "h:99999",
            "example.com/path",
            " example.com",
            "[not-ipv6]:80",
            "[zz]",
            "::1]:80",
            "h:80:90",
            "example.com:port",
        ]
        for authority in invalid:
            with self.subTest(authority=authority):
                with self.assertRaises(ValueError):
                    Url(scheme="http", authority=authority)

    def test_authority_assignment_is_all_or_nothing(self) -> None:
        """
        Test that a rejected authority changes neither hostname nor port.
        """
        url = Url("http://example.com:8080/")
        with self.assertRaises(ValueError):
            url.authority = "other.org:99999"
        self.assertEqual(url.as_str(), "http://example.com:8080/")

    def test_none_removes_parts(self) -> None:
        """
        Test that None can be assigned to every part (regression: for path,
        fragment, scheme and authority it broke rendering).
        """
        url = Url("https://user:pass@example.com:8443/path;v=1?a=1#frag")
        url.fragment = None
        url.path = None
        url.path_params = None
        url.query = None
        url.username = None
        url.password = None
        self.assertEqual(url.as_str(), "https://example.com:8443")
        url.authority = None
        self.assertIsNone(url.hostname)
        self.assertIsNone(url.port)
        url.scheme = None
        self.assertEqual(url.as_str(), "")
        self.assertEqual(url, Url())

    def test_empty_string_is_none_for_optional_parts(self) -> None:
        """
        Test that "" and None mean the same for the parts that can be
        missing (regression: ``url.username = ""`` made a Url unequal to
        its own copy).
        """
        url = Url("https://user:pass@example.com/")
        url.username = ""
        url.password = ""
        self.assertIsNone(url.username)
        self.assertIsNone(url.password)
        self.assertEqual(url, url.copy())

    def test_wrong_types(self) -> None:
        """
        Test that values of the wrong type raise a TypeError right away
        (regression: ``query=5`` silently removed the query).
        """
        for part in ("scheme", "hostname", "path", "fragment", "username", "password"):
            with self.subTest(part=part):
                with self.assertRaises(TypeError):
                    Url("https://example.com/", **{part: cast(Any, 5)})
                with self.assertRaises(TypeError):
                    setattr(Url("https://example.com/"), part, 5)
        with self.assertRaises(TypeError):
            Url("https://example.com/?a=1", query=cast(Any, 5))
        with self.assertRaises(TypeError):
            Url("https://example.com/").path_params = cast(Any, 5)

    def test_wrong_url_type(self) -> None:
        """
        Test that the base url has to be a string (regression: a Url or
        bytes failed deep inside urllib).
        """
        for url in (b"https://example.com/", Url("https://example.com/"), 123):
            with self.subTest(url=url):
                with self.assertRaisesRegex(TypeError, "url must be a str"):
                    Url(cast(Any, url))

    def test_unknown_attribute(self) -> None:
        """
        Test that a misspelled attribute raises (regression:
        ``url.host = ...`` silently did nothing).
        """
        url = Url("https://example.com/")
        with self.assertRaises(AttributeError):
            cast(Any, url).host = "evil.example"

    def test_copy_validates(self) -> None:
        """
        Test that the replacements of copy() are validated like assignments.
        """
        url = Url("https://example.com/")
        with self.assertRaises(ValueError):
            url.copy(hostname="a/b")
        with self.assertRaises(ValueError):
            url.copy(port=-1)
        with self.assertRaises(ValueError):
            url.copy(authority="example.com", port=1)


class UrlRawPartsTestCase(unittest.TestCase):
    """
    tests for the encoded form the parts of
    :py:class:`action0.url.base.Url` are kept in
    """

    def test_escaped_reserved_characters_round_trip(self) -> None:
        """
        Test that escapes of reserved characters are not lost (regression:
        "%2B" came back as "+", which S3 reads as a space, "%2F" as "/").
        """
        url_str = "https://u%21%24:p%26%3D@example.com/a%2Bb%3D%26%3A%40%2C%2F.txt#%2F%3F%3D"
        url = Url(url_str)
        self.assertEqual(url.as_str(), url_str)
        self.assertEqual(url.path, "/a+b=&:@,/.txt")
        self.assertEqual(url.raw_path, "/a%2Bb%3D%26%3A%40%2C%2F.txt")
        self.assertEqual(url.username, "u!$")
        self.assertEqual(url.password, "p&=")
        self.assertEqual(url.fragment, "/?=")
        self.assertEqual(url.raw_fragment, "%2F%3F%3D")

    def test_invalid_utf8_escapes_round_trip(self) -> None:
        """
        Test that escapes that are not valid UTF-8 survive, although the
        decoded attribute can only show a replacement character.
        """
        url = Url("https://example.com/a%FFb")
        self.assertEqual(url.as_str(), "https://example.com/a%FFb")
        self.assertEqual(url.path, "/a�b")

    def test_signed_url_round_trip(self) -> None:
        """
        Test that a URL whose exact spelling matters is not touched.
        """
        url_str = (
            "https://bucket.s3.amazonaws.com/k%2Fey%20x?X-Amz-Signature=ab%2Bc%2f"
            "&X-Amz-Date=20260131T000000Z&flag&a=b=c&&"
        )
        self.assertEqual(Url(url_str).as_str(), url_str)
        self.assertEqual(Url(url_str).copy().as_str(), url_str)

    def test_characters_not_allowed_in_a_url_are_encoded(self) -> None:
        """
        Test that the only repairs of a parsed URL are the ones it needs
        to be a URL: spaces, non-ASCII characters and a stray "%".
        """
        url = Url("https://example.com/a b/ä/100%?q=a b&x=ä%#f g%")
        self.assertEqual(
            url.as_str(), "https://example.com/a%20b/%C3%A4/100%25?q=a%20b&x=%C3%A4%25#f%20g%25"
        )
        self.assertEqual(url.path, "/a b/ä/100%")
        self.assertEqual(url.query["q"], "a b")
        self.assertEqual(url.query["x"], "ä%")

    def test_assigning_path_encodes(self) -> None:
        """
        Test that the path attribute takes a decoded value: a "%" is a
        percent sign, not the start of an escape.
        """
        url = Url("https://example.com/")
        url.path = "/a b/c%2Fd"
        self.assertEqual(url.raw_path, "/a%20b/c%252Fd")
        self.assertEqual(url.path, "/a b/c%2Fd")

    def test_assigning_raw_path_keeps_escapes(self) -> None:
        """
        Test that raw_path takes an encoded value and only encodes what
        cannot be raw in a path.
        """
        url = Url("https://example.com/")
        url.raw_path = "/a%2Fb c/ä?x#y"
        self.assertEqual(url.raw_path, "/a%2Fb%20c/%C3%A4%3Fx%23y")
        self.assertEqual(url.path, "/a/b c/ä?x#y")
        self.assertEqual(url.as_str(), "https://example.com/a%2Fb%20c/%C3%A4%3Fx%23y")
        self.assertEqual(Url(url.as_str()), url)

        url.raw_fragment = "a%2Fb c"
        self.assertEqual(url.raw_fragment, "a%2Fb%20c")
        self.assertEqual(url.fragment, "a/b c")

    def test_name_is_one_segment(self) -> None:
        """
        Test that the name is split on real slashes only and that a "/" in
        an assigned name is encoded.
        """
        url = Url("https://example.com/dir/a%2Fb.txt")
        self.assertEqual(url.name, "a/b.txt")
        self.assertEqual(url.suffix, ".txt")
        self.assertEqual(url.parent.as_str(), "https://example.com/dir")
        url.name = "x/y z.txt"
        self.assertEqual(url.as_str(), "https://example.com/dir/x%2Fy%20z.txt")

    def test_equality_of_escapes(self) -> None:
        """
        Test that only equivalent spellings are equal (RFC 3986, 6.2.2):
        escapes of unreserved characters and the case of the hex digits
        don't matter, escaped reserved characters do.
        """
        self.assertEqual(Url("https://example.com/%7Euser"), Url("https://example.com/~user"))
        self.assertEqual(Url("https://example.com/a%c3%a4"), Url("https://example.com/a%C3%A4"))
        self.assertEqual(
            Url("https://example.com/a%20b"),
            Url(scheme="https", hostname="example.com", path="/a b"),
        )
        self.assertNotEqual(Url("https://example.com/a%2Fb"), Url("https://example.com/a/b"))
        self.assertNotEqual(Url("https://example.com/a%3Fb"), Url("https://example.com/a?b"))
        self.assertEqual(Url("https://u%7E@example.com/#%7E"), Url("https://u~@example.com/#~"))

    def test_normalize_canonicalizes_escapes(self) -> None:
        """
        Test that normalize() brings escapes into their canonical form.
        """
        url = Url("https://example.com/%7euser/a%2fb/%c3%a4#%7e").normalize()
        self.assertEqual(url.as_str(), "https://example.com/~user/a%2Fb/%C3%A4#~")

    def test_escaped_slash_is_no_segment_separator(self) -> None:
        """
        Test that an escaped "/" takes no part in resolving dot segments
        (regression: "/a%2F..%2Fb" was normalized to "/b").
        """
        url = Url("http://example.com/a%2F..%2Fb")
        self.assertEqual(url.normalize().as_str(), "http://example.com/a%2F..%2Fb")
        self.assertEqual(
            Url("http://example.com/b/c/d").join("a%2F..%2Fb").as_str(),
            "http://example.com/b/c/a%2F..%2Fb",
        )
        # an escaped dot segment is a dot segment
        self.assertEqual(Url("http://example.com/a/%2E%2e/b").normalize().path, "/b")


class UrlQueryEncodingTestCase(unittest.TestCase):
    """
    tests for how :py:class:`action0.url.base.Url` reads and writes its query
    """

    def test_unmodified_query_is_kept(self) -> None:
        """
        Test that the query is rendered as it was written (regression:
        "?foo+bar" became "?foo+bar=", "%20" became "+").
        """
        for query in ("foo+bar", "flag&a=1", "q=a%20b", "a=1&&b=2&", "r=https://x/y?z", "a=b=c"):
            with self.subTest(query=query):
                url_str = f"https://example.com/search?{query}"
                self.assertEqual(Url(url_str).as_str(), url_str)

    def test_modified_query_is_normalized(self) -> None:
        """
        Test that the query is written from its pairs once it was modified.
        """
        url = Url("https://example.com/?flag&q=a%20b&&x=1")
        url.query.add("y", 2)
        self.assertEqual(url.as_str(), "https://example.com/?flag=&q=a+b&x=1&y=2")

    def test_reading_does_not_modify(self) -> None:
        """
        Test that reading the parameters keeps the original spelling.
        """
        url_str = "https://example.com/?flag&q=a%20b"
        url = Url(url_str)
        self.assertEqual(url.query["q"], "a b")
        self.assertEqual(dict(url.query), {"flag": "", "q": "a b"})
        self.assertEqual(url.query.remove("missing"), [])
        self.assertEqual(url.as_str(), url_str)

    def test_form_encoding_for_web_schemes(self) -> None:
        """
        Test that a "+" is a space for the web schemes and for URLs
        without a scheme.
        """
        for url_str in (
            "https://h/?q=a+b",
            "http://h/?q=a+b",
            "wss://h/?q=a+b",
            "//h/?q=a+b",
            "?q=a+b",
        ):
            with self.subTest(url=url_str):
                url = Url(url_str)
                self.assertTrue(url.query.form_encoding)
                self.assertEqual(url.query["q"], "a b")

    def test_no_form_encoding_for_other_schemes(self) -> None:
        """
        Test that a "+" is a plus sign elsewhere (regression: the body of
        "mailto:a@b.com?body=1+1=2" was read as "1 1=2").
        """
        url_str = "mailto:a@b.com?subject=Hello%20World&body=1+1=2"
        url = Url(url_str)
        self.assertFalse(url.query.form_encoding)
        self.assertEqual(url.query["body"], "1+1=2")
        self.assertEqual(url.query["subject"], "Hello World")
        self.assertEqual(url.as_str(), url_str)

        url.query.add("cc", "x y+z")
        self.assertEqual(
            url.as_str(), "mailto:a@b.com?subject=Hello%20World&body=1+1%3D2&cc=x%20y+z"
        )
        self.assertEqual(Url("myapp://open?q=a+b").query["q"], "a+b")

    def test_scheme_argument_decides(self) -> None:
        """
        Test that a scheme given as keyword argument decides how a base
        url without a scheme is read, and how assigned queries are written.
        """
        self.assertEqual(Url("?q=a+b", scheme="mailto").query["q"], "a+b")
        self.assertEqual(Url("?q=a+b", scheme="https").query["q"], "a b")
        self.assertEqual(
            Url(scheme="myapp", hostname="h", query={"q": "a b"}).as_str(), "myapp://h?q=a%20b"
        )
        self.assertEqual(
            Url(scheme="https", hostname="h", query={"q": "a b"}).as_str(), "https://h?q=a+b"
        )

    def test_form_encoding_can_be_overridden(self) -> None:
        """
        Test that the Params attribute overrides what the scheme implies.
        """
        url = Url("myapp://open?q=a+b")
        url.query.form_encoding = True
        self.assertEqual(url.as_str(), "myapp://open?q=a%2Bb")
        self.assertEqual(url.copy().query.form_encoding, True)

    def test_equality_ignores_query_spelling(self) -> None:
        """
        Test that queries are compared by their parameters.
        """
        self.assertEqual(Url("https://h/?a=%20&flag"), Url("https://h/?flag=&a=+"))


class UrlJoinEdgeCasesTestCase(unittest.TestCase):
    """
    more tests for :py:meth:`action0.url.base.Url.join`
    """

    def test_semicolon_for_schemes_without_path_params(self) -> None:
        """
        Test that the reference is read in the context of the base URL
        (regression: "report;final.txt" joined onto a file URL lost
        ";final.txt" from the path).
        """
        url = Url("file:///a/b").join("report;final.txt")
        self.assertEqual(url.as_str(), "file:///a/report;final.txt")
        self.assertEqual(url.path, "/a/report;final.txt")
        self.assertEqual(url.name, "report;final.txt")
        self.assertEqual(Url(url.as_str()), url)
        self.assertEqual(Url("s3://bucket/dir/").join("key;v1").as_str(), "s3://bucket/dir/key;v1")

        url = Url("/a/report;final.txt", scheme="file")
        self.assertEqual(url.path, "/a/report;final.txt")
        self.assertEqual(url.as_str(), "file:///a/report;final.txt")

    def test_empty_query_reference_clears_the_query(self) -> None:
        """
        Test that "?" replaces the query with an empty one, like in
        browsers (regression: the query of the base URL was kept).
        """
        base = Url("http://example.com/list?filter=x#top")
        self.assertEqual(base.join("?").as_str(), "http://example.com/list")
        self.assertEqual(base.join("?#x").as_str(), "http://example.com/list#x")
        self.assertEqual(base.join("#x").as_str(), "http://example.com/list?filter=x#x")
        # the fragment is the one of the reference: none
        self.assertEqual(base.join("").as_str(), "http://example.com/list?filter=x")
        self.assertEqual(base.join("#").as_str(), "http://example.com/list?filter=x")

    def test_strict_resolution(self) -> None:
        """
        Test the cases where RFC 3986 and urllib's urljoin differ: a
        reference with a scheme is never treated as relative.
        """
        self.assertEqual(Url("http://a/b/c/d").join("http:g").as_str(), "http:g")
        self.assertEqual(Url("http://a/b/c/d").join("g//h").as_str(), "http://a/b/c/g//h")

    def test_rootless_base(self) -> None:
        """
        Test bases with a scheme but without a "/" in their path: the
        result is an absolute URL without dot segments (regression:
        "mailto:../g").
        """
        self.assertEqual(Url("mailto:x@y").join("../g").as_str(), "mailto:g")
        self.assertEqual(Url("urn:a:b").join(".").as_str(), "urn:")
        self.assertEqual(Url("myapp:a/b").join("../g").as_str(), "myapp:/g")
        self.assertEqual(Url("mailto:a@b.c").join("x").as_str(), "mailto:x")

    def test_dot_segment_with_path_params_is_literal(self) -> None:
        """
        Test that "..;x" is a segment named ".." with params, not a dot
        segment (RFC 3986, section 3.3).
        """
        self.assertEqual(Url("http://a/b/c/d").join("..;x=1").as_str(), "http://a/b/c/..;x=1")
        self.assertEqual(
            Url("http://example.com/a/b/..;x=1").normalize().as_str(),
            "http://example.com/a/b/..;x=1",
        )

    def test_result_has_the_class_of_the_base(self) -> None:
        """
        Test that the class of the result does not depend on the reference
        (regression: joining a Url instance returned its class).
        """

        class MyUrl(Url):
            pass

        self.assertIs(type(MyUrl("http://h/a").join(Url("http://o/b"))), MyUrl)
        self.assertIs(type(MyUrl("http://h/a").join("http://o/b")), MyUrl)
        self.assertIs(type(Url("http://h/a").join(MyUrl("http://o/b"))), Url)
        self.assertEqual(MyUrl("http://h/a").join(Url("http://o/b")).as_str(), "http://o/b")

    def test_reference_is_not_modified_or_shared(self) -> None:
        """
        Test that the result shares nothing with a Url given as reference.
        """
        reference = Url("b?x=1")
        result = Url("http://h/a").join(reference)
        result.query.add("y", 2)
        self.assertEqual(reference.as_str(), "b?x=1")

    def test_invalid_reference(self) -> None:
        """
        Test that something that is no URL raises (regression:
        ``join(None)`` returned a copy of the base).
        """
        with self.assertRaises(TypeError):
            Url("http://h/a").join(cast(Any, None))
        with self.assertRaises(ValueError):
            Url("http://h/a").join("http://h:port/")


class UrlPathParamsSegmentTestCase(unittest.TestCase):
    """
    tests that the path params of :py:class:`action0.url.base.Url` stay
    with the last path segment they belong to
    """

    def test_parent_drops_path_params(self) -> None:
        """
        Test that the params of the removed segment are removed with it
        (regression: they moved on to the parent segment).
        """
        url = Url("http://example.com/a/b;x=1?q=1#f")
        self.assertEqual(url.parent.as_str(), "http://example.com/a?q=1#f")
        self.assertEqual(url.as_str(), "http://example.com/a/b;x=1?q=1#f")

    def test_appending_keeps_path_params_on_their_segment(self) -> None:
        """
        Test that the params stay where they are when a segment is
        appended (regression: they moved on to the new last segment).
        """
        url = Url("http://example.com/a;p=1") / "b"
        self.assertEqual(url.as_str(), "http://example.com/a;p=1/b")
        self.assertEqual(url.path, "/a;p=1/b")
        self.assertFalse(url.path_params)
        self.assertEqual(Url(url.as_str()), url)


class UrlRobustnessTestCase(unittest.TestCase):
    """
    tests for repr(), error messages and copying of
    :py:class:`action0.url.base.Url`
    """

    def test_repr_of_subclass_with_own_constructor(self) -> None:
        """
        Test that repr() does not depend on the constructor (regression:
        with a password it went through copy() and raised a TypeError).
        """

        class TenantUrl(Url):
            def __init__(self, url: str, tenant: str) -> None:
                super().__init__(url)
                self.tenant = tenant

        url = TenantUrl("http://user:secret@example.com/", "acme")
        self.assertEqual(repr(url), "TenantUrl(http://user:***@example.com/)")

        copied = url.copy(port=8080)
        self.assertIsInstance(copied, TenantUrl)
        self.assertEqual(copied.tenant, "acme")
        self.assertEqual(copied.as_str(), "http://user:secret@example.com:8080/")
        self.assertIsInstance(url.origin(), TenantUrl)
        self.assertIsInstance(url / "a", TenantUrl)

    def test_repr_never_raises(self) -> None:
        """
        Test that repr() survives whatever a subclass does.
        """

        class Broken(Url):
            def _render(self, *, redact_password: bool) -> str:
                raise RuntimeError("boom")

        self.assertEqual(repr(Broken("http://example.com/")), "Broken(<unrenderable>)")

    def test_password_not_in_error_message(self) -> None:
        """
        Test that the errors for an unparsable URL do not quote the
        password (regression: urllib's message contained the netloc).
        """
        for url_str in (
            "https://user:secret@ho℀st/",
            "https://user:secret@example.com:port/",
            "https://user:secret@[::1/",
            "https://user:secret@exa mple.com/",
        ):
            with self.subTest(url=url_str):
                with self.assertRaises(ValueError) as caught:
                    Url(url_str)
                self.assertNotIn("secret", str(caught.exception))
                # the original error (with the password) is not chained
                self.assertIsNone(caught.exception.__cause__)
                self.assertTrue(
                    caught.exception.__context__ is None or caught.exception.__suppress_context__
                )

    def test_copy_module(self) -> None:
        """
        Test that copy.copy() and copy.deepcopy() give independent Urls
        (regression: a shallow copy shared the query).
        """
        url = Url("http://example.com/?a=1")
        for copier in (copy.copy, copy.deepcopy):
            with self.subTest(copier=copier.__name__):
                copied = copier(url)
                copied.query.add("b", 2)
                copied.path_params.add("v", 1)
                self.assertEqual(url.as_str(), "http://example.com/?a=1")
                self.assertEqual(copied.as_str(), "http://example.com/;v=1?a=1&b=2")

    def test_deepcopy_of_subclass_attributes(self) -> None:
        """
        Test that deepcopy() also copies what a subclass adds.
        """

        class TaggedUrl(Url):
            def __init__(self, url: str, tags: list[str]) -> None:
                super().__init__(url)
                self.tags = tags

        url = TaggedUrl("http://example.com/", ["a"])
        self.assertIs(copy.copy(url).tags, url.tags)
        deep = copy.deepcopy(url)
        self.assertEqual(deep.tags, ["a"])
        self.assertIsNot(deep.tags, url.tags)

    def test_pickle(self) -> None:
        """
        Test that a Url survives pickling.
        """
        url = Url("http://user:pass@example.com:1/a%2Fb;v=1?flag&x=1#f")
        restored = pickle.loads(pickle.dumps(url))
        self.assertEqual(restored, url)
        self.assertEqual(restored.as_str(), url.as_str())


class UrlEquivalenceTestCase(unittest.TestCase):
    """
    tests that :py:class:`action0.url.base.Url` instances that render the
    same are equal
    """

    def test_equal_after_render_and_parse(self) -> None:
        """
        Test that a Url equals the Url parsed from its string
        (regression: IDNA hostnames, hostname case and relative paths
        behind a host did not).
        """
        urls = [
            Url("http://bücher.example/"),
            Url(scheme="http", hostname="EXAMPLE.com", path="/"),
            Url(scheme="https", hostname="example.com", path="index.html"),
            Url(scheme="https", hostname="::1", port=8443, path="/a b;c", fragment="ä"),
            Url(scheme="https", hostname="example.com", username="a:b", password="c@d/e"),
            Url("redis://:secret@localhost:6379/0"),
            Url("mailto:me@example.com?subject=a+b"),
            Url("../a/b;v=1?x=1#f"),
            Url("http://[v1.fe]/"),
            Url("http://[fe80::1%25eth0]:80/"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(Url(url.as_str()), url)
                self.assertEqual(Url(url.as_str()).as_str(), url.as_str())

    def test_hostname_and_its_idna_form(self) -> None:
        """
        Test that a hostname equals its punycode form.
        """
        self.assertEqual(Url("http://bücher.example/"), Url("http://xn--bcher-kva.example/"))

    def test_path_param_order_ignored(self) -> None:
        """
        Test that, like for the query, the order of path param names
        doesn't matter.
        """
        self.assertEqual(Url("http://h/a;x=1;y=2"), Url("http://h/a;y=2;x=1"))
        self.assertNotEqual(Url("http://h/a;x=1;x=2"), Url("http://h/a;x=2;x=1"))


class UrlSpellingTestCase(unittest.TestCase):
    """
    tests for the documented differences between a URL string and what
    :py:meth:`action0.url.base.Url.as_str` renders for it
    """

    def test_exact_round_trips(self) -> None:
        """
        Test URL forms that have to come back unchanged.
        """
        for url_str in (
            "http:/path",
            "http:path",
            "file:///etc/hosts",
            "file:relative",
            "http://[v1.fe]/",
            "mailto:me@example.com",
            "urn:isbn:0451450523",
            "tel:+1-816-555-1212",
            "https://example.com",
            "https://example.com/",
            "//example.com",
        ):
            with self.subTest(url=url_str):
                self.assertEqual(Url(url_str).as_str(), url_str)

    def test_normalized_spellings(self) -> None:
        """
        Test the things that are normalized: case of scheme and hostname,
        delimiters without content and the authority of file URLs.
        """
        cases = {
            "HTTP://EXAMPLE.com/A": "http://example.com/A",
            "https://example.com/?": "https://example.com/",
            "https://example.com/#": "https://example.com/",
            "https://user:@example.com/": "https://user@example.com/",
            "https://@example.com/": "https://example.com/",
            "file:/etc/hosts": "file:///etc/hosts",
        }
        for url_str, expected in cases.items():
            with self.subTest(url=url_str):
                self.assertEqual(Url(url_str).as_str(), expected)

    def test_file_url_from_parts(self) -> None:
        """
        Test that a file URL built from parts gets its empty authority.
        """
        self.assertEqual(Url(scheme="file", path="/etc/hosts").as_str(), "file:///etc/hosts")

    def test_empty_authority_round_trips(self) -> None:
        """
        Test that an authority that is present but empty is kept
        (regression: "sqlite:///data.db" was rendered as "sqlite:/data.db",
        which is a different URL and nothing a database driver accepts).
        """
        for url_str in (
            "sqlite:///relative.db",
            "sqlite:////absolute/path.db",
            "postgresql:///dbname",
            "unix:///var/run/app.sock",
            "myapp:///path",
            "http:///path",
            "//",
            "///path",
            "myapp://",
        ):
            with self.subTest(url=url_str):
                url = Url(url_str)
                self.assertEqual(url.hostname, "")
                self.assertEqual(url.as_str(), url_str)
                self.assertEqual(Url(url.as_str()), url)

    def test_empty_authority_is_not_no_authority(self) -> None:
        """
        Test that the hostname "" (empty authority) and None (no
        authority) are told apart.
        """
        self.assertIsNone(Url("sqlite:/data.db").hostname)
        self.assertEqual(Url("sqlite:/data.db").as_str(), "sqlite:/data.db")
        self.assertNotEqual(Url("sqlite:///data.db"), Url("sqlite:/data.db"))
        # file URLs are always rendered with their "//", so these are equal
        self.assertEqual(Url("file:///etc/hosts"), Url("file:/etc/hosts"))
        # a netloc with only userinfo is an authority, but has no hostname
        self.assertIsNone(Url("postgresql://user:pw@/dbname").hostname)
        self.assertEqual(
            Url("postgresql://user:pw@/dbname").as_str(), "postgresql://user:pw@/dbname"
        )

    def test_empty_authority_from_parts(self) -> None:
        """
        Test building and removing an empty authority.
        """
        url = Url(scheme="sqlite", hostname="", path="/data.db")
        self.assertEqual(url.as_str(), "sqlite:///data.db")
        self.assertEqual(Url(scheme="sqlite", authority="", path="/data.db"), url)
        self.assertEqual(url.authority, "")

        url.hostname = None
        self.assertEqual(url.as_str(), "sqlite:/data.db")
        url.authority = ""
        self.assertEqual(url.as_str(), "sqlite:///data.db")
        url.authority = None
        self.assertIsNone(url.hostname)

    def test_empty_authority_reference(self) -> None:
        """
        Test that a reference with an empty authority replaces the one of
        the base URL (RFC 3986, section 5.2.2).
        """
        self.assertEqual(Url("http://a/b/c").join("///g").as_str(), "http:///g")

    def test_query_of_other_schemes_is_kept(self) -> None:
        """
        Test that the query of a non-web URL is not re-encoded either
        (connection strings carry paths in it).
        """
        url_str = "postgresql://user:pw@/dbname?host=/var/run/postgresql&sslmode=require"
        url = Url(url_str)
        self.assertEqual(url.as_str(), url_str)
        self.assertEqual(url.query["host"], "/var/run/postgresql")


class UrlOriginAndNormalizeTestCase(unittest.TestCase):
    """
    more tests for :py:meth:`action0.url.base.Url.origin` and
    :py:meth:`action0.url.base.Url.normalize`
    """

    def test_origin_without_default_port(self) -> None:
        """
        Test that the default port is not part of the origin (regression:
        "https://example.com:443" and "https://example.com" differed).
        """
        self.assertEqual(
            Url("https://example.com:443/a").origin(), Url("https://example.com/b").origin()
        )
        self.assertEqual(Url("https://example.com:443/a").origin().as_str(), "https://example.com")
        self.assertEqual(Url("https://example.com:8443/a").origin().port, 8443)
        self.assertNotEqual(
            Url("http://example.com/").origin(), Url("https://example.com/").origin()
        )

    def test_normalize_empty_first_segment_stays_relative(self) -> None:
        """
        Test the regression that "a/..//b" was normalized to "/b".
        """
        url = Url("a/..//b").normalize()
        self.assertEqual(url.as_str(), ".//b")
        self.assertEqual(Url(".//b").normalize().as_str(), ".//b")

    def test_normalize_path_is_absolute_behind_any_authority(self) -> None:
        """
        Test that the path is made absolute for an authority without a
        hostname as well (regression: "http://:80/a" became "http:a").
        """
        url = Url(scheme="http", port=80, path="a")
        self.assertEqual(url.as_str(), "http://:80/a")
        self.assertEqual(url.normalize().as_str(), "http:/a")

    def test_normalize_is_stable(self) -> None:
        """
        Test that normalizing what a normalized URL renders as changes
        nothing (regression: "file:" needed two rounds).
        """
        for url_str in (
            "file:",
            "file:/a/../b",
            "http://:80/a",
            "a/..//b",
            "./a:b",
            "//",
            "x:a/../..",
        ):
            with self.subTest(url=url_str):
                normalized = Url(url_str).normalize().as_str()
                self.assertEqual(Url(normalized).as_str(), normalized)
                self.assertEqual(Url(normalized).normalize().as_str(), normalized)

    def test_normalize_adds_root_path_for_any_scheme(self) -> None:
        """
        Test that an empty path behind an authority becomes "/" (RFC
        3986, section 6.2.3), whatever the scheme is.
        """
        self.assertEqual(
            Url("redis://localhost:6379").normalize().as_str(), "redis://localhost:6379/"
        )


if __name__ == "__main__":
    unittest.main()
