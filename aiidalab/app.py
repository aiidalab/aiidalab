# -*- coding: utf-8 -*-
"""Module to manage AiiDAlab apps."""

import errno
import os
import shutil
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from enum import Enum, auto
from itertools import repeat
from pathlib import Path
from threading import Thread
from time import sleep
from typing import List
from urllib.parse import urldefrag
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

import requests
import traitlets
from dulwich.errors import NotGitRepository
from packaging.requirements import Requirement
from packaging.version import parse
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver


from .config import AIIDALAB_APPS
from .git_util import GitManagedAppRepo as Repo
from .git_util import git_clone
from .utils import find_installed_packages
from .utils import load_app_registry_entry
from .utils import split_git_url
from .utils import this_or_only_subdir
from .utils import throttled


# A version is usually of type str, but it can also be a value
# of this Enum to indicate special app states in which the
# version cannot be determined, e.g., because the app is in a
# detached state, or because the app is not installed at all.
class AppVersion(Enum):
    UNKNOWN = auto()
    NOT_INSTALLED = auto()


@dataclass
class _AiidaLabApp:

    metadata: dict
    name: str
    path: Path
    categories: List[str] = field(default_factory=list)
    releases: dict = field(default_factory=dict)

    @classmethod
    def from_registry_entry(cls, path, registry_entry):
        return cls(
            path=path,
            **{
                key: value
                for key, value in registry_entry.items()
                if key in ("categories", "metadata", "name", "releases")
            },
        )

    @classmethod
    def from_id(cls, app_id, registry_entry=None, apps_path=None):
        if registry_entry is None:
            registry_entry = load_app_registry_entry(app_id) or dict(
                name=app_id, metadata=dict()
            )
        if apps_path is None:
            apps_path = AIIDALAB_APPS

        return cls.from_registry_entry(
            path=Path(apps_path).joinpath(app_id), registry_entry=registry_entry
        )

    @property
    def _repo(self):
        try:
            return Repo(str(self.path))
        except NotGitRepository:
            return None

    def installed_version(self):
        if self._repo:
            head_commit = self._repo.head().decode()
            versions_by_commit = {
                split_git_url(release["url"])[1]: version
                for version, release in self.releases.items()
                if urlsplit(release["url"]).scheme.startswith("git+")
            }
            return versions_by_commit.get(head_commit, AppVersion.UNKNOWN)
        elif self.path.exists():
            return AppVersion.UNKNOWN
        return AppVersion.NOT_INSTALLED

    def dirty(self):
        if self._repo:
            return self._repo.dirty()

    def uninstall(self):
        if self.path.exists():
            shutil.rmtree(self.path)

    def find_matching_releases(self, specifier):
        matching_releases = [
            version for version in self.releases if parse(version) in specifier
        ]
        # Sort by intrinsic order (e.g. 1.1.0 -> 1.0.1 -> 1.0.0 and so on)
        matching_releases.sort(key=parse, reverse=True)
        return matching_releases

    @staticmethod
    def _find_incompatibilities_python(requirements, python_bin):
        packages = find_installed_packages(python_bin)
        for requirement in map(Requirement, requirements):
            f = [p for p in packages if p.fulfills(requirement)]
            if not any(f):
                yield requirement

    def find_incompatibilities(self, version, python_bin=None):
        if python_bin is None:
            python_bin = sys.executable
        environment = self.releases[version].get("environment")
        for key, spec in environment.items():
            if key == "python_requirements":
                yield from zip(
                    repeat("python"),
                    self._find_incompatibilities_python(spec, python_bin),
                )
            else:
                raise ValueError(f"Unknown eco-system '{key}'")

    def is_compatible(self, version, python_bin=None):
        return not any(self.find_incompatibilities(version, python_bin))

    def _install_from_path(self, path):
        if path.is_dir():
            shutil.copytree(this_or_only_subdir(path), self.path)
        else:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with tarfile.open(path) as tar_file:
                    tar_file.extractall(path=tmp_dir)
                    self._install_from_path(Path(tmp_dir))

    def _install_from_https(self, url):
        response = requests.get(url, stream=True)
        response.raise_for_status()
        content = response.content

        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            self._install_from_path(Path(tmp_file.name))

    def _install_from_git_repository(self, git_url):
        if urldefrag(git_url).fragment:
            raise NotImplementedError(
                "Path specification via fragment not yet supported."
            )
        base_url, ref = split_git_url(git_url)
        git_clone(base_url, ref, self.path)

    def install(self, version=None):
        if version is None:
            try:
                version = list(sorted(self.releases, key=parse))[-1]
            except IndexError:
                raise ValueError("No versions available for '{self}'.")

        self.uninstall()

        url = self.releases[version]["url"]
        split_url = urlsplit(url)
        try:
            if split_url.scheme in ("", "file"):
                self._install_from_path(Path(split_url.path))
            elif split_url.scheme == "https":
                self._install_from_https(url)
            elif split_url.scheme == "git+file":
                self._install_from_git_repository(
                    urlunsplit(split_url._replace(scheme="file"))
                )
            elif split_url.scheme == "git+https":
                self._install_from_git_repository(
                    urlunsplit(split_url._replace(scheme="https"))
                )
            else:
                raise NotImplementedError(
                    "Unsupported scheme: {split_url.scheme} ({url})"
                )
        except RuntimeError as error:
            raise RuntimeError(
                f"Failed to install '{self.name}' (version={version}) at '{self.path}'"
                f", due to error: {error}"
            )


