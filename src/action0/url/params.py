import re
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import MutableMapping
from typing import Literal
from typing import Self
from typing import cast
from urllib.parse import parse_qsl
from urllib.parse import quote
from urllib.parse import urlencode

ParamValue = str | int | float | bool
"""A single parameter value; non-strings are coerced to strings on the way in
(bools become the web-style ``"true"`` / ``"false"``)."""

# Mapping instead of dict so callers may pass any dict-ish type and, unlike
# dict, Mapping is covariant in its value type (a dict[str, str] works too)
ParamTypes = (
    Iterable[tuple[str, ParamValue | Iterable[ParamValue]]]
    | Mapping[str, ParamValue | Iterable[ParamValue]]
    | str
)
"""Everything that can initialize a :py:class:`Params` instance: a query
string, a mapping, or an iterable of name/value(s) tuples."""

# characters that stay raw when rendering without form encoding (on top of
# quote()'s always-safe unreserved characters): RFC 3986 pchar minus "&", ";"
# and "=", which delimit the pairs, and "/", which would start a path segment
_PLAIN_SAFE = ":@!$'()*+,"

# characters a parameter string that is kept as it was written may contain
# raw: everything that is legal inside a query ("&" separated), respectively
# inside a path segment (";" separated, no "/" and "?" there). Everything
# else gets percent-encoded.
_RAW_QUERY_SAFE = "/?:@!$&'()*+,;="
_RAW_SEGMENT_SAFE = ":@!$&'()*+,;="

# a "%" that does not start a percent escape
_STRAY_PERCENT_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _requote(encoded: str, safe: str) -> str:
    """
    Make an already percent-encoded string safe to render without changing
    what it means: the escapes it has are kept as they are, a "%" that is
    not part of an escape and every character that is neither unreserved nor
    in `safe` is percent-encoded.

    :param encoded: the (possibly sloppily) percent-encoded string
    :param safe: the characters that may stay raw besides the unreserved ones
    :return: the string with only valid escapes and allowed characters
    """
    return quote(_STRAY_PERCENT_RE.sub("%25", encoded), safe=safe + "%")


def _coerce_key(key: object) -> str:
    """
    Check a parameter name.

    :param key: the name to check
    :return: the name as a plain string
    :raises TypeError: if the name is not a string
    """
    if not isinstance(key, str):
        raise TypeError(f"parameter names must be str, not {type(key).__name__}")
    # str.__str__ turns instances of str subclasses (enum members) into
    # plain strings
    return str.__str__(key)


def _coerce_value(value: object) -> str:
    """
    Coerce a single parameter value to its string representation.

    :param value: the value to coerce
    :return: the value as a string, bools as "true" / "false"
    :raises TypeError: for everything but str, int, float and bool
    """
    # bool before int: bools use the web convention
    if isinstance(value, bool):
        return "true" if value else "false"
    # the unbound base class methods give the plain value also for enum
    # members, whose own str() would be "Color.RED"
    if isinstance(value, str):
        return str.__str__(value)
    if isinstance(value, int):
        return int.__repr__(value)
    if isinstance(value, float):
        return float.__repr__(value)
    raise TypeError(
        "parameter values must be str, int, float or bool (or an iterable "
        f"of those), not {type(value).__name__}; convert other objects with str()"
    )


def _coerce_values(value_s: object) -> list[str]:
    """
    Coerce a single value or an iterable of values to a list of strings.

    :param value_s: a single value or an iterable of values
    :return: all values as a list of strings
    :raises TypeError: if a value is not a str, int, float or bool
    """
    if isinstance(value_s, (str, int, float)):
        return [_coerce_value(value_s)]
    # iterable, but never meant as a list of values: bytes would become one
    # value per byte, a mapping its keys
    if isinstance(value_s, (bytes, bytearray, memoryview, Mapping)) or not isinstance(
        value_s, Iterable
    ):
        # raises the TypeError naming the offending type
        return [_coerce_value(value_s)]
    return [_coerce_value(value_) for value_ in value_s]


