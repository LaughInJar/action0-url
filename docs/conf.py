"""Sphinx configuration for the action0-url documentation."""

import sys
from pathlib import Path

# make the package importable even without an installed wheel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from action0.url import __version__  # noqa: E402

project = "action0-url"
author = "Simon Lachinger"
project_copyright = "2026, Simon Lachinger"
# shown as "main" on the site, see html_title below
version = "main"
release = "main"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
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
# the site is built from main on every push, so it is not the documentation
# of a release: say so in the title and on top of every page
html_title = "action0-url (main)"
html_theme_options = {
    "announcement": (
        "This documentation describes the <code>main</code> branch, which can be "
        f"ahead of the latest release on PyPI (the version in the sources is {__version__}). "
        'See the <a href="changelog.html">changelog</a> for what is released.'
    ),
}
