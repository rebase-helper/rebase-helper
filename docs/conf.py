# -*- coding: utf-8 -*-
#
# rebase-helper documentation build configuration file
#

import os
import subprocess
import sys

sys.path[0:0] = [os.path.abspath('.'), os.path.abspath('..')]

from rebasehelper import VERSION

# Determine if this script is running inside RTD build environment
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

if not on_rtd:
    # Use RTD theme when building locally
    import sphinx_rtd_theme


def setup(app):
    # convert Markdown files to RST
    subprocess.check_call(['pandoc', '--from=markdown', '--to=rst', '--output=../README.rst', '../README.md'])
    subprocess.check_call(['pandoc', '--from=markdown', '--to=rst', '--output=../CHANGELOG.rst', '../CHANGELOG.md'])


# -- General configuration ------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.mathjax',
    'sphinx.ext.ifconfig',
    'sphinx.ext.viewcode',
    'ext.autoargs',
    'ext.custom_man_builder',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = ['.rst']

# The encoding of source files.
source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'rebase-helper'
copyright = '2014-2019, Red Hat'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '.'.join(VERSION.split('.')[0:2])
# The full version, including alpha/beta/rc tags.
release = VERSION

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = []

# The reST default role (used for this markup: `text`) to use for all
# documents.
default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = []


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'default' if on_rtd else 'sphinx_rtd_theme'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = [] if on_rtd else [sphinx_rtd_theme.get_html_theme_path()]

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = 'rebase-helper {0} documentation'.format(VERSION)

# A shorter title for the navigation bar.  Default is the same as html_title.
html_short_title = html_title

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = None

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom style sheets
html_css_files = ['css/custom.css']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
html_additional_pages = {}

# If false, no module index is generated.
html_domain_indices = True

# If false, no index is generated.
html_use_index = True

# If true, the index is split into individual pages for each letter.
html_split_index = False

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'rebase-helper-docs'


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('man/rebase-helper', 'rebase-helper',
     'helps you rebase your package to the latest version',
     ['Petr Hráček <phracek@redhat.com>',
      'Tomáš Hozza <thozza@redhat.com>',
      'Nikola Forró <nforro@redhat.com>',
      'František Nečas <fifinecas@seznam.cz>'], 1),
]

# If true, show URL addresses after external links.
man_show_urls = False


# -- Options for autodoc --------------------------------------------------

# This value contains a list of modules to be mocked up. This is useful
# when some external dependencies are not met at build time and break
# the building process.
autodoc_mock_imports = ['rpm', 'koji', 'requests_gssapi']
