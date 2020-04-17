"""Helpful utilities for the AiiDA lab tools."""

import sys
import json
import time
from os import path
from importlib import import_module
from urllib.parse import urlparse
from collections import defaultdict
from functools import wraps
from threading import Lock

import requests
from markdown import markdown
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
    parsed_url = urlparse(AIIDALAB_REGISTRY)
    if parsed_url.scheme == 'file':
        with open(parsed_url.path) as file:
            return json.loads(file.read())
    else:
        try:
            return requests.get(AIIDALAB_REGISTRY).json()
        except ValueError:
            print("Registry server is unavailable! Can't check for the updates")
            return dict(apps=dict(), catgories=dict())


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


class throttled:  # pylint: disable=invalid-name
    """Decorator to throttle calls to a function to a specified rate.

    The throttle is specific to the first argument of the wrapped
    function. That means for class methods it is specific to each
    instance.

    Adapted from: https://gist.github.com/gregburek/1441055

    """

    def __init__(self, calls_per_second=1):
        self.calls_per_second = calls_per_second
        self.last_start = defaultdict(lambda: -1)
        self.locks = defaultdict(Lock)

    def __call__(self, func):
        """Return decorator function."""

        @wraps(func)
        def wrapped(instance, *args, **kwargs):
            if self.last_start[hash(instance)] >= 0:
                elapsed = time.perf_counter() - self.last_start[hash(instance)]
                to_wait = 1.0 / self.calls_per_second - elapsed
                if to_wait > 0:
                    locked = self.locks[hash(instance)].acquire(blocking=False)
                    if locked:
                        try:
                            time.sleep(to_wait)
                        finally:
                            self.locks[hash(instance)].release()
                    else:
                        return None  # drop

            self.last_start[hash(instance)] = time.perf_counter()
            return func(instance, *args, **kwargs)

        return wrapped
