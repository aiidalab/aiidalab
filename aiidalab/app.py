"""Module to manage AiiDAlab apps."""

from __future__ import annotations

import errno
import io
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from enum import Enum, Flag, auto
from itertools import repeat
from pathlib import Path
from subprocess import CalledProcessError
from threading import Thread
from time import sleep
from typing import Any, Generator
from urllib.parse import urldefrag, urlsplit, urlunsplit
from uuid import uuid4

import requests
import traitlets
from dulwich.errors import NotGitRepository
from packaging.requirements import Requirement
from packaging.version import parse
from watchdog.events import EVENT_TYPE_OPENED, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from aiidalab.utils import (
    FIND_INSTALLED_PACKAGES_CACHE,
    Package,
    PEP508CompliantUrl,
    find_installed_packages,
    get_package_by_name,
    load_app_registry_entry,
    load_app_registry_index,
    run_pip_install,
    run_post_install_script,
    run_reentry_scan,
    run_verdi_daemon_restart,
    split_git_url,
    this_or_only_subdir,
    throttled,
)

from .config import AIIDALAB_APPS
from .environment import Environment
from .git_util import GitManagedAppRepo as Repo
from .git_util import git_clone
from .metadata import Metadata

logger = logging.getLogger(__name__)

_CORE_PACKAGES = [Package("aiida-core"), Package("jupyter-client")]


# A version is usually of type str, but it can also be a value
# of this Enum to indicate special app states in which the
# version cannot be determined, e.g., because the app is in a
# detached state, or because the app is not installed at all.
class AppVersion(Enum):
    UNKNOWN = auto()
    NOT_INSTALLED = auto()


class AppRemoteUpdateStatus(Flag):
    NOT_REGISTERED = auto()
    UP_TO_DATE = auto()
    UPDATE_AVAILABLE = auto()
    CANNOT_REACH_REGISTRY = auto()
    DETACHED = auto()