def _names_and_values(params: object) -> Iterator[tuple[str, list[str]]]:
    """
    Iterate over the checked names and coerced values of a mapping or of an
    iterable of (name, value) pairs.

    :param params: a mapping or an iterable of pairs
    :return: an iterator over tuples of a name and its list of values
    :raises TypeError: if `params` is something else, a name is not a
                       string or a value is not a str, int, float or bool
    """
    if isinstance(params, Mapping):
        for key, value_s in params.items():
            yield _coerce_key(key), _coerce_values(value_s)
        return

    if not isinstance(params, Iterable) or isinstance(params, (bytes, bytearray, memoryview)):
        raise TypeError(
            "params must be a str, a mapping, an iterable of (name, value) "
            f"pairs or a Params instance, not {type(params).__name__}"
        )
    for item in params:
        # a string would unpack into its characters ("ab" -> a=b)
        if isinstance(item, (str, bytes)):
            raise TypeError(
                f"expected (name, value) pairs, got the {type(item).__name__} {item!r}"
            )
        try:
            # cast: whether it really is a pair is what gets tried here
            key, value_s = cast("Iterable[object]", item)
        except (TypeError, ValueError):
            raise TypeError(f"expected (name, value) pairs, got {item!r}") from None
        yield _coerce_key(key), _coerce_values(value_s)


