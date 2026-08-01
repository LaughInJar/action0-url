from typing import Iterable
from typing import Iterator
from typing import Literal
from typing import Mapping
from typing import MutableMapping
from typing import Union
from typing import cast
from urllib.parse import parse_qs
from urllib.parse import urlencode

ParamValue = Union[str, int, float, bool]
"""A single parameter value; non-strings are coerced to strings on the way in
(bools become the web-style ``"true"`` / ``"false"``)."""

# Mapping instead of dict so callers may pass any dict-ish type and, unlike
# dict, Mapping is covariant in its value type (a dict[str, str] works too)
ParamTypes = Union[
    Iterable[tuple[str, Union[ParamValue, Iterable[ParamValue]]]],
    Mapping[str, Union[ParamValue, Iterable[ParamValue]]],
    str,
]
"""Everything that can initialize a :py:class:`Params` instance: a query
string, a mapping, or an iterable of name/value(s) tuples."""


def _coerce_value(value: ParamValue) -> str:
    """
    Coerce a single parameter value to its string representation.

    :param value: the value to coerce
    :return: the value as a string, bools as "true" / "false"
    """
    # bool before the plain str() fallback: bools use the web convention
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_values(value_s: Union[ParamValue, Iterable[ParamValue]]) -> list[str]:
    """
    Coerce a single value or an iterable of values to a list of strings.

    :param value_s: a single value or an iterable of values
    :return: all values as a list of strings
    """
    if isinstance(value_s, (str, int, float, bool)):
        return [_coerce_value(value_s)]
    return [_coerce_value(value_) for value_ in value_s]