@dataclass
class _AiidaLabApp:
    metadata: dict[str, Any]
    name: str
    path: Path
    releases: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_registry_entry(
        cls, path: Path, registry_entry: dict[str, Any]
    ) -> _AiidaLabApp:
        return cls(
            path=path,
            **{
                key: value
                for key, value in registry_entry.items()
                if key in ("metadata", "name", "releases")
            },
        )

    @classmethod
    def _registry_entry_from_path(cls, path: Path) -> dict[str, Any]:
        try:
            return {
                "name": path.stem,
                "metadata": asdict(Metadata.parse(path)),
                "releases": None,
            }
        except (TypeError, ValueError):
            logger.debug(f"Unable to parse metadata from '{path}'")
            return {
                "name": path.stem,
                "metadata": dict(title=path.stem, description=""),
                "releases": None,
            }

    @classmethod
    def from_id(
        cls,
        app_id: str,
        registry_entry: dict[str, Any] | None = None,
        apps_path: str | None = None,
    ) -> _AiidaLabApp:
        if apps_path is None:
            apps_path = AIIDALAB_APPS

        app_path = Path(apps_path).joinpath(app_id)

        if registry_entry is None:
            local_registry_entry = cls._registry_entry_from_path(app_path)
            remote_registry_entry = load_app_registry_entry(app_id)
            registry_entry = remote_registry_entry or local_registry_entry

        return cls.from_registry_entry(path=app_path, registry_entry=registry_entry)

    def is_registered(self) -> bool | None:
        try:
            app_registry_index = load_app_registry_index()
        except RuntimeError as error:
            logger.warning(str(error))
            return None
        else:
            return self.name in app_registry_index["apps"]

    @property
    def _repo(self) -> Repo | None:
        try:
            return Repo(str(self.path))
        except NotGitRepository:
            return None

    def installed_version(self) -> AppVersion | str:
        if self._repo and self.is_registered():
            if self.dirty():
                return AppVersion.UNKNOWN
            else:
                try:
                    head_commit = self._repo.head().decode()
                    versions_by_commit = {
                        split_git_url(release["url"])[1]: version
                        for version, release in self.releases.items()
                        if urlsplit(release["url"]).scheme.startswith("git+")
                    }
                    return versions_by_commit.get(
                        head_commit, self.metadata.get("version", AppVersion.UNKNOWN)
                    )
                except Exception as error:
                    logger.debug(
                        f"Encountered error while determining version: {error}"
                    )
                    return AppVersion.UNKNOWN
        elif self.is_installed():
            return self.metadata.get("version", AppVersion.UNKNOWN)

        return AppVersion.NOT_INSTALLED

    def available_versions(
        self,
        python_bin: str | None = None,
        prereleases: bool = False,
    ) -> Generator[str, None, None]:
        """Return a list of available versions excluding the ones with core dependency conflicts."""
        if self.is_registered():
            for version in sorted(self.releases, key=parse, reverse=True):
                version_requirements = [
                    Requirement(r)
                    for r in (
                        self.releases[version]
                        .get("environment", {})
                        .get("python_requirements", [])
                    )
                ]
                if (
                    prereleases or not parse(version).is_prerelease
                ) and self._strict_dependencies_met(version_requirements, python_bin):
                    yield version

    def dirty(self):
        if self._repo:
            return self._repo.dirty()

    def is_installed(self) -> bool:
        """The app is installed if the corresponding folder is present."""
        return self.path.exists()

    def remote_update_status(self, prereleases: bool = False) -> AppRemoteUpdateStatus:
        """Determine the remote update satus.

        Arguments:
            prereleases (Bool):
                Set to True to include available preleases. Defaults to False.
        Returns:
            AppRemoteUpdateStatus
        """
        if self.is_installed():
            # Check whether app is registered.
            if self.is_registered() is None:
                return AppRemoteUpdateStatus.CANNOT_REACH_REGISTRY

            if self.is_registered() is False:
                return AppRemoteUpdateStatus.NOT_REGISTERED

            # Check whether the locally installed version is a registered release.
            installed_version = self.installed_version()
            if installed_version is AppVersion.UNKNOWN:
                return AppRemoteUpdateStatus.DETACHED

            # Check whether the locally installed version is the latest release.
            available_versions = list(self.available_versions(prereleases=prereleases))
            if len(available_versions) and installed_version != available_versions[0]:
                return AppRemoteUpdateStatus.UPDATE_AVAILABLE

            # App must be up-to-date.
            return AppRemoteUpdateStatus.UP_TO_DATE

        return AppRemoteUpdateStatus(0)  # app is not installed

    def _move_to_trash(self) -> Path | None:
        trash_path = Path.home().joinpath(".trash", f"{self.name}-{uuid4()!s}")
        if self.path.exists():
            trash_path.parent.mkdir(parents=True, exist_ok=True)
            self.path.rename(trash_path)
            return trash_path
        return None

    def _restore_from(self, trash_path: Path) -> None:
        self._move_to_trash()
        trash_path.rename(self.path)

    def uninstall(self) -> None:
        self._move_to_trash()

    def find_matching_releases(self, specifier, prereleases=None):
        matching_releases = list(
            specifier.filter(self.releases or [], prereleases=prereleases)
        )
        # Sort by intrinsic order (e.g. 1.1.0 -> 1.0.1 -> 1.0.0 and so on)
        matching_releases.sort(key=parse, reverse=True)
        return matching_releases

    @staticmethod
    def _strict_dependencies_met(
        requirements: list[Requirement], python_bin: str | None
    ) -> bool:
        """Check whether the given requirements are compatible with the core dependencies of a package."""
        from packaging.utils import canonicalize_name

        packages = find_installed_packages(python_bin)
        # Too avoid subtle bugs, we canonicalize the names of the requirements.
        requirements_dict = {canonicalize_name(r.name): r for r in requirements}
        for core in _CORE_PACKAGES:
            installed_core_package = get_package_by_name(packages, core.canonical_name)
            if (
                core.canonical_name in requirements_dict
                and installed_core_package is not None
                and not installed_core_package.fulfills(
                    requirements_dict[core.canonical_name]
                )
            ):
                return False
        return True

    @staticmethod
    def _find_incompatibilities_python(
        requirements: list[str], python_bin: str
    ) -> Generator[Requirement, None, None]:
        packages = find_installed_packages(python_bin)
        for requirement in map(Requirement, requirements):
            pkg = get_package_by_name(packages, requirement.name)
            if pkg is None:
                yield requirement
            elif not pkg.fulfills(requirement):
                yield requirement

    def is_detached(self) -> bool:
        """Check whether the app is detached from the registry."""
        return self.remote_update_status() == AppRemoteUpdateStatus.DETACHED

    def find_incompatibilities(self, version, python_bin=None):
        """Compatibility is checked by comparing the app requirements
        with the packages installed in the python environment.

        If the app is registered the list of requirements is fetched from the registry for the specific version.
        If the app is not registered or if it is detached (i.e. locally modified),
        the requirements list is read from the local repository (e.g. by parsing setup.cfg).
        """
        if python_bin is None:
            python_bin = sys.executable

        if not self.is_registered() or self.is_detached():
            environment = asdict(Environment.scan(self.path))
        else:
            environment = self.releases[version].get("environment", {})

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

    def find_dependencies_to_install(
        self, version_to_install: str, python_bin: str | None = None
    ) -> list[dict[str, Package | Requirement]]:
        """Returns a list of dependencies that need to be installed.

        If an unsupported version of a dependency is installed, it will look
        something like: {installed=<Package...>, required=<Requirement(...)>}.

        If the dependency is not present at all, it will look something like:
        {installed=None, required=<Requirement(...)>}.
        """
        if python_bin is None:
            python_bin = sys.executable

        if not version_to_install:
            return []

        unmatched_dependencies = {
            dep[1].name: dep[1]
            for dep in self.find_incompatibilities(version_to_install, python_bin)
        }
        installed_packages = find_installed_packages(python_bin)
        return [
            {
                "installed": get_package_by_name(installed_packages, name),
                "required": requirement,
            }
            for name, requirement in unmatched_dependencies.items()
        ]

    def _install_dependencies(self, python_bin, stdout):
        """Try to install the app dependencies with pip (if specified)."""

        def _should_run_reentry():
            # We do not need to run reentry scan for aiida-core>=2"""
            packages = find_installed_packages(python_bin=None)
            installed_aiida = get_package_by_name(packages, "aiida-core")
            # In practice this should never happen
            if installed_aiida is None:
                return False
            aiida_v1 = Requirement("aiida-core<2.0.0b1")
            # This is needed to handle pre-release versions such as 1.0.0b0
            aiida_v1.specifier.prereleases = True
            if installed_aiida.fulfills(aiida_v1):
                return True
            return False

        def _pip_install(*args, stdout):
            # The implementation of this function is taken and adapted from:
            # https://www.endpoint.com/blog/2015/01/getting-realtime-output-using-python/

            # Install package dependencies.
            logger.info(f"Running 'pip install --user {' '.join(args)}'\n")
            process = run_pip_install(*args, python_bin=python_bin)
            for line in io.TextIOWrapper(process.stdout, encoding="utf-8"):
                stdout.write(line)
            process.wait()
            if process.returncode != 0:
                raise RuntimeError("Failed to install dependencies.")

            # AiiDA plugins require reentry run to be found by AiiDA.
            if _should_run_reentry():
                logger.info("\nRunning 'reentry scan'\n")
                process = run_reentry_scan()
                for line in io.TextIOWrapper(process.stdout, encoding="utf-8"):
                    stdout.write(line)
                process.wait()
                if process.returncode != 0:
                    # Let's not fail the install because of this, just emit a warning.
                    logger.warning("'reentry scan' failed")

            # Restarting the AiiDA daemon to import newly installed plugins.
            process = run_verdi_daemon_restart()
            for line in io.TextIOWrapper(process.stdout, encoding="utf-8"):
                stdout.write(line)
            process.wait()
            if process.returncode != 0:
                raise RuntimeError("Failed to restart verdi daemon.")

        for path in (self.path.joinpath(".aiidalab"), self.path):
            if path.exists():
                try:
                    if (
                        path.joinpath("setup.py").is_file()
                        or path.joinpath("pyproject.toml").is_file()
                    ):
                        _pip_install(str(path), stdout=stdout)
                    elif path.joinpath("requirements.txt").is_file():
                        _pip_install(
                            f"--requirement={path.joinpath('requirements.txt')}",
                            stdout=stdout,
                        )
                    else:
                        logger.warning(
                            f"Warning: App '{self.name}' does not declare any dependencies."
                        )
                    break
                except CalledProcessError:
                    raise RuntimeError("Failed to install dependencies.")

    def _post_install_triggers(self) -> None:
        """Run a post_install script.

        Typically used to execute additional commands after the app installation.
        """
        post_install_file = self.path.joinpath("post_install")
        if post_install_file.exists():
            logger.info(f"Running post_install script: {post_install_file}")
            # We do not track of the output for the execution of the
            # post_install script, because it may prevent intentional
            # detachment of child processes. For example, an app might trigger
            # a background process that is supposed to finish after the
            # installation is technically completed.
            process = run_post_install_script(post_install_file)
            process.wait()
            if process.returncode != 0:
                logger.error(
                    f'Post-install script "{post_install_file}" returned an error!'
                )
                raise CalledProcessError(process.returncode, str(post_install_file))

    def _install_from_path(self, path):
        if path.is_dir():
            shutil.copytree(this_or_only_subdir(path), self.path)
        else:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with tarfile.open(path) as tar_file:

                    def is_within_directory(directory, target):
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)

                        prefix = os.path.commonprefix([abs_directory, abs_target])

                        return prefix == abs_directory

                    def safe_extract(
                        tar, path=".", members=None, *, numeric_owner=False
                    ):
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")

                        tar.extractall(path, members, numeric_owner=numeric_owner)

                    safe_extract(tar_file, path=tmp_dir)
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

    def install(
        self,
        version=None,
        python_bin=None,
        install_dependencies=True,
        stdout=sys.stdout,
        prereleases=False,
        post_install_triggers=True,
    ):
        if version is None:
            try:
                version = [
                    version
                    for version in sorted(self.releases, key=parse)
                    if prereleases or not parse(version).is_prerelease
                ][-1]
            except IndexError:
                raise ValueError(f"No versions available for '{self}'.")
        if python_bin is None:
            python_bin = sys.executable

        if isinstance(version, PEP508CompliantUrl):
            url = version
        else:
            url = self.releases[version]["url"]

        trash_path = self._move_to_trash()

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

            # Install dependencies
            if install_dependencies:
                self._install_dependencies(python_bin, stdout)

            # Run post-installation triggers.
            if post_install_triggers:
                self._post_install_triggers()

        # NOTE: We want to catch everything, including keyboard interrupt,
        # so we can rollback incomplete installation.
        except BaseException as error:
            try:
                if trash_path is None:
                    # App, was not previously installed, just remove it.
                    logger.warning("Removing partially installed app.")
                    self._move_to_trash()
                else:
                    # Attempt rollback to previous version.
                    logger.warning(
                        "Performing rollback to previously installed version."
                    )
                    self._restore_from(trash_path)
            except RuntimeError as inner_error:
                logger.error(f"Rollback failed due to error: {inner_error}!")
            finally:
                raise RuntimeError(
                    f"Failed to install '{self.name}' (version={version}) at '{self.path}'"
                ) from error


