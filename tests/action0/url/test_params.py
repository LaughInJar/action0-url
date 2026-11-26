import datetime
import decimal
import unittest
import uuid
from collections.abc import MutableMapping
from typing import Any
from typing import Literal
from typing import cast

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
        Test that duplicate keys in a query string collect all their values
        while the representation order is preserved.
        """
        params = Params("foo=bar&a=b&foo=baz")
        self.assertEqual(params.as_dict(), {"foo": ["bar", "baz"], "a": ["b"]})
        self.assertEqual(params.as_str(), "foo=bar&a=b&foo=baz")

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
        collect all their values while the given order is preserved.
        """
        params = Params([("foo", "bar"), ("a", "b"), ("foo", "baz"), ("a", ["c", "d"])])
        self.assertEqual(params.as_dict(), {"foo": ["bar", "baz"], "a": ["b", "c", "d"]})
        self.assertEqual(params.as_str(), "foo=bar&a=b&foo=baz&a=c&a=d")

    def test_init_from_params(self) -> None:
        """
        Test that initialization from another Params instance copies all
        values and results in an independent instance.
        """
        source = Params("foo=bar&foo=baz&a=b")
        params = Params(source)
        self.assertEqual(params.as_dict(), {"foo": ["bar", "baz"], "a": ["b"]})

        params.add("foo", "new")
        self.assertEqual(source.as_dict(), {"foo": ["bar", "baz"], "a": ["b"]})

    def test_init_coerces_values(self) -> None:
        """
        Test that non-string values are coerced on initialization.
        """
        params = Params({"page": 2, "ratio": 1.5, "debug": True, "verbose": False})
        self.assertEqual(
            params.as_dict(),
            {"page": ["2"], "ratio": ["1.5"], "debug": ["true"], "verbose": ["false"]},
        )


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
        Test sorting by name, the values of one name keep their order
        (regression: sorting used to drop all values).
        """
        params = Params("b=2&a=3&a=1")
        self.assertEqual(params.as_str(sort=True), "a=3&a=1&b=2")
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


class ParamsMappingTestCase(unittest.TestCase):
    """
    tests for the MutableMapping interface of :py:class:`action0.url.params.Params`
    """

    def setUp(self) -> None:
        self.params = Params("foo=bar&foo=baz&a=b")

    def test_is_mutable_mapping(self) -> None:
        """
        Test that Params is registered as a MutableMapping.
        """
        self.assertIsInstance(self.params, MutableMapping)

    def test_getitem_returns_last_value(self) -> None:
        """
        Test that subscription returns the single (last) value.
        """
        self.assertEqual(self.params["foo"], "baz")
        self.assertEqual(self.params["a"], "b")

    def test_getitem_missing_key(self) -> None:
        """
        Test that subscription with an unknown name raises a KeyError.
        """
        with self.assertRaises(KeyError):
            self.params["nope"]

    def test_get(self) -> None:
        """
        Test the inherited get() with and without a default.
        """
        self.assertEqual(self.params.get("foo"), "baz")
        self.assertIsNone(self.params.get("nope"))
        self.assertEqual(self.params.get("nope", "fallback"), "fallback")

    def test_get_all(self) -> None:
        """
        Test that get_all() returns all values, or an empty list.
        """
        self.assertEqual(self.params.get_all("foo"), ["bar", "baz"])
        self.assertEqual(self.params.get_all("nope"), [])

    def test_get_all_returns_copy(self) -> None:
        """
        Test that mutating the returned list does not affect the params.
        """
        values = self.params.get_all("foo")
        values.append("mutated")
        self.assertEqual(self.params.get_all("foo"), ["bar", "baz"])

    def test_setitem_replaces_values(self) -> None:
        """
        Test that assignment replaces all values, like set().
        """
        self.params["foo"] = "new"
        self.assertEqual(self.params.get_all("foo"), ["new"])

        self.params["foo"] = ["x", "y"]
        self.assertEqual(self.params.get_all("foo"), ["x", "y"])

    def test_delitem(self) -> None:
        """
        Test that del removes the parameter with all its values.
        """
        del self.params["foo"]
        self.assertNotIn("foo", self.params)

    def test_delitem_missing_key(self) -> None:
        """
        Test that del with an unknown name raises a KeyError.
        """
        with self.assertRaises(KeyError):
            del self.params["nope"]

    def test_contains(self) -> None:
        """
        Test the "in" operator.
        """
        self.assertIn("foo", self.params)
        self.assertNotIn("nope", self.params)

    def test_len_counts_keys(self) -> None:
        """
        Test that len() counts distinct names, not values.
        """
        self.assertEqual(len(self.params), 2)

    def test_iter_yields_keys(self) -> None:
        """
        Test that iteration yields the parameter names.
        """
        self.assertEqual(list(self.params), ["foo", "a"])

    def test_bool(self) -> None:
        """
        Test that empty Params are falsy and non-empty ones truthy.
        """
        self.assertTrue(self.params)
        self.assertFalse(Params())

    def test_items_and_values_are_single_view(self) -> None:
        """
        Test that the inherited items() and values() use the single-value
        view (last value per key).
        """
        self.assertEqual(list(self.params.items()), [("foo", "baz"), ("a", "b")])
        self.assertEqual(list(self.params.values()), ["baz", "b"])

    def test_pop(self) -> None:
        """
        Test that the inherited pop() returns the single value and removes
        the whole parameter.
        """
        self.assertEqual(self.params.pop("foo"), "baz")
        self.assertNotIn("foo", self.params)


class ParamsCoercionTestCase(unittest.TestCase):
    """
    tests for the coercion of non-string parameter values
    """

    def test_add_int_and_float(self) -> None:
        """
        Test that ints and floats are stringified.
        """
        params = Params()
        params.add("page", 2)
        params.add("ratio", 1.5)
        self.assertEqual(params.as_str(), "page=2&ratio=1.5")

    def test_add_bool(self) -> None:
        """
        Test that bools become the web-style "true" / "false".
        """
        params = Params()
        params.add("debug", True)
        params.add("verbose", False)
        self.assertEqual(params.as_str(), "debug=true&verbose=false")

    def test_set_mixed_values(self) -> None:
        """
        Test coercion of a list with mixed value types.
        """
        params = Params()
        values: list[str | int | bool] = ["a", 1, True]
        params.set("mixed", values)
        self.assertEqual(params.get_all("mixed"), ["a", "1", "true"])

    def test_set_empty_values_removes_key(self) -> None:
        """
        Test that setting an empty list of values removes the parameter.
        """
        params = Params("foo=bar")
        params.set("foo", [])
        self.assertNotIn("foo", params)

    def test_remove_matches_coerced_values(self) -> None:
        """
        Test that remove() coerces the given value before matching.
        """
        params = Params("page=2&page=3")
        self.assertEqual(params.remove("page", 2), ["2"])
        self.assertEqual(params.get_all("page"), ["3"])


class ParamsUnsupportedValuesTestCase(unittest.TestCase):
    """
    tests for values outside of str/int/float/bool given to
    :py:class:`action0.url.params.Params`
    """

    def test_none_raises(self) -> None:
        """
        Test that None raises a helpful TypeError (regression: the message
        was "'NoneType' object is not iterable").
        """
        with self.assertRaisesRegex(TypeError, "must be str, int, float or bool.*NoneType"):
            Params(cast(Any, {"a": None}))
        with self.assertRaisesRegex(TypeError, "NoneType"):
            Params().add("a", cast(Any, ["1", None]))
        with self.assertRaisesRegex(TypeError, "NoneType"):
            # MutableMapping.setdefault() defaults to None
            cast(Any, Params()).setdefault("a")

    def test_bytes_raise(self) -> None:
        """
        Test that bytes raise (regression: they were silently iterated
        into one value per byte, "a=97&a=98").
        """
        for value in (b"ab", bytearray(b"ab"), memoryview(b"ab")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, type(value).__name__):
                    Params(cast(Any, {"a": value}))

    def test_failed_add_changes_nothing(self) -> None:
        """
        Test that a rejected value leaves the instance untouched.
        """
        params = Params("a=1")
        with self.assertRaises(TypeError):
            params.add("a", cast(Any, ["2", None]))
        self.assertEqual(params.as_str(), "a=1")

    def test_other_objects_are_stringified(self) -> None:
        """
        Test that non-iterable objects go through str() (regression: they
        raised "object is not iterable").
        """
        params = Params(
            cast(
                Any,
                {
                    "d": decimal.Decimal("1.50"),
                    "t": datetime.date(2026, 1, 31),
                    "u": uuid.UUID(int=1),
                    "l": [decimal.Decimal("2"), 3],
                },
            )
        )
        self.assertEqual(
            params.as_dict(),
            {
                "d": ["1.50"],
                "t": ["2026-01-31"],
                "u": ["00000000-0000-0000-0000-000000000001"],
                "l": ["2", "3"],
            },
        )

    def test_generator_of_values(self) -> None:
        """
        Test that any iterable of values works, not just lists.
        """
        params = Params()
        params.set("a", (index for index in range(3)))
        self.assertEqual(params.as_str(), "a=0&a=1&a=2")


class ParamsUpdateTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.update`
    """

    def test_update_replaces_existing_keys(self) -> None:
        """
        Test that update replaces the values of existing keys and adds new
        keys (dict.update semantics).
        """
        params = Params("a=1&a=2&b=3")
        params.update({"a": "x", "c": "y"})
        self.assertEqual(params.as_dict(), {"a": ["x"], "b": ["3"], "c": ["y"]})

    def test_update_from_query_string(self) -> None:
        """
        Test updating from a query string.
        """
        params = Params("a=1")
        params.update("a=x&b=2")
        self.assertEqual(params.as_dict(), {"a": ["x"], "b": ["2"]})

    def test_update_from_params_keeps_multi_values(self) -> None:
        """
        Test that updating from another Params instance keeps all values
        of a multi-value key.
        """
        params = Params("a=1")
        params.update(Params("a=x&a=y"))
        self.assertEqual(params.as_dict(), {"a": ["x", "y"]})

    def test_update_with_kwargs(self) -> None:
        """
        Test updating via keyword arguments.
        """
        params = Params("a=1")
        params.update(b="2", a=["x", "y"])
        self.assertEqual(params.as_dict(), {"a": ["x", "y"], "b": ["2"]})