def _pair_key(pair: tuple[str, str]) -> str:
    """
    Sort key for the pairs: the name only, so that sorting (which is stable)
    keeps the order of the values of one name.

    :param pair: a (key, value) pair
    :return: the key of the pair
    """
    return pair[0]


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

    Parameters parsed from a string are rendered exactly as they were
    written for as long as they are not modified (see :py:meth:`as_str`).

    Params implements :py:class:`collections.abc.MutableMapping`: the mapping
    view works with a single value per key — the last one, like
    :py:meth:`singles`. That holds for ``params[key]`` and for the methods
    inherited from the mapping classes: ``get(key, default)``, ``keys()``,
    ``items()``, ``values()``, ``pop(key)`` and ``popitem()`` (both return
    the last value and remove all values of the key). Multi-value access is
    available through :py:meth:`get_all`, :py:meth:`add`, :py:meth:`as_dict`
    and :py:meth:`as_tuples`.

    Like every mutable mapping, Params instances are not hashable.

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
        self,
        params: ParamTypes | None = None,
        separator: Literal["&", ";"] = "&",
        *,
        form_encoding: bool = True,
    ) -> None:
        """
        :param params: the initial key-value(s) to set, either as a string which
                       will be parsed using parse_qsl, another Params instance
                       whose pairs are copied, or as a list of tuples or a
                       dictionary. The values can be single values or lists
                       of values; non-string values are coerced to strings
                       (bools become "true" / "false"). A string is the bare
                       parameter string, without a leading "?". Unlike
                       parse_qsl's default, blank values are kept ("a=&b=1"
                       keeps "a").
        :param separator: either a '&' or a ';' to separate the key-value pairs
                          in the string representation (also used when copying
                          another Params instance)
        :param form_encoding: whether a space is written as "+" and a "+" is
                              read as a space, as HTML forms and the queries
                              of web URLs do. Without it a space is written as
                              "%20" and a "+" is a literal plus sign, which is
                              right for path params and for the queries of
                              other schemes like "mailto" (see
                              :py:class:`~action0.url.base.Url`). Like the
                              separator, it is not taken over when copying
                              another Params instance.
        :raises TypeError: if `params` is of an unsupported type, a name is
                           not a string or a value is not a str, int, float
                           or bool
        :raises ValueError: if the separator is neither "&" nor ";"
        """
        if separator not in ("&", ";"):
            raise ValueError(f"separator must be '&' or ';', not {separator!r}")

        self._pairs: list[tuple[str, str]] = []
        self.separator: Literal["&", ";"] = separator
        self.form_encoding: bool = form_encoding
        # the string the pairs were parsed from, with the settings it was
        # parsed with: as_str() returns it while nothing was changed
        self._raw: str | None = None
        self._raw_settings: tuple[str, bool] = (separator, form_encoding)
        # lazily built {key: last value} view of the pairs for the mapping
        # methods, see _singles()
        self._index: dict[str, str] | None = None

        if params is None:
            pass

        elif isinstance(params, Params):
            self._pairs = list(params._pairs)
            if params._raw_settings == self._raw_settings:
                # same settings: the copy renders exactly like the original
                self._raw = params._raw

        elif isinstance(params, str):
            raw = _requote(params, _RAW_QUERY_SAFE if separator == "&" else _RAW_SEGMENT_SAFE)
            # parse_qsl always reads "+" as a space; escaping it first keeps
            # it a literal plus sign
            parsable = raw if form_encoding else raw.replace("+", "%2B")
            self._pairs = parse_qsl(parsable, separator=separator, keep_blank_values=True)
            self._raw = raw

        else:
            # a mapping or an iterable of pairs; raises for everything else
            for key, values in _names_and_values(params):
                self._pairs.extend((key, value_) for value_ in values)

    def _changed(self) -> None:
        """
        To be called after every change of the pairs: forgets the string
        they were parsed from and the index over them.
        """
        self._raw = None
        self._index = None

    def _singles(self) -> dict[str, str]:
        """
        The mapping view of the pairs: every key (in the order of its first
        pair) with its last value. Built once per change, so that the mapping
        methods don't have to scan all pairs on every access.

        :return: the cached dictionary — do not modify it
        """
        if self._index is None:
            index: dict[str, str] = {}
            for key, value in self._pairs:
                # assigning keeps the position of the first pair of the key
                index[key] = value
            self._index = index
        return self._index

    def __getitem__(self, key: str) -> str:
        """
        The single value of the parameter; if the parameter has multiple
        values, the last one — like :py:meth:`singles`. Use
        :py:meth:`get_all` for all values.

        :param key: the parameter name
        :return: the (last) value of the parameter
        :raises KeyError: if the parameter does not exist
        """
        return self._singles()[key]

    def __setitem__(self, key: str, value: ParamValue | Iterable[ParamValue]) -> None:
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
        # a copy of the keys: the cached index is replaced on changes
        return iter(list(self._singles()))

    def __len__(self) -> int:
        """
        :return: the number of distinct parameter names
        """
        return len(self._singles())

    def __contains__(self, key: object) -> bool:
        """
        :param key: the parameter name
        :return: whether a parameter with this name exists
        """
        return key in self._singles()

    def get_all(self, key: str) -> list[str]:
        """
        All values of the parameter in representation order; use
        ``params[key]`` or ``get()`` for the single-value view.

        :param key: the parameter name
        :return: the values as a list, an empty list if the parameter
                 does not exist
        """
        return [value for pair_key, value in self._pairs if pair_key == key]

    def add(self, key: str, value: ParamValue | Iterable[ParamValue]) -> None:
        """
        Add a parameter with a single value or multiple values, appended at
        the end of the representation. If it is a single value, the query
        string equivalent would be something like "foo=bar". If it is a
        list of values, the query string equivalent would be something like
        "foo=bar&foo=baz&foo=abc". Existing values are kept (in place).

        :param key: the parameter name to add
        :param value: the parameter value or list of values to add
        :raises TypeError: if the name is not a string or a value is not a
                           str, int, float or bool
        """
        key = _coerce_key(key)
        values = _coerce_values(value)
        if values:
            self._pairs.extend((key, value_) for value_ in values)
            self._changed()

    def remove(
        self, key: str, value: ParamValue | Iterable[ParamValue] | None = None
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

        if removed:
            self._pairs = kept
            self._changed()
        return removed

    def set(self, key: str, value: ParamValue | Iterable[ParamValue]) -> None:
        """
        Replace all value(s) of the key with the value(s) given, at the
        position of the key's first pair (new keys are appended at the
        end). Setting an empty list of values removes the key.

        :param key: the key to set values for
        :param value: a single value or a list of values to set
        :raises TypeError: if the name is not a string or a value is not a
                           str, int, float or bool
        """
        self._replace({_coerce_key(key): _coerce_values(value)})

    def _replace(self, replacements: Mapping[str, list[str]]) -> None:
        """
        Replace the values of the given keys in one pass over the pairs: the
        new values take the position of the key's first pair, keys that do
        not exist yet are appended in the order given. An empty list of
        values removes the key.

        :param replacements: the (already coerced) values per key
        """
        new_pairs: list[tuple[str, str]] = []
        placed: set[str] = set()
        for pair_key, pair_value in self._pairs:
            if pair_key not in replacements:
                new_pairs.append((pair_key, pair_value))
            elif pair_key not in placed:
                # the first pair of the key is replaced by the new values,
                # the other pairs of the key are dropped
                new_pairs.extend((pair_key, value_) for value_ in replacements[pair_key])
                placed.add(pair_key)
        for key, values in replacements.items():
            if key not in placed:
                new_pairs.extend((key, value_) for value_ in values)

        if new_pairs != self._pairs:
            self._pairs = new_pairs
            self._changed()

    # narrower than the MutableMapping contract on purpose: update() accepts
    # the same input forms as the constructor (e.g. a query string) instead of
    # arbitrary keys()/__getitem__ objects
    def update(  # type: ignore[override]  # ty: ignore[invalid-method-override]
        self,
        params: ParamTypes | None = None,
        /,
        **kwargs: ParamValue | Iterable[ParamValue],
    ) -> None:
        """
        Merge the given parameters into this instance: values of keys that
        already exist are replaced (like ``dict.update``, at the position of
        the key's first pair), other keys are appended. Accepts the same
        forms as the constructor (query string, mapping, iterable of tuples,
        Params instance) plus keyword arguments. As in :py:meth:`set`, an
        empty list of values removes the name.

        The update is all or nothing: if one of the values is rejected,
        nothing is changed.

        :param params: the parameters to merge in; positional-only, so that
                       a parameter named "params" can be given as a keyword
                       argument
        :param kwargs: parameters to merge in given as keyword arguments
        :raises TypeError: if `params` is of an unsupported type, a name is
                           not a string or a value is not a str, int, float
                           or bool
        """
        # everything is coerced before the first change is made
        replacements: dict[str, list[str]] = {}
        if isinstance(params, (str, Params)):
            # a string is parsed like this instance would parse it
            other = Params(params, self.separator, form_encoding=self.form_encoding)
            replacements.update(other.as_dict())
        elif params is not None:
            for key, values in _names_and_values(params):
                # an empty list of values removes the name, like in set()
                replacements.setdefault(key, []).extend(values)
        for key, value_s in kwargs.items():
            # like in a dict, a keyword argument wins over the same key in
            # the positional argument but keeps its position
            replacements[key] = _coerce_values(value_s)
        self._replace(replacements)

    def setdefault(  # ty: ignore[invalid-method-override]
        self, key: str, default: ParamValue | Iterable[ParamValue]
    ) -> str:
        """
        The value of the parameter like ``params[key]``; if the parameter
        does not exist it is set to `default` first. Unlike
        ``dict.setdefault`` there is no implicit default: a parameter cannot
        be ``None``.

        :param key: the parameter name
        :param default: the value or list of values to set if the parameter
                        does not exist
        :return: the (last) value of the parameter as it is stored, i.e.
                 as a string
        :raises TypeError: if the name is not a string or a value is not a
                           str, int, float or bool
        :raises ValueError: if the parameter does not exist and `default`
                            is an empty list
        """
        if key not in self:
            values = _coerce_values(default)
            if not values:
                raise ValueError("setdefault() needs at least one value as default")
            self.add(key, values)
        return self[key]

    def clear(self) -> dict[str, list[str]]:  # type: ignore[override]  # ty: ignore[invalid-method-override]
        """
        Remove all parameters, returns a dictionary of the
        cleared parameters (unlike ``MutableMapping.clear`` which
        returns ``None``).

        :return: a dictionary of removed keys and values
        """
        old = self.as_dict()
        self._pairs = []
        self._changed()
        return old

    def copy(self) -> Self:
        """
        An independent copy with the same pairs, separator and form
        encoding; it renders exactly like this instance.

        :return: a new instance of the same class
        """
        copied = type(self)(separator=self.separator, form_encoding=self.form_encoding)
        copied._pairs = list(self._pairs)
        copied._raw = self._raw
        copied._raw_settings = self._raw_settings
        return copied

    def __copy__(self) -> Self:
        return self.copy()

    def sort(self) -> None:
        """
        Sort the pairs in place by their name — the persistent equivalent of
        ``as_str(sort=True)``, which only sorts the rendered output. The sort
        is stable: the values of one name keep their order, so the sorted
        instance still equals the unsorted one.
        """
        sorted_pairs = sorted(self._pairs, key=_pair_key)
        if sorted_pairs != self._pairs:
            self._pairs = sorted_pairs
            self._changed()

    def as_str(self, sort: bool = False) -> str:
        """
        A string representation of the parameters, url encoded.

        Parameters that were parsed from a string and not modified since are
        returned exactly as they were written (only characters that are not
        allowed in a URL are percent-encoded), so a signed URL or a
        hand-crafted query survives a round trip byte for byte. After the
        first modification, and when sorting, the parameters are rendered
        from the pairs in a normalized spelling: every pair has a "="
        ("flag" becomes "flag="), empty pairs ("a=1&&b=2") are gone and all
        escapes are written in their canonical form.

        Example::

            >>> params = Params("flag&q=a%20b&&x=1")
            >>> params.as_str()
            'flag&q=a%20b&&x=1'
            >>> params.add("y", 2)
            >>> params.as_str()
            'flag=&q=a+b&x=1&y=2'

        :param sort: sort the parameters by their name (the values of one name keep
                     their order), otherwise they'll be returned in the order of the
                     representation
        :return: the url encoded query / path parameter string, e.g.
                 "foo=bar&bar=baz&bar=abc"
        """
        settings = (self.separator, self.form_encoding)
        if not sort and self._raw is not None and self._raw_settings == settings:
            return self._raw

        pairs = sorted(self._pairs, key=_pair_key) if sort else self._pairs

        if self.form_encoding:
            param_str = urlencode(pairs)
        else:
            # plain percent-encoding: a space becomes "%20", a "+" stays a "+"
            param_str = urlencode(pairs, safe=_PLAIN_SAFE, quote_via=quote)

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
        return dict(self._singles())

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
        the same per-key order; the order of the keys, the separator, the
        form encoding and the spelling they were parsed from don't matter.
        Plain mappings are converted to Params before comparing; one that
        cannot be converted is simply not equal.

        Mind that this compares all values, while the mapping view only
        shows the last one: ``Params("a=1&a=2") == {"a": "2"}`` is false,
        ``== {"a": ["1", "2"]}`` is true.

        :param other: the Params instance or mapping to compare with
        :return: whether the parameters are equal
        """
        if isinstance(other, Params):
            return self.as_dict() == other.as_dict()
        if isinstance(other, Mapping):
            try:
                # cast: the values of an arbitrary mapping are unknown to the
                # type checker; non-string values are coerced like everywhere else
                other_params = Params(cast("ParamTypes", other))
            except TypeError:
                # names or values Params cannot hold can never be equal
                return False
            return self.as_dict() == other_params.as_dict()
        return NotImplemented

    def __str__(self) -> str:
        return self.as_str()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.as_str()})"