class AppNotInstalledException(Exception):
    pass


class AiidaLabAppWatch:
    """Watch to monitor the app installation status.

    Create a watch instance to monitor the installation status of an
    AiiDAlab app. This is achieved by monitoring the app repository
    for existance and changes.

    Arguments:
        app (AiidaLabApp):
            The AiidaLab app to monitor.
    """

    class AppPathFileSystemEventHandler(FileSystemEventHandler):
        """Internal event handeler for app path file system events."""

        def __init__(self, app):
            self.app = app

        def on_any_event(self, event):
            """Refresh app for any event."""
            self.app.refresh_async()

    def __init__(self, app):
        self.app = app

        self._started = False
        self._monitor_thread = None
        self._observer = None

    def __repr__(self):
        return f"<{type(self).__name__}(app={self.app!r})>"

    def _start_observer(self):
        """Start the directory observer thread.

        The ._observer thread is controlled by the ._monitor_thread.
        """
        assert os.path.isdir(self.app.path)
        assert self._observer is None or not self._observer.isAlive()

        event_handler = self.AppPathFileSystemEventHandler(self.app)

        self._observer = Observer()
        self._observer.schedule(event_handler, self.app.path, recursive=True)
        try:
            self._observer.start()
        except OSError as error:
            if error.errno in (errno.ENOSPC, errno.EMFILE) and "inotify" in str(error):
                # We reached the inotify watch limit, using polling-based fallback observer.
                self._observer = PollingObserver()
                self._observer.schedule(event_handler, self.app.path, recursive=True)
                self._observer.start()
            else:  # reraise unrelated error
                raise error

    def _stop_observer(self):
        """Stop the directory observer thread.

        The ._observer thread is controlled by the ._monitor_thread.
        """
        assert self._observer is not None
        self._observer.stop()

    def start(self):
        """Watch the app repository for file system events.

        The app state is refreshed automatically for all events.
        """
        if self._started:
            raise RuntimeError(
                f"Instances of {type(self).__name__} can only be started once."
            )

        if self._monitor_thread is None:

            def check_path_exists_changed():
                is_dir = os.path.isdir(self.app.path)
                while not self._monitor_thread.stop_flag:
                    switched = is_dir != os.path.isdir(self.app.path)
                    if switched:
                        is_dir = not is_dir
                        self.app.refresh()

                    if is_dir:
                        if self._observer is None or not self._observer.isAlive():
                            self._start_observer()
                    elif self._observer and self._observer.isAlive():
                        self._stop_observer()

                    sleep(1)

                # stop-flag set, stopping observer...
                if self._observer:
                    self._observer.stop()

            self._monitor_thread = Thread(target=check_path_exists_changed)
            self._monitor_thread.stop_flag = False
            self._monitor_thread.start()

        self._started = True

    def stop(self):
        """Stop watching the app repository for file system events."""
        if self._monitor_thread is not None:
            self._monitor_thread.stop_flag = True

    def is_alive(self):
        """Return True if this watch is still alive."""
        return self._monitor_thread and self._monitor_thread.is_alive()

    def join(self, timeout=None):
        """Join the watch after stopping.

        This function will timeout if a timeout argument is provided. Use the
        is_alive() function to determien whether the watch was stopped within
        the given timout.
        """
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=timeout)


