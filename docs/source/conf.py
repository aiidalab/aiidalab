# pylint: disable=invalid-name

# -*- coding: utf-8 -*-
"""Sphinx configuration for aiidalab."""

import time
import aiidalab

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.mathjax',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinxcontrib.contentui',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3.7', None),
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
#~ master_doc = 'index'
master_doc = 'index'

# General information about the project.
project = u'aiidalab'
copyright_first_year = "2020"
copyright_owners = "The AiiDAlab Team"

current_year = str(time.localtime().tm_year)
copyright_year_string = current_year if current_year == copyright_first_year else "{}-{}".format(
    copyright_first_year, current_year)
copyright = u'{}, {}. All rights reserved'.format(copyright_year_string, copyright_owners)  # pylint: disable=redefined-builtin

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The full version, including alpha/beta/rc tags.
# The short X.Y version.
version = '.'.join(aiidalab.__version__.split('.')[:2])

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
show_authors = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = False

# Output file base name for HTML help builder.
htmlhelp_basename = 'aiidalab-doc'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# Warnings to ignore when using the -n (nitpicky) option
# We should ignore any python built-in exception, for instance
nitpick_ignore = [
    ('py:class', 'Exception'),
    ('py:class', 'traitlets.traitlets.HasTraits'),
    ('py:class', 'watchdog.events.FileSystemEventHandler'),
    ('py:class', 'enum.Enum'),
    ('py:class', 'dulwich.repo.Repo'),
]
