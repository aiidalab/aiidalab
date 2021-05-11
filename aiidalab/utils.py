"""Helpful utilities for the AiiDAlab tools."""

import sys
import json
import time
from collections import defaultdict
from functools import wraps
from subprocess import run
from threading import Lock
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

import requests
from cachetools import cached, TTLCache
from IPython.lib import backgroundjobs as bg
from packaging.utils import canonicalize_name

from .config import AIIDALAB_REGISTRY


def update_cache():
    """Run this process asynchronously."""
    requests_cache.install_cache(
        cache_name="apps_meta",
        backend="sqlite",
        expire_after=3600,
        old_data_on_error=True,
    )
    requests.get(AIIDALAB_REGISTRY)
    requests_cache.install_cache(cache_name="apps_meta", backend="sqlite")


# Warning: try-except is a fix for Quantum Mobile release v19.03.0 that does not have requests_cache installed
try:
    import requests_cache

    # At start getting data from cache
    requests_cache.install_cache(cache_name="apps_meta", backend="sqlite")

    # If requests_cache is installed, upgrade the cache in the background.
    UPDATE_CACHE_BACKGROUND = bg.BackgroundJobFunc(update_cache)
    UPDATE_CACHE_BACKGROUND.start()
except ImportError:
    pass


def load_app_registry_index():
    """Load apps' information from the AiiDAlab registry."""
    try:
        return requests.get(f"{AIIDALAB_REGISTRY}/apps_index.json").json()
    except (ValueError, requests.ConnectionError):
        print("Registry server is unavailable! Can't check for the updates")
        return dict(apps=dict(), catgories=dict())


def load_app_registry_entry(app_id):
    """Load registry enty for app with app_id."""
    try:
        return requests.get(f"{AIIDALAB_REGISTRY}/apps/{app_id}.json").json()
    except (ValueError, requests.ConnectionError):
        print(f"Unable to load registry entry for app with id '{app_id}'.")
        return None


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


class Package:
    """Helper class to check whether a given package fulfills a requirement."""

    def __init__(self, name, version):
        self.name = name
        self.version = version

    def __str__(self):
        return f"{type(self).__name__}({self.name}, {self.version})"

    def fulfills(self, requirement):
        """Returns True if this entry fullfills the requirement."""
        return (
            canonicalize_name(self.name) == canonicalize_name(requirement.name)
            and self.version in requirement.specifier
        )


@cached(cache=TTLCache(maxsize=32, ttl=60))
def find_installed_packages(python_bin=None):
    """Return all currently installed packages."""
    if python_bin is None:
        python_bin = sys.executable
    output = run(
        [python_bin, "-m", "pip", "list", "--format=json"],
        encoding="utf-8",
        capture_output=True,
    ).stdout
    return [Package(**package) for package in json.loads(output)]


def split_git_url(git_url):
    """Split the base url and the ref pointer of a git url.

    For example: git+https://example.com/app.git@v1 is split into and returned
    as tuple: (git+https://example.com/app.git, v1)
    """

    parsed_url = urlsplit(git_url)
    if "@" in parsed_url.path:
        path, ref = parsed_url.path.rsplit("@", 1)
    else:
        path, ref = parsed_url.path, None
    return urlunsplit(parsed_url._replace(path=path)), ref


def this_or_only_subdir(path):
    members = list(path.iterdir())
    return members[0] if len(members) == 1 and members[0].is_dir() else path