class AiidaLabApp(traitlets.HasTraits):
    """Manage installation status of an AiiDAlab app.

    Arguments:

        name (str):
            Name of the Aiida lab app.
        app_data (dict):
            Dictionary containing the app metadata.
        aiidalab_apps_path (str):
            Path to directory at which the app is expected to be installed.
        watch (bool):
            If true (default), automatically watch the repository for changes.
    """

    path = traitlets.Unicode(allow_none=True, readonly=True)
    install_info = traitlets.Unicode()

    available_versions = traitlets.List(traitlets.Unicode)
    installed_version = traitlets.Union(
        [traitlets.Unicode(), traitlets.UseEnum(AppVersion)]
    )
    updates_available = traitlets.Bool(readonly=True, allow_none=True)

    busy = traitlets.Bool(readonly=True)
    detached = traitlets.Bool(readonly=True, allow_none=True)
    compatible = traitlets.Bool(readonly=True, allow_none=True)
    compatibility_info = traitlets.Dict()

    def __init__(self, name, app_data, aiidalab_apps_path, watch=True):
        self._app = _AiidaLabApp.from_id(
            name, registry_entry=app_data, apps_path=aiidalab_apps_path
        )
        super().__init__()

        self.name = self._app.name
        self.path = str(self._app.path)
        self.refresh_async()

        if watch:
            self._watch = AiidaLabAppWatch(self)
            self._watch.start()
        else:
            self._watch = None

    def __repr__(self):
        app_data_argument = (
            None if self._registry_data is None else asdict(self._registry_data)
        )
        return (
            f"AiidaLabApp(name={self.name!r}, app_data={app_data_argument!r}, "
            f"aiidalab_apps_path={os.path.dirname(self.path)!r})"
        )

    @traitlets.default("detached")
    def _default_detached(self):
        """Provide default value for detached traitlet."""
        if self.is_installed():
            return self._app.dirty() or self._installed_version() is AppVersion.UNKNOWN
        return None

    @traitlets.default("busy")
    def _default_busy(self):  # pylint: disable=no-self-use
        return False

    @contextmanager
    def _show_busy(self):
        """Apply this decorator to indicate that the app is busy during execution."""
        self.set_trait("busy", True)
        try:
            yield
        finally:
            self.set_trait("busy", False)

    def in_category(self, category):
        # One should test what happens if the category won't be defined.
        return category in self._registry_data.categories

    def is_installed(self):
        """The app is installed if the corresponding folder is present."""
        return os.path.isdir(self.path)

    def _has_git_repo(self):
        """Check if the app has a .git folder in it."""
        try:
            Repo(self.path)
            return True
        except NotGitRepository:
            return False

    def install_app(self, version=None):
        """Installing the app."""
        with self._show_busy():
            self._app.install(version=version)
            self.refresh()
            return self._installed_version()

    def update_app(self, _=None):
        """Perform app update."""
        with self._show_busy():
            # Installing with version=None automatically selects latest
            # available version.
            version = self.install_app(version=None)
            self.refresh()
            return version

    def uninstall_app(self, _=None):
        """Perfrom app uninstall."""
        # Perform uninstall process.
        with self._show_busy():
            self._app.uninstall()
            self.refresh()

    def _available_versions(self):
        """Return all available and compatible versions."""
        for version in sorted(self._app.releases, key=parse, reverse=True):
            if self._is_compatible(version):
                yield version

    def _installed_version(self):
        """Determine the currently installed version."""
        return self._app.installed_version()

    @traitlets.default("compatible")
    def _default_compatible(self):  # pylint: disable=no-self-use
        return None

    def _is_compatible(self, app_version):
        """Determine whether the currently installed version is compatible."""
        try:
            incompatibilities = dict(
                self._app.find_incompatibilities(version=app_version)
            )
            self.compatibility_info.update(
                {
                    app_version: [
                        f"({eco_system}) {requirement}"
                        for eco_system, requirement in incompatibilities.items()
                    ]
                }
            )
            return not any(incompatibilities)
        except KeyError:
            raise
            return None  # compatibility indetermined for given version

    def _updates_available(self):
        """Determine whether there are updates available.

        For this the app must be installed in a known version and there must be
        available (and compatible) versions.
        """
        installed_version = self._installed_version()
        if installed_version not in (AppVersion.UNKNOWN, AppVersion.NOT_INSTALLED):
            available_versions = list(self._available_versions())
            if len(available_versions):
                return self._installed_version() != available_versions[0]
        return False

    @throttled(calls_per_second=1)
    def refresh(self):
        """Refresh app state."""
        with self._show_busy():
            with self.hold_trait_notifications():
                self.available_versions = list(self._available_versions())
                self.installed_version = self._installed_version()
                self.set_trait(
                    "compatible", self._is_compatible(self.installed_version)
                )
                if self.is_installed() and self._has_git_repo():
                    self.installed_version = self._installed_version()
                    modified = self._repo.dirty()
                    self.set_trait(
                        "detached",
                        self.installed_version is AppVersion.UNKNOWN or modified,
                    )
                    self.set_trait("updates_available", self._updates_available())
                else:
                    self.set_trait("updates_available", None)
                    self.set_trait("detached", None)

    def refresh_async(self):
        """Asynchronized (non-blocking) refresh of the app state."""
        refresh_thread = Thread(target=self.refresh)
        refresh_thread.start()

    @property
    def metadata(self):
        """Return metadata dictionary. Give the priority to the local copy (better for the developers)."""
        return self._app.metadata

    def _get_from_metadata(self, what):
        """Get information from metadata."""
        try:
            return "{}".format(self._app.metadata[what])
        except KeyError:
            if not os.path.isfile(os.path.join(self.path, "metadata.json")):
                return "({}) metadata.json file is not present".format(what)
            return 'the field "{}" is not present in metadata.json file'.format(what)

    @property
    def authors(self):
        return self._get_from_metadata("authors")

    @property
    def description(self):
        return self._get_from_metadata("description")

    @property
    def title(self):
        return self._get_from_metadata("title")

    @property
    def url(self):
        """Provide explicit link to Git repository."""
        return getattr(self._registry_data, "git_url", None)

    @property
    def more(self):
        return """<a href=./single_app.ipynb?app={}>Manage App</a>""".format(self.name)

    @property
    def _repo(self):
        """Returns Git repository."""
        if not self.is_installed():
            raise AppNotInstalledException("The app is not installed")
        return Repo(self.path)
