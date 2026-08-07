from typing import Iterable
from typing import Iterator
from typing import Literal
from typing import Mapping
from typing import MutableMapping
from typing import Union
from typing import cast
from urllib.parse import parse_qsl
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

    Internally the parameters are an ordered list of ``(key, value)`` pairs, so
    the full representation order — including values of one key interleaved
    with other keys — round-trips losslessly:
    ``Params("a=1&b=2&a=3").as_str()`` is ``"a=1&b=2&a=3"`` again. The grouped
    views (:py:meth:`as_dict`, :py:meth:`as_tuples`) collect the values per
    key instead.

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
                       will be parsed using parse_qsl, another Params instance
                       whose pairs are copied, or as a list of tuples or a
                       dictionary. The values can be single values or lists
                       of values; non-string values are coerced to strings
                       (bools become "true" / "false"). Unlike parse_qsl's
                       default, blank values are kept ("a=&b=1" keeps "a"), so
                       parsing and re-rendering is lossless.
        :param separator: either a '&' or a ';' to separate the key-value pairs
                          in the string representation (also used when copying
                          another Params instance)
        """
        self._pairs: list[tuple[str, str]] = []
        self.separator: Literal["&", ";"] = separator

        if isinstance(params, Params):
            self._pairs = list(params._pairs)

        elif isinstance(params, str):
            self._pairs = parse_qsl(params, separator=self.separator, keep_blank_values=True)

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
        for pair_key, value in reversed(self._pairs):
            if pair_key == key:
                return value
        raise KeyError(key)

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
        if not self.remove(key):
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        """
        :return: an iterator over the distinct parameter names in the order
                 of their first pair
        """
        seen: set[str] = set()
        for key, _ in self._pairs:
            if key not in seen:
                seen.add(key)
                yield key

    def __len__(self) -> int:
        """
        :return: the number of distinct parameter names
        """
        return len({key for key, _ in self._pairs})

    def __contains__(self, key: object) -> bool:
        """
        :param key: the parameter name
        :return: whether a parameter with this name exists
        """
        return any(pair_key == key for pair_key, _ in self._pairs)

    def get_all(self, key: str) -> list[str]:
        """
        All values of the parameter in representation order; use
        ``params[key]`` or :py:meth:`get` for the single-value view.

        :param key: the parameter name
        :return: the values as a list, an empty list if the parameter
                 does not exist
        """
        return [value for pair_key, value in self._pairs if pair_key == key]

    def add(self, key: str, value: Union[ParamValue, Iterable[ParamValue]]) -> None:
        """
        Add a parameter with a single value or multiple values, appended at
        the end of the representation. If it is a single value, the query
        string equivalent would be something like "foo=bar". If it is a
        list of values, the query string equivalent would be something like
        "foo=bar&foo=baz&foo=abc". Existing values are kept (in place).

        :param key: the parameter name to add
        :param value: the parameter value or list of values to add
        """
        self._pairs.extend((key, value_) for value_ in _coerce_values(value))

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
        value_list = None if value is None else _coerce_values(value)

        kept: list[tuple[str, str]] = []
        removed: list[str] = []
        for pair_key, pair_value in self._pairs:
            if pair_key == key and (value_list is None or pair_value in value_list):
                removed.append(pair_value)
            else:
                kept.append((pair_key, pair_value))

        self._pairs = kept
        return removed

    def set(self, key: str, value: Union[ParamValue, Iterable[ParamValue]]) -> None:
        """
        Replace all value(s) of the key with the value(s) given, at the
        position of the key's first pair (new keys are appended at the
        end). Setting an empty list of values removes the key.

        :param key: the key to set values for
        :param value: a single value or a list of values to set
        """
        values = _coerce_values(value)
        if not values:
            self.remove(key)
            return

        new_pairs: list[tuple[str, str]] = []
        inserted = False
        for pair_key, pair_value in self._pairs:
            if pair_key == key:
                # replace the key's first pair with the new values, drop the
                # other pairs of the key
                if not inserted:
                    new_pairs.extend((key, value_) for value_ in values)
                    inserted = True
            else:
                new_pairs.append((pair_key, pair_value))
        if not inserted:
            new_pairs.extend((key, value_) for value_ in values)
        self._pairs = new_pairs

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
        already exist are replaced (like ``dict.update``, at the position of
        the key's first pair), other keys are appended. Accepts the same
        forms as the constructor (query string, mapping, iterable of tuples,
        Params instance) plus keyword arguments.

        :param params: the parameters to merge in
        :param kwargs: parameters to merge in given as keyword arguments
        """
        if params is not None:
            other = Params(params, self.separator)
            for key in other:
                self.set(key, other.get_all(key))
        for key, value_s in kwargs.items():
            self.set(key, value_s)

    def clear(self) -> dict[str, list[str]]:  # type: ignore[override]  # ty: ignore[invalid-method-override]
        """
        Remove all parameters, returns a dictionary of the
        cleared parameters (unlike ``MutableMapping.clear`` which
        returns ``None``).

        :return: a dictionary of removed keys and values
        """
        old = self.as_dict()
        self._pairs = []
        return old

    def sort(self) -> None:
        """
        Sort the pairs in place by their name and then by their values — the
        persistent equivalent of ``as_str(sort=True)``, which only sorts the
        rendered output.
        """
        self._pairs.sort()

    def as_str(self, sort: bool = False) -> str:
        """
        A string representation of the parameters, url encoded.

        :param sort: sort the parameters by their name and then by their value, otherwise
                     they'll be returned in the order of the representation
        :return: the url encoded query / file parameter string, e.g.
                 "foo=bar&bar=baz&bar=abc"
        """
        pairs = sorted(self._pairs) if sort else self._pairs

        param_str = urlencode(pairs)

        # urlencode always joins with "&"; a literal separator inside a value is
        # percent-encoded by then, so a plain replace cannot corrupt values
        if self.separator != "&":
            param_str = param_str.replace("&", self.separator)

        return param_str

    def as_tuples(self) -> Iterator[tuple[str, list[str]]]:
        """
        :return: the parameters grouped per key as an iterator of tuples with
                 the values being lists of strings
        """
        return iter(self.as_dict().items())

    def as_single_tuples(self) -> Iterator[tuple[str, str]]:
        """
        :return: the parameter representation as an iterator of tuples of
                 the key and a single value, in representation order. This
                 means keys with multiple values will appear more than once.
        """
        return iter(list(self._pairs))

    def as_dict(self) -> dict[str, list[str]]:
        """
        :return: the parameters grouped per key as a dictionary with the
                 parameter names as key and the values as lists of strings
        """
        result: dict[str, list[str]] = {}
        for key, value in self._pairs:
            result.setdefault(key, []).append(value)
        return result

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
        return {key: values[-1] for key, values in self.as_dict().items()}

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
            return self.as_dict() == other.as_dict()
        if isinstance(other, Mapping):
            # cast: the values of an arbitrary mapping are unknown to the
            # type checker; non-string values are coerced like everywhere else
            return self.as_dict() == Params(cast("ParamTypes", other)).as_dict()
        return NotImplemented

    def __str__(self) -> str:
        return self.as_str()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.as_str()})"
