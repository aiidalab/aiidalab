# -*- coding: utf-8 -*-
"""Module to manage AiiDAlab apps."""

import re
import os
import shutil
import json
import errno
from contextlib import contextmanager
from enum import Enum, auto
from time import sleep
from threading import Thread
from subprocess import check_output, STDOUT
from dataclasses import dataclass, field, asdict
from urllib.parse import urlsplit, urldefrag

from typing import List, Dict

import traitlets
from dulwich.porcelain import fetch
from dulwich.errors import NotGitRepository
from dulwich.objects import Tag, Commit
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from .config import AIIDALAB_DEFAULT_GIT_BRANCH
from .git_util import GitManagedAppRepo as Repo
from .utils import throttled


class AppNotInstalledException(Exception):
    pass


class AppRemoteUpdateError(RuntimeError):
    pass


# A version is usually of type str, but it can also be a value
# of this Enum to indicate special app states in which the
# version cannot be determined, e.g., because the app is in a
# detached state, or because the app is not installed at all.
class AppVersion(Enum):
    UNKNOWN = auto()
    NOT_INSTALLED = auto()


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
            if error.errno in (errno.ENOSPC, errno.EMFILE) and 'inotify' in str(error):
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
            raise RuntimeError(f"Instances of {type(self).__name__} can only be started once.")

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
    installed_version = traitlets.Union([traitlets.Unicode(), traitlets.UseEnum(AppVersion)])
    updates_available = traitlets.Bool(readonly=True, allow_none=True)

    busy = traitlets.Bool(readonly=True)
    detached = traitlets.Bool(readonly=True, allow_none=True)

    @dataclass
    class AppRegistryData:
        """Dataclass that contains the app data from the app registry."""
        git_url: str
        meta_url: str
        categories: List[str]
        groups: List[str]  # appears to be a duplicate of categories?
        metainfo: Dict[str, str] = field(default_factory=dict)
        gitinfo: Dict[str, str] = field(default_factory=dict)
        hosted_on: str = None

    class _GitReleaseLine:
        """Utility class to operate on the release line of the app.

        A release line is specified via the app url as part of the fragment (after '#').

        A release line can be specified either as
            a) a commit denoted by a hexadecimal number with either 20 or 40 digits, or
            b) a short reference, which can be either a branch or a tag name.

        A full ref is the ref as defined in the Git glossary, e.g., 'refs/heads/main'.
        A revision is either a full ref or a commit.
        """

        def __init__(self, app, line):
            self.app = app
            self.line = line

            match = re.fullmatch(r'(?P<commit>([0-9a-fA-F]{20}){1,2})|(?P<short_ref>.+)', line)
            if not match:
                raise ValueError(f"Illegal release line: {line}")

            self.commit = match.groupdict()['commit']
            self.short_ref = match.groupdict()['short_ref']
            assert self.commit or self.short_ref

        @property
        def _repo(self):
            return Repo(self.app.path)

        def _resolve_short_ref(self, short_ref):
            """Attempt to resolve the short-ref to a full ref.

            For example, 'branch' would be resolved to 'refs/heads/branch'
            if 'branch' is a local branch or 'refs/tags/branch' if it was
            a tag.

            This function returns None if the short-ref cannot be resolved
            to a full reference.
            """
            # Check if short-ref is among the remote refs:
            for ref in self._repo.refs.allkeys():
                if re.match(r'refs\/remotes\/(.*)?\/' + short_ref, ref.decode()):
                    return ref

            # Check if short-ref is a head (branch):
            if f'refs/heads/{short_ref}'.encode() in self._repo.refs.allkeys():
                return f'refs/heads/{short_ref}'.encode()

            # Check if short-ref is a tag:
            if f'refs/tags/{short_ref}'.encode() in self._repo.refs.allkeys():
                return f'refs/tags/{short_ref}'.encode()

            return None

        def find_versions(self):
            """Find versions available for this release line.

            When encountering an ambiguous release line name, i.e.,
            a shared branch and tag name, we give preference to the
            branch, because that is what git does in this situation.
            """
            assert self.short_ref or self.commit

            if self.commit:  # The release line is a commit.
                assert self.commit.encode() in self._repo.object_store
                yield self.commit.encode()
            else:
                ref = self._resolve_short_ref(self.short_ref)
                if ref is None:
                    raise ValueError(f"Unable to resolve {self.short_ref!r}. "
                                     "Are you sure this is a valid git branch or tag?")

                def get_sha(obj):
                    assert isinstance(obj, (Tag, Commit))
                    return obj.object[1] if isinstance(obj, Tag) else obj.id

                # The release line is a head (branch).
                if ref.startswith(b'refs/remotes/'):
                    ref_commit = self._repo.get_peeled(ref)
                    all_tags = {ref for ref in self._repo.get_refs() if ref.startswith(b'refs/tags')}
                    tags_lookup = {get_sha(self._repo[ref]): ref for ref in all_tags}
                    commits_on_head = self._repo.get_walker(self._repo.refs[ref])
                    tagged_commits_on_head = [c.commit.id for c in commits_on_head if c.commit.id in tags_lookup]

                    # Always yield the tip of the branch (HEAD), i.e., the latest commit on the branch.
                    yield tags_lookup.get(ref_commit, ref)

                    # Yield all other tagged commits on the branch:
                    for commit in tagged_commits_on_head:
                        if commit != ref_commit:
                            yield tags_lookup[commit]

                # The release line is a tag.
                elif ref.startswith(b'refs/tags/'):
                    yield ref

        def _resolve_commit(self, rev):
            """Map a revision to a commit."""
            if len(rev) in (20, 40) and rev in self._repo.object_store:
                return rev

            return self._repo.get_peeled(rev)

        def resolve_revision(self, commit):
            """Map a given commit to a named version (branch/tag) if possible."""
            lookup = {self._resolve_commit(version): version for version in self.find_versions()}
            return lookup.get(commit, commit)

        def _on_release_line(self, rev):
            """Determine whether the release line contains the provided version."""
            return rev in [self._resolve_commit(version) for version in self.find_versions()]

        def current_revision(self):
            """Return the version currently installed on the release line.

            Returns None if the current revision is not on this release line.
            """
            current_commit = self._repo.head()
            on_release_line = self._on_release_line(current_commit)
            if on_release_line:
                return self.resolve_revision(current_commit)

            return None  # current revision not on the release line

        def is_branch(self):
            """Return True if release line is a branch."""
            return f'refs/remotes/origin/{self.line}'.encode() in self._repo.refs

    def __init__(self, name, app_data, aiidalab_apps_path, watch=True):
        super().__init__()

        if app_data is None:
            self._registry_data = None
            self._release_line = None
        else:
            self._registry_data = self.AppRegistryData(**app_data)
            parsed_url = urlsplit(self._registry_data.git_url)
            self._release_line = self._GitReleaseLine(self, parsed_url.fragment or AIIDALAB_DEFAULT_GIT_BRANCH)

        self.name = name
        self.path = os.path.join(aiidalab_apps_path, self.name)
        self.refresh_async()

        if watch:
            self._watch = AiidaLabAppWatch(self)
            self._watch.start()
        else:
            self._watch = None

    def __repr__(self):
        app_data_argument = None if self._registry_data is None else asdict(self._registry_data)
        return (f"AiidaLabApp(name={self.name!r}, app_data={app_data_argument!r}, "
                f"aiidalab_apps_path={os.path.dirname(self.path)!r})")

    @traitlets.default('detached')
    def _default_detached(self):
        """Provide default value for detached traitlet."""
        if self.is_installed():
            modified = self._repo.dirty()
            if self._release_line is not None:
                revision = self._release_line.current_revision()
                return revision is not None and not modified
            return True
        return None

    @traitlets.default('busy')
    def _default_busy(self):  # pylint: disable=no-self-use
        return False

    @contextmanager
    def _show_busy(self):
        """Apply this decorator to indicate that the app is busy during execution."""
        self.set_trait('busy', True)
        try:
            yield
        finally:
            self.set_trait('busy', False)

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
        assert self._registry_data is not None
        assert self._release_line is not None

        with self._show_busy():
            if version is None:
                version = f'git:{self._release_line.line}'

            if not re.fullmatch(r'git:((?P<commit>([0-9a-fA-F]{20}){1,2})|(?P<short_ref>.+))', version):
                raise ValueError(f"Unknown version format: '{version}'")

            if not os.path.isdir(self.path):  # clone first
                url = urldefrag(self._registry_data.git_url).url
                check_output(['git', 'clone', url, self.path], cwd=os.path.dirname(self.path), stderr=STDOUT)

            # Switch to desired version
            rev = self._release_line.resolve_revision(re.sub('git:', '', version).encode())
            if self._release_line.is_branch():
                branch = self._release_line.line
                check_output(['git', 'checkout', '--force', branch], cwd=self.path, stderr=STDOUT)
                check_output(['git', 'reset', '--hard', rev], cwd=self.path, stderr=STDOUT)
            else:
                check_output(['git', 'checkout', '--force', rev], cwd=self.path, stderr=STDOUT)

            self.refresh()
            return 'git:' + rev.decode()

    def update_app(self, _=None):
        """Perform app update."""
        assert self._registry_data is not None
        try:
            if self._remote_update_available():
                self._fetch_from_remote()
        except AppRemoteUpdateError:
            pass
        available_versions = list(self._available_versions())
        self.install_app(version=available_versions[0])

    def uninstall_app(self, _=None):
        """Perfrom app uninstall."""
        # Perform uninstall process.
        with self._show_busy():
            try:
                shutil.rmtree(self.path)
            except FileNotFoundError:
                raise RuntimeError("App was already uninstalled!")
            self.refresh()

    def _remote_update_available(self):
        """Check whether there are more commits at the origin (based on the registry)."""
        error_message_prefix = "Unable to determine whether remote update is available: "

        try:  # Obtain reference to git repository.
            repo = self._repo
        except NotGitRepository as error:
            raise AppRemoteUpdateError(f"{error_message_prefix}{error}")

        try:  # Determine sha of remote-tracking branch from registry.
            branch = self._release_line.line
            branch_ref = 'refs/heads/' + branch
            local_remote_ref = 'refs/remotes/origin/' + branch
            remote_sha = self._registry_data.gitinfo[branch_ref]
        except AttributeError:
            raise AppRemoteUpdateError(f"{error_message_prefix}app is not registered")
        except KeyError:
            raise AppRemoteUpdateError(f"{error_message_prefix}no data about this release line in registry")

        try:  # Determine sha of remote-tracking branch from repository.
            local_remote_sha = repo.refs[local_remote_ref.encode()].decode()
        except KeyError:
            return False  # remote ref not found, release line likely not a branch

        return remote_sha != local_remote_sha

    def _fetch_from_remote(self):
        with self._show_busy():
            fetch(repo=self._repo, remote_location=urldefrag(self._registry_data.git_url).url)

    def check_for_updates(self):
        """Check whether there is an update available for the installed release line."""
        try:
            remote_update_available = self._remote_update_available()
        except AppRemoteUpdateError:
            self.set_trait('updates_available', None)
        else:
            available_versions = list(self._available_versions())
            on_release_line = self.installed_version in available_versions
            latest = self.installed_version == available_versions[0]
            self.set_trait('updates_available', remote_update_available or (on_release_line and not latest))

    def _available_versions(self):
        if self.is_installed() and self._release_line is not None:
            for version in self._release_line.find_versions():
                yield 'git:' + version.decode()

    def _installed_version(self):
        """Determine the currently installed version."""
        if self.is_installed():
            if self._has_git_repo():
                modified = self._repo.dirty()
                if not (self._release_line is None or modified):
                    revision = self._release_line.current_revision()
                    if revision is not None:
                        return f'git:{revision.decode()}'
            return AppVersion.UNKNOWN
        return AppVersion.NOT_INSTALLED

    @throttled(calls_per_second=1)
    def refresh(self):
        """Refresh app state."""
        with self._show_busy():
            with self.hold_trait_notifications():
                self.available_versions = list(self._available_versions())
                self.installed_version = self._installed_version()
                if self.is_installed() and self._has_git_repo():
                    self.installed_version = self._installed_version()
                    self.check_for_updates()
                    modified = self._repo.dirty()
                    self.set_trait('detached', self.installed_version is AppVersion.UNKNOWN or modified)
                else:
                    self.set_trait('updates_available', None)
                    self.set_trait('detached', None)

    def refresh_async(self):
        """Asynchronized (non-blocking) refresh of the app state."""
        refresh_thread = Thread(target=self.refresh)
        refresh_thread.start()

    @property
    def metadata(self):
        """Return metadata dictionary. Give the priority to the local copy (better for the developers)."""
        if self.is_installed():
            try:
                with open(os.path.join(self.path, 'metadata.json')) as json_file:
                    return json.load(json_file)
            except IOError:
                return dict()
        elif self._registry_data is not None and self._registry_data.metainfo:
            return dict(self._registry_data.metainfo)
        else:
            raise RuntimeError(
                f"Requested app '{self.name}' is not installed and is also not registered on the app registry.")

    def _get_from_metadata(self, what):
        """Get information from metadata."""

        try:
            return "{}".format(self.metadata[what])
        except KeyError:
            if not os.path.isfile(os.path.join(self.path, 'metadata.json')):
                return '({}) metadata.json file is not present'.format(what)
            return 'the field "{}" is not present in metadata.json file'.format(what)

    @property
    def authors(self):
        return self._get_from_metadata('authors')

    @property
    def description(self):
        return self._get_from_metadata('description')

    @property
    def title(self):
        return self._get_from_metadata('title')

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
