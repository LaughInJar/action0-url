import unittest

from action0.url import Params


class ParamsInitTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.__init__`
    """

    def test_separator_init(self) -> None:
        """
        Test that the separator is stored regardless of how params are given.
        """
        self.assertEqual(Params().separator, "&")
        self.assertEqual(Params(params=None, separator="&").separator, "&")
        self.assertEqual(Params(None, "&").separator, "&")
        self.assertEqual(Params("a=b", "&").separator, "&")

        self.assertEqual(Params(separator=";").separator, ";")
        self.assertEqual(Params(params=None, separator=";").separator, ";")
        self.assertEqual(Params(None, ";").separator, ";")
        self.assertEqual(Params("a=b", ";").separator, ";")

    def test_empty_init(self) -> None:
        """
        Test initialization with no params
        """
        params = Params()
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, "&")

    def test_empty_init_with_none(self) -> None:
        """
        Test initialization with `None` for params
        """
        params = Params(None)
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, "&")

        params = Params(params=None)
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, "&")

    def test_empty_init_with_separator(self) -> None:
        """
        Test initialization with `None` for params and a separator
        """
        params = Params(separator=";")
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, ";")

        params = Params(None, ";")
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, ";")

        params = Params(params=None, separator=";")
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, ";")

    def test_string_init_single_param(self) -> None:
        """
        Test initialization from a query string with a single parameter.
        """
        params = Params("foo=bar")
        self.assertEqual(params.as_dict(), {"foo": ["bar"]})
        self.assertEqual(params.as_str(), "foo=bar")

    def test_string_init_multiple_params(self) -> None:
        """
        Test initialization from a query string with multiple parameters.
        """
        params = Params("foo=bar&a=b")
        self.assertEqual(params.as_dict(), {"foo": ["bar"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar&a=b")

    def test_string_init_multiple_params_separator(self) -> None:
        """
        Test initialization from a ";"-separated string of parameters.
        """
        params = Params("foo=bar;a=b", separator=";")
        self.assertEqual(params.as_dict(), {"foo": ["bar"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar;a=b")

    def test_string_init_multiple_params_duplicates(self) -> None:
        """
        Test that duplicate keys in a query string collect all their values.
        """
        params = Params("foo=bar&a=b&foo=baz")
        self.assertEqual(params.as_dict(), {"foo": ["bar", "baz"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar&foo=baz&a=b")

    def test_dict_init_single_param(self) -> None:
        """
        Test initialization from a dict with a single parameter.
        """
        params = Params({"foo": "bar"})
        self.assertEqual(params.as_dict(), {"foo": ["bar"]})
        self.assertEqual(params.as_str(), "foo=bar")

    def test_dict_init_multiple_params(self) -> None:
        """
        Test initialization from a dict with multiple parameters.
        """
        params = Params({"foo": "bar", "a": "b"})
        self.assertEqual(params.as_dict(), {"foo": ["bar"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar&a=b")

    def test_dict_init_multiple_params_separator(self) -> None:
        """
        Test initialization from a dict combined with the ";" separator.
        """
        params = Params({"foo": "bar", "a": "b"}, separator=";")
        self.assertEqual(params.as_dict(), {"foo": ["bar"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar;a=b")

    def test_dict_init_multiple_params_duplicates(self) -> None:
        """
        A dict cannot have duplicate keys, so duplicates are expressed as a
        list of values for a key.
        """
        params = Params({"foo": ["bar", "baz"], "a": "b"})
        self.assertEqual(params.as_dict(), {"foo": ["bar", "baz"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar&foo=baz&a=b")

    def test_tuple_init_single_param(self) -> None:
        """
        Test initialization from a list of tuples with a single parameter.
        """
        params = Params([("foo", "bar")])
        self.assertEqual(params.as_dict(), {"foo": ["bar"]})
        self.assertEqual(params.as_str(), "foo=bar")

    def test_tuple_init_multiple_params(self) -> None:
        """
        Test initialization from a list of tuples with multiple parameters.
        """
        params = Params([("foo", "bar"), ("a", "b")])
        self.assertEqual(params.as_dict(), {"foo": ["bar"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar&a=b")

    def test_tuple_init_multiple_params_separator(self) -> None:
        """
        Test initialization from a list of tuples combined with the ";" separator.
        """
        params = Params([("foo", "bar"), ("a", "b")], separator=";")
        self.assertEqual(params.as_dict(), {"foo": ["bar"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar;a=b")

    def test_tuple_init_multiple_params_duplicates(self) -> None:
        """
        Test that repeated keys and iterable values in a list of tuples
        collect all their values.
        """
        params = Params([("foo", "bar"), ("a", "b"), ("foo", "baz"), ("a", ["c", "d"])])
        self.assertEqual(params.as_dict(), {"foo": ["bar", "baz"], "a": ["b", "c", "d"]})
        self.assertEqual(params.as_str(), "foo=bar&foo=baz&a=b&a=c&a=d")


class ParamsAddTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.add`
    """

    def test_add_new_key(self) -> None:
        """
        Test adding a value for a key that does not exist yet.
        """
        params = Params()
        params.add("foo", "bar")
        self.assertEqual(params.as_dict(), {"foo": ["bar"]})

    def test_add_existing_key_appends(self) -> None:
        """
        Test that adding to an existing key keeps the previous values.
        """
        params = Params("foo=bar")
        params.add("foo", "baz")
        self.assertEqual(params.as_dict(), {"foo": ["bar", "baz"]})

    def test_add_multiple_values(self) -> None:
        """
        Test adding an iterable of values at once.
        """
        params = Params("foo=bar")
        params.add("foo", ["baz", "abc"])
        self.assertEqual(params.as_dict(), {"foo": ["bar", "baz", "abc"]})


class ParamsSetTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.set`
    """

    def test_set_new_key(self) -> None:
        """
        Test that setting a missing key adds it.
        """
        params = Params()
        params.set("foo", "bar")
        self.assertEqual(params.as_dict(), {"foo": ["bar"]})

    def test_set_replaces_all_values(self) -> None:
        """
        Test that setting an existing key discards all previous values.
        """
        params = Params("foo=bar&foo=baz")
        params.set("foo", "abc")
        self.assertEqual(params.as_dict(), {"foo": ["abc"]})

    def test_set_multiple_values(self) -> None:
        """
        Test setting an iterable of values at once.
        """
        params = Params("foo=bar")
        params.set("foo", ["baz", "abc"])
        self.assertEqual(params.as_dict(), {"foo": ["baz", "abc"]})


class ParamsRemoveTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.remove`
    """

    def test_remove_key(self) -> None:
        """
        Test that removing by key alone removes and returns all its values.
        """
        params = Params("foo=bar&foo=baz&a=b")
        removed = params.remove("foo")
        self.assertEqual(removed, ["bar", "baz"])
        self.assertEqual(params.as_dict(), {"a": ["b"]})

    def test_remove_missing_key(self) -> None:
        """
        Test that removing an unknown key returns an empty list.
        """
        params = Params("a=b")
        self.assertEqual(params.remove("foo"), [])
        self.assertEqual(params.as_dict(), {"a": ["b"]})

    def test_remove_single_value(self) -> None:
        """
        Test that removing one value keeps the key's other values.
        """
        params = Params("foo=bar&foo=baz")
        removed = params.remove("foo", "bar")
        self.assertEqual(removed, ["bar"])
        self.assertEqual(params.as_dict(), {"foo": ["baz"]})

    def test_remove_multiple_values(self) -> None:
        """
        Test removing several values at once.
        """
        params = Params("foo=bar&foo=baz&foo=abc")
        removed = params.remove("foo", ["bar", "abc"])
        self.assertEqual(removed, ["bar", "abc"])
        self.assertEqual(params.as_dict(), {"foo": ["baz"]})

    def test_remove_returns_only_removed_values(self) -> None:
        """
        Test that only the actually removed values are returned, not the
        kept ones (regression: all values used to be returned).
        """
        params = Params("foo=bar&foo=baz")
        removed = params.remove("foo", ["baz", "nope"])
        self.assertEqual(removed, ["baz"])
        self.assertEqual(params.as_dict(), {"foo": ["bar"]})

    def test_remove_value_missing(self) -> None:
        """
        Test that removing a value that is not present changes nothing.
        """
        params = Params("foo=bar")
        self.assertEqual(params.remove("foo", "nope"), [])
        self.assertEqual(params.as_dict(), {"foo": ["bar"]})

    def test_remove_last_value_removes_key(self) -> None:
        """
        Test that a key disappears once its last value is removed
        (regression: an empty list used to linger).
        """
        params = Params("foo=bar&a=b")
        removed = params.remove("foo", "bar")
        self.assertEqual(removed, ["bar"])
        self.assertNotIn("foo", params.as_dict())


class ParamsClearTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.clear`
    """

    def test_clear(self) -> None:
        """
        Test that clear empties the params and returns what was removed.
        """
        params = Params("foo=bar&foo=baz&a=b")
        old = params.clear()
        self.assertEqual(old, {"foo": ["bar", "baz"], "a": ["b"]})
        self.assertEqual(params.as_dict(), {})
        self.assertEqual(params.as_str(), "")


class ParamsAsStrTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.as_str`
    """

    def test_url_encoding(self) -> None:
        """
        Test that names and values are url encoded.
        """
        params = Params({"a b": "c d", "x": "1&2"})
        self.assertEqual(params.as_str(), "a+b=c+d&x=1%262")

    def test_sort(self) -> None:
        """
        Test sorting by name and then by value (regression: sorting used to
        drop all values).
        """
        params = Params("b=2&a=3&a=1")
        self.assertEqual(params.as_str(sort=True), "a=1&a=3&b=2")
        # sorting only affects the output, not the stored order
        self.assertEqual(params.as_str(), "b=2&a=3&a=1")

    def test_separator_output(self) -> None:
        """
        Test that a ";" separator is actually used in the output (regression:
        the replacement used to be discarded).
        """
        params = Params("a=1;b=2", separator=";")
        self.assertEqual(params.as_str(), "a=1;b=2")

    def test_separator_does_not_corrupt_values(self) -> None:
        """
        Test that a literal separator inside a value stays percent-encoded and
        is not affected by the separator replacement.
        """
        params = Params({"a": "1;2", "b": "x&y"}, separator=";")
        self.assertEqual(params.as_str(), "a=1%3B2;b=x%26y")

    def test_str_dunder(self) -> None:
        """
        Test that str() and repr() are based on as_str().
        """
        params = Params("foo=bar&a=b")
        self.assertEqual(str(params), "foo=bar&a=b")
        self.assertEqual(repr(params), "Params(foo=bar&a=b)")


