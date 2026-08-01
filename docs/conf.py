"""Sphinx configuration for the action0-url documentation."""

import sys
from pathlib import Path

# make the package importable even without an installed wheel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from action0.url import __version__  # noqa: E402

project = "action0-url"
author = "Simon Lachinger"
project_copyright = "2026, Simon Lachinger"
version = __version__
release = __version__

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
]

# link references like :py:class:`urllib.parse.ParseResult` to the Python docs
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# order the API reference like the source files and merge the rich __init__
# docstrings into their class documentation
autodoc_member_order = "bysource"
autoclass_content = "both"

# sphinx-autodoc-typehints: document every parameter type and default value
always_document_param_types = True
typehints_defaults = "comma"

myst_enable_extensions = ["colon_fence"]

html_theme = "furo"
html_title = f"action0-url {__version__}"
