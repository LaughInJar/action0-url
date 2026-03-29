from typing import Union
from urllib.parse import parse_qs

ParamTypes = Union[list[tuple[str, str]], dict[str, str], dict[str, list[str]], str]


class Params:
    """
    Allows easy manipulation of URL query parameters and URL path parameters.
    """

    def __init__(self, params: Union[ParamTypes, None] = None) -> None:
        self._params: dict[str, list[str]] = {}

        if isinstance(params, str):
            self._params = parse_qs(params)

        if isinstance(params, dict):
            for key, value_s in params.items():
                if isinstance(value_s, list):
                    self._params.setdefault(key, []).extend(value_s)
                else:
                    self._params.setdefault(key, []).append(value_s)

        if isinstance(params, list):
            for key, value_s in params:
                self._params.setdefault(key, []).append(value_s)

    def add(self, key: str, value: Union[str, list[str]]) -> None:
        pass

    def remove(self, key: str, value: Union[str, list[str], None] = None) -> None:
        pass

    def replace(self, key: str, value: Union[str, list[str], None] = None) -> None:
        pass

    def clear(self):
        pass

    def as_str(self) -> str:
        pass

    def as_tuples(self) -> list[tuple[str, str]]:
        pass

    def as_dict(self) -> dict[str, list[str]]:
        pass

    def as_single(self) -> dict[str, str]:
        pass