"""Helpful utilities for the AiiDAlab tools."""
from __future__ import annotations

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
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from cachetools import TTLCache, cached
from packaging.requirements import Requirement
from packaging.utils import NormalizedName, canonicalize_name

from .config import AIIDALAB_REGISTRY
from .environment import Environment
from .fetch import fetch_from_url
from .metadata import Metadata

logger = logging.getLogger(__name__)
FIND_INSTALLED_PACKAGES_CACHE = TTLCache(maxsize=32, ttl=60)  # type: ignore

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


def load_app_registry_index() -> Any:
    """Load apps' information from the AiiDAlab registry."""
    try:
        return requests.get(f"{AIIDALAB_REGISTRY}/apps_index.json").json()
    except (ValueError, requests.ConnectionError) as error:
        raise RuntimeError(f"Unable to load registry index: '{error}'")


def load_app_registry_entry(app_id: str) -> Any:
    """Load registry enty for app with app_id."""
    try:
        return requests.get(f"{AIIDALAB_REGISTRY}/apps/{app_id}.json").json()
    except (ValueError, requests.ConnectionError):
        logger.debug(f"Unable to load registry entry for app with id '{app_id}'.")
        return None


class PEP508CompliantUrl(str):
    """Represents a PEP 508 compliant URL."""

    pass


def parse_app_repo(
    url: str, metadata_fallback: dict[str, Any] | None = None
) -> dict[str, Any] | None:
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
            metadata = metadata_fallback  # type: ignore

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

    def __init__(self, calls_per_second: int = 1):
        self.calls_per_second = calls_per_second
        self.last_start = defaultdict(lambda: -1)  # type: ignore
        self.locks = defaultdict(Lock)  # type: ignore

    def __call__(self, func):  # type: ignore
        """Return decorator function."""

        @wraps(func)
        def wrapped(instance, *args, **kwargs):  # type: ignore
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

    def __init__(self, name: str, version: str | None = None):
        """If version is None, means not confinement for the version therefore
        the package always fulfill."""
        self._name = name  # underscore to avoid name clash with property canonical_name
        self.version = version

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.canonical_name}, {self.version})"

    def __str__(self) -> str:
        return f"{self.canonical_name}=={self.version}"

    @property
    def canonical_name(self) -> NormalizedName:
        """Return the cananicalized name of the package."""
        return canonicalize_name(self._name)

    def fulfills(self, requirement: Requirement) -> bool:
        """Returns True if this entry fulfills the requirement."""
        return self.canonical_name == canonicalize_name(requirement.name) and (
            self.version in requirement.specifier or self.version is None
        )


@cached(cache=FIND_INSTALLED_PACKAGES_CACHE)
def find_installed_packages(python_bin: str | None = None) -> dict[str, Package]:
    """Return all currently installed packages."""
    output = _pip_list(python_bin)
    return {
        canonicalize_name(package["name"]): Package(
            name=canonicalize_name(package["name"]), version=package["version"]
        )
        for package in output
    }


def _pip_list(python_bin: str | None = None) -> Any:
    """Return all currently installed packages."""
    if python_bin is None:
        python_bin = sys.executable
    output = run(
        [python_bin, "-m", "pip", "list", "--format=json"],
        encoding="utf-8",
        capture_output=True,
    ).stdout

    return json.loads(output)


def get_package_by_name(packages: dict[str, Package], name: str) -> Package | None:
    """Return the package with the given name from the list of packages.
    The name can be the canonicalized name or the requirement name which may not canonicalized.
    We try to convert the name to the canonicalized in both side and compare them.

    For example, the requirement name is 'jupyter-client' and the package name is 'jupyter_client'.
    The implementation of this method is inspired by https://github.com/pypa/pip/pull/8054
    """
    for package in packages.values():
        if package.canonical_name == canonicalize_name(name):
            return package
    return None


def split_git_url(git_url):  # type: ignore
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


def this_or_only_subdir(path: Path) -> Path:
    members = list(path.iterdir())
    return members[0] if len(members) == 1 and members[0].is_dir() else path


def run_pip_install(*args: Any, python_bin: str) -> Any:
    return subprocess.Popen(
        [python_bin, "-m", "pip", "install", "--user", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def run_reentry_scan() -> Any:
    return subprocess.Popen(
        ["reentry", "scan"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def run_verdi_daemon_restart() -> Any:
    return subprocess.Popen(
        ["verdi", "daemon", "restart"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def run_post_install_script(post_install_script_path: Path) -> Any:
    return subprocess.Popen(
        f"./{post_install_script_path.resolve().stem}",
        cwd=post_install_script_path.resolve().parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