class AppNotInstalledException(Exception):
    pass


class AiidaLabAppWatch:
    """Watch to monitor the app installation status.

    Create a watch instance to monitor the installation status of an
    AiiDAlab app. This is achieved by monitoring the app repository
    for existance and changes.

    If there is a change in the app repository, the app is refreshed.

    Arguments:
        app (AiidaLabApp):
            The AiidaLab app to monitor.
    """

    class AppPathFileSystemEventHandler(FileSystemEventHandler):  # type: ignore
        """Internal event handeler for app path file system events."""

        def __init__(self, app):
            self.app = app

        def on_any_event(self, event):
            """Refresh app for any event except opened."""
            if event.event_type != EVENT_TYPE_OPENED:
                self.app.refresh_async()

    def __init__(self, app):
        self.app = app

        self._started = False
        self._monitor_thread = None
        self._observer = None
        self._monitor_thread_stop = threading.Event()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}(app={self.app!r})>"

    def _start_observer(self) -> None:
        """Start the directory observer thread.

        The ._observer thread is controlled by the ._monitor_thread.
        """
        assert os.path.isdir(self.app.path)
        assert self._observer is None or not self._observer.is_alive()

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

    def _stop_observer(self) -> None:
        """Stop the directory observer thread.

        The ._observer thread is controlled by the ._monitor_thread.
        """
        assert self._observer is not None
        self._observer.stop()

    def start(self) -> None:
        """Watch the app repository for file system events.

        The app state is refreshed automatically for all events.
        """
        if self._started:
            raise RuntimeError(
                f"Instances of {type(self).__name__} can only be started once."
            )

        if self._monitor_thread is None:

            def check_path_exists_changed() -> None:
                is_dir = os.path.isdir(self.app.path)
                while not self._monitor_thread_stop.is_set():
                    switched = is_dir != os.path.isdir(self.app.path)
                    if switched:
                        # this is for when the app folder first time create or deleted
                        is_dir = not is_dir
                        self.app.refresh()

                    if is_dir:
                        if self._observer is None or not self._observer.is_alive():
                            self._start_observer()
                    elif self._observer and self._observer.is_alive():
                        self._stop_observer()

                    sleep(1)

                # stop-flag set, stopping observer...
                if self._observer:
                    self._observer.stop()

            self._monitor_thread = Thread(target=check_path_exists_changed)
            self._monitor_thread_stop.clear()
            self._monitor_thread.start()

        self._started = True

    def stop(self) -> None:
        """Stop watching the app repository for file system events."""
        if self._monitor_thread is not None:
            self._monitor_thread_stop.set()

    def is_alive(self) -> bool | None:
        """Return True if this watch is still alive."""
        return self._monitor_thread and self._monitor_thread.is_alive()

    def join(self, timeout: float | None = None) -> None:
        """Join the watch and observer after stopping.

        This function will timeout if a timeout argument is provided. Use the
        is_alive() function to determien whether the watch was stopped within
        the given timout.
        """
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=timeout)
        if self._observer is not None:
            self._observer.join(timeout=timeout)


