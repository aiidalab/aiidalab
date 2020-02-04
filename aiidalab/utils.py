"""Helpful utilities for the AiiDA lab tools."""

import sys
from os import path
from importlib import import_module

from markdown import markdown
import requests

import ipywidgets as ipw
from IPython.lib import backgroundjobs as bg
from .config import AIIDALAB_APPS, AIIDALAB_REGISTRY


def update_cache():
    """Run this process asynchronously."""
    requests_cache.install_cache(cache_name='apps_meta', backend='sqlite', expire_after=3600, old_data_on_error=True)
    requests.get(AIIDALAB_REGISTRY)
    requests_cache.install_cache(cache_name='apps_meta', backend='sqlite')


# Warning: try-except is a fix for Quantum Mobile release v19.03.0 that does not have requests_cache installed
try:
    import requests_cache
    # At start getting data from cache
    requests_cache.install_cache(cache_name='apps_meta', backend='sqlite')

    # If requests_cache is installed, upgrade the cache in the background.
    UPDATE_CACHE_BACKGROUND = bg.BackgroundJobFunc(update_cache)
    UPDATE_CACHE_BACKGROUND.start()
except ImportError:
    pass


def load_app_registry():
    """Load apps' information from the AiiDA lab registry."""
    try:
        return requests.get(AIIDALAB_REGISTRY).json()
    except ValueError:
        print("Registry server is unavailable! Can't check for the updates")
        return {}


def load_widget(name):
    if path.exists(path.join(AIIDALAB_APPS, name, 'start.py')):
        return load_start_py(name)
    return load_start_md(name)


def load_start_py(name):
    """Load app appearance from a Python file."""
    try:
        mod = import_module('apps.%s.start' % name)
        appbase = "../" + name
        jupbase = "../../.."
        notebase = jupbase + "/notebooks/apps/" + name
        try:
            return mod.get_start_widget(appbase=appbase, jupbase=jupbase, notebase=notebase)
        except TypeError:
            return mod.get_start_widget(appbase=appbase, jupbase=jupbase)
    except Exception:  # pylint: disable=broad-except
        return ipw.HTML("<pre>{}</pre>".format(sys.exc_info()))


def load_start_md(name):
    """Load app appearance from a Markdown file."""
    fname = path.join(AIIDALAB_APPS, name, 'start.md')
    try:

        md_src = open(fname).read()
        md_src = md_src.replace("](./", "](../{}/".format(name))
        html = markdown(md_src)

        # open links in new window/tab
        html = html.replace('<a ', '<a target="_blank" ')

        # downsize headings
        html = html.replace("<h3", "<h4")
        return ipw.HTML(html)

    except Exception as exc:  # pylint: disable=broad-except
        return ipw.HTML("Could not load start.md: {}".format(str(exc)))
