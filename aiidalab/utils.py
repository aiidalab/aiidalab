"""Helpful utilities for the AiiDAlab tools."""

import json
import logging
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from functools import wraps
from pathlib import Path
from subprocess import run
from threading import Lock
from urllib.parse import urlsplit, urlunsplit

import requests
from cachetools import TTLCache, cached
from packaging.utils import canonicalize_name

from .config import AIIDALAB_REGISTRY
from .environment import Environment
from .fetch import fetch_from_url
from .metadata import Metadata

logger = logging.getLogger(__name__)
FIND_INSTALLED_PACKAGES_CACHE = TTLCache(maxsize=32, ttl=60)

# Warning: try-except is a fix for Quantum Mobile release v19.03.0 where
# requests_cache is not installed.
try:
    import requests_cache
except ImportError:
    logger.warning(
        "The requests_cache package is missing.  Requests made to the app "
        "registry will not be cached!"
    )
else:
    # Install global cache for all requests.

    # The cache file is placed within the user home directory.
    cache_file = Path.home().joinpath(".cache", "requests", "cache")
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    # The cache is configured to avoid spamming the index server with requests
    # that are made in rapid succession and also serves as a fallback in case
    # that the index server is not reachable.
    requests_cache.install_cache(
        cache_name=str(cache_file),
        backend="sqlite",
        expire_after=60,  # seconds
        old_data_on_error=True,
    )


def load_app_registry_index():
    """Load apps' information from the AiiDAlab registry."""
    try:
        return requests.get(f"{AIIDALAB_REGISTRY}/apps_index.json").json()
    except (ValueError, requests.ConnectionError) as error:
        raise RuntimeError(f"Unable to load registry index: '{error}'")


def load_app_registry_entry(app_id):
    """Load registry enty for app with app_id."""
    try:
        return requests.get(f"{AIIDALAB_REGISTRY}/apps/{app_id}.json").json()
    except (ValueError, requests.ConnectionError):
        logger.debug(f"Unable to load registry entry for app with id '{app_id}'.")
        return None


class PEP508CompliantUrl(str):
    """Represents a PEP 508 compliant URL."""

    pass


def parse_app_repo(url, metadata_fallback=None):
    """Parse an app repo for metadata and other information.

    Use this function to parse a local or remote app repository for the app
    metadata and environment specification.

    Examples:

    For a local app repository, provide the absolute or relative path:

        url="/path/to/aiidalab-hello-world"

    For a remote app repository, provide a PEP 508 compliant URL, for example:

        url="git+https://github.com/aiidalab/aiidalab-hello-world.git@v1.0.0"
    """
    with fetch_from_url(url) as repo:
        try:
            metadata = asdict(Metadata.parse(repo))
        except TypeError as error:
            logger.debug(f"Failed to parse metadata for '{url}': {error}")
            metadata = metadata_fallback

        return {
            "metadata": metadata,
            "environment": asdict(Environment.scan(repo)),
        }


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


@cached(cache=FIND_INSTALLED_PACKAGES_CACHE)
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


def run_pip_install(*args, python_bin=sys.executable):
    return subprocess.Popen(
        [python_bin, "-m", "pip", "install", *args],
        bufsize=1,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def run_reentry_scan():
    return subprocess.Popen(
        ["reentry", "scan"],
        bufsize=1,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def run_verdi_daemon_restart():
    return subprocess.Popen(
        ["verdi", "daemon", "restart"],
        bufsize=1,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
