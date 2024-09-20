# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------


import os
import sys

project = "RansomLook"
copyright = "RansomLook Core Team"
author = "RansomLook Core Team"

# The full version, including alpha/beta/rc tags
release = "1.7.0"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib.openapi",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

numfig = True


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_title = "RansomLook"
html_theme_options = {
    "path_to_docs": "docs",
    "repository_url": "https://github.com/RansomLook/RansomLook",
    # "repository_branch": "gh-pages",  # For testing
    "launch_buttons": {
        "binderhub_url": "https://github.com/RansomLook/RansomLook",
    },
    "use_edit_page_button": True,
    "use_issues_button": True,
    "use_repository_button": True,
    "use_download_button": True,
    "home_page_in_toc": True,
}


# -- Options for LaTeX output --------------------------------------------------

latex_engine = "pdflatex"

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
    ("index", "ransomlook.tex", "RansomLook", "RansomLook Core Team", "howto"),
]

latex_show_urls = True
latex_show_pagerefs = True

ADDITIONAL_PREAMBLE = r"""
\setcounter{tocdepth}{3}
"""