class ParamsUpdateSignatureTestCase(unittest.TestCase):
    """
    tests for the positional-only first parameter of
    :py:meth:`action0.url.params.Params.update`
    """

    def test_keyword_named_params(self) -> None:
        """
        Test that a parameter named "params" can be updated as keyword
        (regression: it was taken for the query string to merge in).
        """
        params = Params("a=1")
        params.update(params="x")
        self.assertEqual(params.as_str(), "a=1&params=x")

    def test_positional_and_keyword_named_params(self) -> None:
        """
        Test combining the positional argument with a "params" keyword.
        """
        params = Params("a=1")
        params.update("b=2", params="x")
        self.assertEqual(params.as_str(), "a=1&b=2&params=x")


class ParamsFormEncodingTestCase(unittest.TestCase):
    """
    tests for the form_encoding flag of :py:class:`action0.url.params.Params`
    """

    def test_default_is_form_encoded(self) -> None:
        """
        Test that by default "+" and space are interchangeable.
        """
        params = Params("a=1+2&b=3%204")
        self.assertTrue(params.form_encoding)
        self.assertEqual(params.as_dict(), {"a": ["1 2"], "b": ["3 4"]})
        self.assertEqual(params.as_str(), "a=1+2&b=3+4")

    def test_plus_is_literal_without_form_encoding(self) -> None:
        """
        Test that without form encoding a "+" is a plus sign and a space
        is written as "%20".
        """
        params = Params("a=1+2;b=3%204", separator=";", form_encoding=False)
        self.assertEqual(params.as_dict(), {"a": ["1+2"], "b": ["3 4"]})
        self.assertEqual(params.as_str(), "a=1+2;b=3%204")

    def test_delimiters_encoded_without_form_encoding(self) -> None:
        """
        Test that characters which delimit the pairs or the path are
        always encoded and survive a round trip.
        """
        separators: tuple[Literal["&", ";"], ...] = ("&", ";")
        for separator in separators:
            with self.subTest(separator=separator):
                params = Params({"k=1": "a&b;c=d/e?f#g"}, separator=separator, form_encoding=False)
                rendered = params.as_str()
                self.assertEqual(rendered, "k%3D1=a%26b%3Bc%3Dd%2Fe%3Ff%23g")
                parsed = Params(rendered, separator=separator, form_encoding=False)
                self.assertEqual(parsed.as_dict(), {"k=1": ["a&b;c=d/e?f#g"]})

    def test_update_parses_with_own_encoding(self) -> None:
        """
        Test that update() parses a string like the instance itself would.
        """
        params = Params(separator=";", form_encoding=False)
        params.update("a=1+2")
        self.assertEqual(params["a"], "1+2")

    def test_not_taken_over_when_copying(self) -> None:
        """
        Test that, like the separator, the flag is not copied.
        """
        source = Params("a=1 2", separator=";", form_encoding=False)
        self.assertTrue(Params(source).form_encoding)
        self.assertEqual(Params(source).as_str(), "a=1+2")