class Params(MutableMapping[str, str]):
    """
    Allows easy manipulation of URL query parameters and URL path parameters, it
    supports single and multiple values for a key.

    Params implements :py:class:`typing.MutableMapping`: the mapping view
    (``params[key]``, :py:meth:`get`, ``items()``, ``values()``, ...) works
    with a single value per key — the last one, like :py:meth:`singles`.
    Multi-value access is available through :py:meth:`get_all`,
    :py:meth:`add`, :py:meth:`as_dict` and :py:meth:`as_tuples`.

    Example::

        >>> params = Params("b=2&a=1")
        >>> params["a"]
        '1'
        >>> params.add("a", 3)
        >>> params.get_all("a")
        ['1', '3']
        >>> params.as_str()
        'b=2&a=1&a=3'
        >>> params.as_str(sort=True)
        'a=1&a=3&b=2'
    """

    def __init__(
        self, params: Union[ParamTypes, None] = None, separator: Literal["&", ";"] = "&"
    ) -> None:
        """
        :param params: the initial key-value(s) to set, either as a string which
                       will be parsed using parse_qs, another Params instance
                       whose keys and values are copied, or as a list of tuples
                       or a dictionary. The values can be single values or lists
                       of values; non-string values are coerced to strings
                       (bools become "true" / "false"). Unlike parse_qs, blank
                       values are kept ("a=&b=1" keeps "a"), so parsing and
                       re-rendering is lossless.
        :param separator: either a '&' or a ';' to separate the key-value pairs
                          in the string representation (also used when copying
                          another Params instance)
        """
        self._params: dict[str, list[str]] = {}
        self.separator: Literal["&", ";"] = separator

        if isinstance(params, Params):
            # copy through the multi-value view; the Mapping branch below only
            # sees the single-value view and would lose values
            self._params = {key: list(values) for key, values in params.as_tuples()}

        elif isinstance(params, str):
            self._params = parse_qs(params, separator=self.separator, keep_blank_values=True)

        elif isinstance(params, Mapping):
            # cast: the type checker cannot fully rule out the Iterable-of-tuples
            # union member here because a Mapping is itself an Iterable
            mapping = cast("Mapping[str, Union[ParamValue, Iterable[ParamValue]]]", params)
            for key, value_s in mapping.items():
                self.add(key, value_s)

        elif isinstance(params, Iterable):
            for key, value_s in params:
                self.add(key, value_s)

    def __getitem__(self, key: str) -> str:
        """
        The single value of the parameter; if the parameter has multiple
        values, the last one — like :py:meth:`singles`. Use
        :py:meth:`get_all` for all values.

        :param key: the parameter name
        :return: the (last) value of the parameter
        :raises KeyError: if the parameter does not exist
        """
        return self._params[key][-1]

    def __setitem__(self, key: str, value: Union[ParamValue, Iterable[ParamValue]]) -> None:
        """
        Replace all values of the parameter, same as :py:meth:`set`.

        :param key: the parameter name
        :param value: a single value or a list of values
        """
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        """
        Remove the parameter with all its values.

        :param key: the parameter name
        :raises KeyError: if the parameter does not exist
        """
        del self._params[key]

    def __iter__(self) -> Iterator[str]:
        """
        :return: an iterator over the parameter names
        """
        return iter(self._params)

    def __len__(self) -> int:
        """
        :return: the number of distinct parameter names
        """
        return len(self._params)

    def __contains__(self, key: object) -> bool:
        """
        :param key: the parameter name
        :return: whether a parameter with this name exists
        """
        return key in self._params

    def get_all(self, key: str) -> list[str]:
        """
        All values of the parameter; use ``params[key]`` or :py:meth:`get`
        for the single-value view.

        :param key: the parameter name
        :return: the values as a list, an empty list if the parameter
                 does not exist
        """
        return list(self._params.get(key, []))

    def add(self, key: str, value: Union[ParamValue, Iterable[ParamValue]]) -> None:
        """
        Add a parameter with a single value or multiple values. If
        it is a single value, the query string equivalent would be
        something like "foo=bar". If it is a list of values, the
        query string equivalent would be something like
        "foo=bar&foo=baz&foo=abc". Existing values are kept.

        :param key: the parameter name to add
        :param value: the parameter value or list of values to add
        """
        values = _coerce_values(value)
        if values:
            self._params.setdefault(key, []).extend(values)

    def remove(
        self, key: str, value: Union[ParamValue, Iterable[ParamValue], None] = None
    ) -> list[str]:
        """
        If only a key is given all values with this name are removed. If a
        value or a list of values is given only the matching values are removed.

        :param key: the name of the parameter to remove (or from which values
                    are to be removed)
        :param value: if given, only matching value(s) are to be removed not the
                      entire parameter
        :return: a list of removed values
        """
        if value is None:
            return self._params.pop(key, [])

        value_list = _coerce_values(value)
        values = self._params.get(key, [])
        kept = [value_ for value_ in values if value_ not in value_list]
        removed = [value_ for value_ in values if value_ in value_list]

        # drop the key entirely once its last value is removed
        if kept:
            self._params[key] = kept
        else:
            self._params.pop(key, None)

        return removed

    def set(self, key: str, value: Union[ParamValue, Iterable[ParamValue]]) -> None:
        """
        Replace all value(s) of the key with the value(s) given. If the key
        doesn't exist yet, it will be added; setting an empty list of values
        removes the key.

        :param key: the key to set values for
        :param value: a single value or a list of values to set
        """
        values = _coerce_values(value)
        if values:
            self._params[key] = values
        else:
            self._params.pop(key, None)

    # narrower than the MutableMapping contract on purpose: update() accepts
    # the same input forms as the constructor (e.g. a query string) instead of
    # arbitrary keys()/__getitem__ objects
    def update(  # type: ignore[override]  # ty: ignore[invalid-method-override]
        self,
        params: Union[ParamTypes, None] = None,
        **kwargs: Union[ParamValue, Iterable[ParamValue]],
    ) -> None:
        """
        Merge the given parameters into this instance: values of keys that
        already exist are replaced (like ``dict.update``), other keys are
        added. Accepts the same forms as the constructor (query string,
        mapping, iterable of tuples, Params instance) plus keyword arguments.

        :param params: the parameters to merge in
        :param kwargs: parameters to merge in given as keyword arguments
        """
        if params is not None:
            for key, values in Params(params, self.separator).as_tuples():
                self._params[key] = list(values)
        for key, value_s in kwargs.items():
            self.set(key, value_s)

    def clear(self) -> dict[str, list[str]]:  # type: ignore[override]  # ty: ignore[invalid-method-override]
        """
        Remove all parameters, returns a dictionary of the
        cleared parameters (unlike ``MutableMapping.clear`` which
        returns ``None``).

        :return: a dictionary of removed keys and values
        """
        old = self._params
        self._params = {}
        return old

    def sort(self) -> None:
        """
        Sort the parameters in place by their name and then each name's
        values — the persistent equivalent of ``as_str(sort=True)``, which
        only sorts the rendered output.
        """
        self._params = {key: sorted(values) for key, values in sorted(self._params.items())}

    def as_str(self, sort: bool = False) -> str:
        """
        A string representation of the parameters, url encoded.

        :param sort: sort the parameters by their name and then by their value, otherwise
                     they'll be returned in the order they've been added
        :return: the url encoded query / file parameter string, e.g.
                 "foo=bar&bar=baz&bar=abc"
        """
        if sort:
            # sort by parameter name first, then each name's values
            _params = {key: sorted(values) for key, values in sorted(self._params.items())}
        else:
            _params = self._params

        param_str = urlencode(_params, doseq=True)

        # urlencode always joins with "&"; a literal separator inside a value is
        # percent-encoded by then, so a plain replace cannot corrupt values
        if self.separator != "&":
            param_str = param_str.replace("&", self.separator)

        return param_str

    def as_tuples(self) -> Iterator[tuple[str, list[str]]]:
        """
        :return: the parameter representation as an iterator of tuples with the
                 values being lists of strings
        """
        return iter(self._params.items())

    def as_single_tuples(self) -> Iterator[tuple[str, str]]:
        """
        :return: the parameter representation as an iterator of tuples
                 the key and a single value. This means keys with
                 multiple values will appear more than once.
        """
        for key, values in self._params.items():
            for value in values:
                yield key, value

    def as_dict(self) -> dict[str, list[str]]:
        """
        :return: the parameter representation as a dictionary with the
                 parameter names as key and the values as lists of strings
        """
        return self._params.copy()

    def singles(self) -> dict[str, str]:
        """
        For those who are really sure that each parameter has only one value
        and do not want to bother with the lists for the values, this method
        will return only the last value for each key.

        WARNING: be aware, if the key has multiple values, only one of those
        will be returned for the key!

        :return: a dictionary with the parameters with a single value
                 for each key
        """
        ret: dict[str, str] = {}
        for key, value in self._params.items():
            if value:
                ret[key] = value[-1]
        return ret

    def uniq_tuples(self) -> Iterator[tuple[str, str]]:
        """
        Same as :py:meth:`singles` but returning tuples.

        WARNING: be aware, if the key has multiple values, only one of those
        will be returned for the key!

        :return: an iterable of tuples with a key and a single value
        """
        return iter(self.singles().items())

    def __eq__(self, other: object) -> bool:
        """
        Params are equal when they hold the same keys with the same values in
        the same per-key order; the order of the keys and the separator don't
        matter. Plain mappings are converted to Params before comparing.

        :param other: the Params instance or mapping to compare with
        :return: whether the parameters are equal
        """
        if isinstance(other, Params):
            return self._params == other._params
        if isinstance(other, Mapping):
            # cast: the values of an arbitrary mapping are unknown to the
            # type checker; non-string values are coerced like everywhere else
            return self._params == Params(cast("ParamTypes", other))._params
        return NotImplemented

    def __str__(self) -> str:
        return self.as_str()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.as_str()})"