class ParamsViewsTestCase(unittest.TestCase):
    """
    tests for the read-only views of :py:class:`action0.url.params.Params`
    (as_tuples, as_single_tuples, as_dict, singles, uniq_tuples)
    """

    def setUp(self) -> None:
        self.params = Params("foo=bar&foo=baz&a=b")

    def test_as_tuples(self) -> None:
        """
        Test the tuples view with the values as lists.
        """
        self.assertEqual(list(self.params.as_tuples()), [("foo", ["bar", "baz"]), ("a", ["b"])])

    def test_as_single_tuples(self) -> None:
        """
        Test the tuples view with one tuple per value.
        """
        self.assertEqual(
            list(self.params.as_single_tuples()), [("foo", "bar"), ("foo", "baz"), ("a", "b")]
        )

    def test_as_dict_returns_copy(self) -> None:
        """
        Test that mutating the returned dict does not affect the params.
        """
        d = self.params.as_dict()
        d["new"] = ["value"]
        self.assertNotIn("new", self.params.as_dict())

    def test_singles(self) -> None:
        """
        Test that singles() keeps only the last value per key.
        """
        self.assertEqual(self.params.singles(), {"foo": "baz", "a": "b"})

    def test_uniq_tuples(self) -> None:
        """
        Test that uniq_tuples() yields one tuple per key with its last value.
        """
        self.assertEqual(list(self.params.uniq_tuples()), [("foo", "baz"), ("a", "b")])


if __name__ == "__main__":
    unittest.main()