class ParamsNormalizationTestCase(unittest.TestCase):
    """
    tests for the documented normalizations when parsing a string with
    :py:class:`action0.url.params.Params`
    """

    def test_key_without_equals_sign(self) -> None:
        """
        Test that a key without "=" is kept and rendered with one.
        """
        params = Params("flag&x=1")
        self.assertEqual(params.as_dict(), {"flag": [""], "x": ["1"]})
        self.assertEqual(params.as_str(), "flag=&x=1")

    def test_empty_pairs_dropped(self) -> None:
        """
        Test that empty pairs between separators are dropped.
        """
        self.assertEqual(Params("a=1&&b=2&").as_str(), "a=1&b=2")

    def test_escapes_canonicalized(self) -> None:
        """
        Test that escapes are rewritten in their canonical form.
        """
        self.assertEqual(Params("q=a%20b&r=%7e").as_str(), "q=a+b&r=~")

    def test_leading_question_mark_is_part_of_the_key(self) -> None:
        """
        Test that the string is the bare query: a "?" is not stripped.
        """
        self.assertEqual(Params("?a=1").as_dict(), {"?a": ["1"]})


class ParamsEqualityTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.__eq__`
    """

    def test_equal(self) -> None:
        """
        Test that equal parameters compare equal.
        """
        self.assertEqual(Params("a=1&a=2&b=3"), Params("a=1&a=2&b=3"))

    def test_key_order_ignored(self) -> None:
        """
        Test that the order of the parameter names does not matter.
        """
        self.assertEqual(Params("a=1&b=2"), Params("b=2&a=1"))

    def test_value_order_matters(self) -> None:
        """
        Test that the order of multiple values of one name does matter.
        """
        self.assertNotEqual(Params("a=1&a=2"), Params("a=2&a=1"))

    def test_separator_ignored(self) -> None:
        """
        Test that the separator is presentation only and does not affect
        equality.
        """
        self.assertEqual(Params("a=1&b=2"), Params("a=1;b=2", separator=";"))

    def test_equal_to_plain_mapping(self) -> None:
        """
        Test comparison with a plain dict (in single- and multi-value form).
        """
        self.assertEqual(Params("a=1&a=2&b=x"), {"a": ["1", "2"], "b": "x"})
        self.assertNotEqual(Params("a=1&a=2"), {"a": "2"})

    def test_mapping_with_unsupported_values_is_not_equal(self) -> None:
        """
        Test that comparing with a mapping holding values Params cannot
        hold is False (regression: it raised a TypeError).
        """
        params = Params("a=1")
        self.assertFalse(params == {"a": None})
        self.assertTrue(params != {"a": None})
        self.assertFalse(params == {"a": b"1"})

    def test_form_encoding_ignored(self) -> None:
        """
        Test that the form encoding does not matter, only keys and values.
        """
        self.assertEqual(Params("a=1 2"), Params("a=1%202", separator=";", form_encoding=False))

    def test_not_hashable(self) -> None:
        """
        Test that the mutable Params cannot be used as dictionary key.
        """
        with self.assertRaises(TypeError):
            hash(cast(Any, Params("a=1")))

    def test_not_equal_to_other_types(self) -> None:
        """
        Test that comparison with non-mappings is False, not an error.
        """
        self.assertNotEqual(Params("a=1"), "a=1")
        self.assertNotEqual(Params("a=1"), 42)


class ParamsBlankValuesTestCase(unittest.TestCase):
    """
    tests for the handling of blank parameter values
    """

    def test_blank_values_kept(self) -> None:
        """
        Test that blank values survive a parse/render round trip
        (regression: parse_qs drops them by default).
        """
        params = Params("a=&b=1")
        self.assertEqual(params.as_dict(), {"a": [""], "b": ["1"]})
        self.assertEqual(params.as_str(), "a=&b=1")

    def test_blank_value_access(self) -> None:
        """
        Test that a blank value behaves like any other value.
        """
        params = Params("a=")
        self.assertEqual(params["a"], "")
        self.assertEqual(params.get_all("a"), [""])
        self.assertIn("a", params)


class ParamsOrderTestCase(unittest.TestCase):
    """
    tests for the preservation of the representation order (values of
    duplicate keys interleaved with other keys)
    """

    def test_round_trip_preserves_interleaving(self) -> None:
        """
        Test that parsing and re-rendering keeps interleaved duplicates
        (regression: values used to be grouped per key).
        """
        self.assertEqual(Params("a=1&b=2&a=3").as_str(), "a=1&b=2&a=3")

    def test_add_appends_at_the_end(self) -> None:
        """
        Test that add() appends pairs at the end of the representation.
        """
        params = Params("a=1&b=2")
        params.add("a", "3")
        self.assertEqual(params.as_str(), "a=1&b=2&a=3")

    def test_set_replaces_at_first_position(self) -> None:
        """
        Test that set() places the new values at the key's first position
        and drops the key's other pairs.
        """
        params = Params("a=1&b=2&a=3")
        params.set("a", ["x", "y"])
        self.assertEqual(params.as_str(), "a=x&a=y&b=2")

    def test_update_keeps_first_position(self) -> None:
        """
        Test that update() replaces existing keys in place and appends new
        ones at the end.
        """
        params = Params("a=1&b=2&a=3")
        params.update({"a": "x", "c": "y"})
        self.assertEqual(params.as_str(), "a=x&b=2&c=y")

    def test_as_single_tuples_representation_order(self) -> None:
        """
        Test that as_single_tuples() yields the pairs in representation
        order.
        """
        self.assertEqual(
            list(Params("a=1&b=2&a=3").as_single_tuples()),
            [("a", "1"), ("b", "2"), ("a", "3")],
        )


class ParamsSortTestCase(unittest.TestCase):
    """
    tests for :py:meth:`action0.url.params.Params.sort`
    """

    def test_sort_in_place(self) -> None:
        """
        Test that sort() persistently orders by name and keeps the order
        of the values of one name.
        """
        params = Params("b=2&a=3&a=1")
        params.sort()
        self.assertEqual(params.as_str(), "a=3&a=1&b=2")
        self.assertEqual(list(params), ["a", "b"])
        self.assertEqual(params.get_all("a"), ["3", "1"])

    def test_sort_keeps_equality(self) -> None:
        """
        Test that a sorted instance still equals the unsorted one
        (regression: sorting the values changed what __eq__ compares).
        """
        params = Params("b=2&a=3&a=1")
        sorted_params = Params(params)
        sorted_params.sort()
        self.assertEqual(sorted_params, params)
        self.assertEqual(Params(params.as_str(sort=True)), params)


if __name__ == "__main__":
    unittest.main()