class AiidaLabApp(traitlets.HasTraits):  # type: ignore
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

    path = traitlets.Unicode(allow_none=True).tag(readonly=True)
    install_info = traitlets.Unicode()

    available_versions = traitlets.List(traitlets.Unicode())
    installed_version = traitlets.Union(
        [traitlets.Unicode(), traitlets.UseEnum(AppVersion)]
    )  # installed_version is updated from _AiiDALabApp only
    version_to_install = traitlets.Unicode(allow_none=True)
    dependencies_to_install = traitlets.List()
    remote_update_status = traitlets.UseEnum(
        AppRemoteUpdateStatus, allow_none=True
    ).tag(readonly=True)
    has_prereleases = traitlets.Bool()
    include_prereleases = traitlets.Bool()

    busy = traitlets.Bool().tag(readonly=True)
    detached = traitlets.Bool(allow_none=True).tag(readonly=True)
    compatible = traitlets.Bool(allow_none=True).tag(readonly=True)
    compatibility_info = traitlets.Dict()

    def __init__(
        self,
        name: str,
        app_data: dict[str, Any],
        aiidalab_apps_path: str,
        watch: bool = True,
    ):
        self._app = _AiidaLabApp.from_id(
            name, registry_entry=app_data, apps_path=aiidalab_apps_path
        )
        super().__init__()

        self.name = self._app.name

        self._busy_count = 0
        self._busy_count_lock = threading.Lock()

        try:
            self.logo = self._app.metadata["logo"]
        except KeyError:
            raise ValueError(f"Did not find logo in {self.name} metadata")
        try:
            self.categories = self._app.metadata["categories"]
        except KeyError:
            raise ValueError(f"Did not find categories in {self.name} metadata")

        self.is_installed = self._app.is_installed
        self.path = str(self._app.path)
        self.refresh_async()

        if watch:
            self._watch = AiidaLabAppWatch(self)
            self._watch.start()
        else:
            self._watch = None  # type: ignore

    def __str__(self):
        return f"<AiidaLabApp name='{self._app.name}'>"

    @traitlets.default("include_prereleases")
    def _default_include_prereleases(self):
        "Provide default value for include_prereleases trait." ""
        return False

    @traitlets.observe("include_prereleases")
    def _observe_include_prereleases(self, change):
        if change["old"] != change["new"]:
            self.refresh()

    @traitlets.default("detached")
    def _default_detached(self):
        """Provide default value for detached traitlet."""
        if self.is_installed():
            return (
                self._app.dirty() or self._get_installed_version() is AppVersion.UNKNOWN
            )
        return None

    @traitlets.default("busy")
    def _default_busy(self):  # pylint: disable=no-self-use
        return False

    @traitlets.validate("version_to_install")
    def _validate_version_to_install(self, proposal):
        """Validate the version to install."""
        with self._show_busy():
            if proposal["value"] is None:
                return

            if proposal["value"] not in self.available_versions:
                raise traitlets.TraitError(
                    f"Version {proposal['value']} is not available for {self.name} app."
                )
            return proposal["value"]

    @traitlets.observe("version_to_install")
    def _observe_version_to_install(self, change):
        if change["old"] != change["new"]:
            self.refresh()

    @contextmanager
    def _show_busy(self):
        """Apply this decorator to indicate that the app is busy during execution."""
        # we need to use a lock here, because the busy trait is not thread-safe
        # we may use _show_busy in different threads, e.g. when installing and auto-status refresh
        with self._busy_count_lock:
            self._busy_count += 1
            self.set_trait("busy", True)

        try:
            yield
        finally:
            with self._busy_count_lock:
                self._busy_count -= 1

                if self._busy_count == 0:
                    self.set_trait("busy", False)

    def in_category(self, category):
        # One should test what happens if the category won't be defined.
        return category in self.categories

    def _has_git_repo(self):
        """Check if the app has a .git folder in it."""
        try:
            Repo(self.path)
            return True
        except NotGitRepository:
            return False

    def install_app(
        self, version: str | None = None, stdout: str | None = None
    ) -> AppVersion | str:
        """Installing the app."""
        with self._show_busy():
            self._app.install(
                version=version, stdout=stdout, prereleases=self.include_prereleases
            )
            FIND_INSTALLED_PACKAGES_CACHE.clear()
            self.refresh()
            return self._get_installed_version()

    def update_app(
        self, _: str | None = None, stdout: str | None = None
    ) -> AppVersion | str:
        """Perform app update."""
        with self._show_busy():
            # Installing with version=None automatically selects latest
            # available version.
            version = self.install_app(version=None, stdout=stdout)
            FIND_INSTALLED_PACKAGES_CACHE.clear()
            self.refresh()
            return version

    def uninstall_app(self, _=None):
        """Perfrom app uninstall."""
        # Perform uninstall process.
        with self._show_busy():
            self._app.uninstall()
            self.refresh()

    def _get_installed_version(self) -> AppVersion | str:
        """Determine the currently installed version."""
        return self._app.installed_version()

    @traitlets.default("compatible")  # type: ignore
    def _default_compatible(self) -> None:  # pylint: disable=no-self-use
        return None

    def _is_compatible(self, app_version: str) -> bool:
        """Determine whether the specified version is compatible."""
        try:
            incompatibilities = dict(
                self._app.find_incompatibilities(version=app_version)
            )
            self.compatibility_info = {
                app_version: [
                    f"({eco_system}) {requirement}"
                    for eco_system, requirement in incompatibilities.items()
                ]
            }

            return not any(incompatibilities)
        except KeyError:
            return False  # compatibility indetermined for given version

    def _refresh_versions(self) -> None:
        self.installed_version = (
            self._get_installed_version()
        )  # only update at this refresh method
        self.include_prereleases = self.include_prereleases or (
            isinstance(self.installed_version, str)
            and parse(self.installed_version).is_prerelease
        )

        all_available_versions = list(self._app.available_versions(prereleases=True))
        self.has_prereleases = any(
            parse(version).is_prerelease for version in all_available_versions
        )

        self.available_versions = list(
            self._app.available_versions(prereleases=self.include_prereleases)
        )

    def _refresh_dependencies_to_install(self) -> None:
        self.dependencies_to_install = self._app.find_dependencies_to_install(
            self.version_to_install
        )

    @throttled(calls_per_second=1)  # type: ignore
    def refresh(self) -> None:
        """Refresh app state."""
        with self._show_busy():
            with self.hold_trait_notifications():
                self._refresh_versions()
                self._refresh_dependencies_to_install()
                self.set_trait(
                    "compatible", self._is_compatible(self.installed_version)
                )
                self.set_trait(
                    "remote_update_status",
                    self._app.remote_update_status(
                        prereleases=self.include_prereleases
                    ),
                )
                self.set_trait(
                    "detached",
                    (self.installed_version is AppVersion.UNKNOWN)
                    if (self._has_git_repo() and self._app.is_registered())
                    else None,
                )

    def refresh_async(self) -> None:
        """Asynchronized (non-blocking) refresh of the app state."""
        refresh_thread = Thread(target=self.refresh)
        refresh_thread.start()

    @property
    def metadata(self):
        """Return metadata dictionary. Give the priority to the local copy (better for the developers)."""
        return self._app.metadata

    def _get_from_metadata(self, what: str) -> str:
        """Get information from metadata."""
        try:
            return f"{self._app.metadata[what]}"
        except KeyError:
            return f'Field "{what}" is not present in app metadata.'

    @property
    def authors(self) -> str:
        return self._get_from_metadata("authors")

    @property
    def description(self) -> str:
        return self._get_from_metadata("description")

    @property
    def title(self) -> str:
        return self._get_from_metadata("title")

    @property
    def url(self) -> str:
        """Provide explicit link to Git repository."""
        return self._get_from_metadata("external_url")

    @property
    def more(self) -> str:
        return f"""<a href=./single_app.ipynb?app={self.name}>Manage App</a>"""

    @property
    def _repo(self) -> Repo:
        """Returns Git repository."""
        if not self.is_installed():
            raise AppNotInstalledException("The app is not installed")
        return Repo(self.path)
