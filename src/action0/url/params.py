import urllib
from typing import Iterable
from typing import Iterator
from typing import Literal
from typing import Union
from urllib.parse import parse_qs

from IPython.lib.pretty import pretty

ParamTypes = Union[Iterable[tuple[str, str | Iterable[str]]], dict[str, str | Iterable[str]], str]


class Params:
    """
    Allows easy manipulation of URL query parameters and URL path parameters, it
    supports single and multiple values for a key.
    """

    def __init__(
        self, params: Union[ParamTypes, None] = None, separator: Literal["&", ";"] = "&"
    ) -> None:
        """
        :param params: the initial key-value(s) to set, either as a string which
                       will be parsed using parse_qs, or as a list of tuples or
                       a dictionary. The values can be a single string or a list
                       of strings.
        :param separator: either a '&' or a ';' to separate the key-value pairs
                          in the string representation
        """
        self._params: dict[str, list[str]] = {}
        self.separator = separator

        if isinstance(params, str):
            self._params = parse_qs(params, separator=self.separator)

        elif isinstance(params, dict):
            for key, value_s in params.items():
                if isinstance(value_s, str):
                    self._params.setdefault(key, []).append(value_s)
                else:
                    self._params.setdefault(key, []).extend(value_s)

        elif isinstance(params, Iterable):
            for key, value_s in params:
                if isinstance(value_s, str):
                    self._params.setdefault(key, []).append(value_s)
                else:
                    self._params.setdefault(key, []).extend(value_s)

    def add(self, key: str, value: Union[str, Iterable[str]]) -> None:
        """
        Add a parameter with a single value or multiple values. If
        it is a single value, the query string equivalent would be
        something like "foo=bar". If it is a list of values, the
        query string equivalent would be something like
        "foo=bar&foo=baz&foo=abc".

        :param key: the parameter name to add
        :param value: the parameter value or list of values to add
        """
        if isinstance(value, str):
            self._params.setdefault(key, []).append(value)
        else:
            self._params.setdefault(key, []).extend(value)

    def remove(self, key: str, value: Union[str, Iterable[str], None] = None) -> list[str]:
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

        values = self._params.pop(key, [])
        value_list = [value] if isinstance(value, str) else list(value)
        self._params[key] = [value_ for value_ in values if value_ not in value_list]
        return values

    def set(self, key: str, value: Union[str, Iterable[str]]) -> None:
        """
        Replace all value(s) of the key with the value(s) given. If the key
        doesn't exist yet, it will be added.
        :param key: the key to set values for
        :param value: a single value or a list of values to set
        """
        self._params[key] = [value] if isinstance(value, str) else list(value)

    def clear(self) -> dict[str, list[str]]:
        """
        Remove all parameters, returns a dictionary of the
        cleared parameters.

        :return: a dictionary of removed keys and values
        """
        old = self._params
        self._params = {}
        return old

    def as_str(self) -> str:
        """
        A string representation of the parameters, url encoded.
        :return: the url encoded query / file parameter string, e.g.
                 "foo=bar&bar=baz&bar=abc"
        """
        param_str = urllib.parse.urlencode(self._params, doseq=True)
        if self.separator != "&":
            param_str.replace("&", self.separator)
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
        ret = {}
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

    def __str__(self) -> str:
        return self.as_str()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.as_str()})"
