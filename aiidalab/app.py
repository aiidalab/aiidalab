# -*- coding: utf-8 -*-
"""Module to manage AiiDAlab apps."""

import re
import os
import shutil
import json
import errno
import logging
from collections import defaultdict
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
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet, InvalidSpecifier
from packaging.version import parse
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from .config import AIIDALAB_DEFAULT_GIT_BRANCH
from .git_util import GitManagedAppRepo as Repo
from .utils import throttled
from .utils import find_installed_packages


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
    compatible = traitlets.Bool(readonly=True, allow_none=True)

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

        @staticmethod
        def _get_sha(obj):
            """Determine the SHA for a given commit object."""
            assert isinstance(obj, (Tag, Commit))
            return obj.object[1] if isinstance(obj, Tag) else obj.id

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

                # The release line is a head (branch).
                if ref.startswith(b'refs/remotes/'):
                    ref_commit = self._repo.get_peeled(ref)
                    all_tags = {ref for ref in self._repo.get_refs() if ref.startswith(b'refs/tags')}

                    # Create lookup table from commit -> tags
                    tags_lookup = defaultdict(set)
                    for tag in all_tags:
                        tags_lookup[self._get_sha(self._repo[tag])].add(tag)

                    # Determine all the tagged commits on the branch (HEAD)
                    commits_on_head = self._repo.get_walker(self._repo.refs[ref])
                    tagged_commits_on_head = [c.commit.id for c in commits_on_head if c.commit.id in tags_lookup]

                    # Always yield the tip of the branch (HEAD), i.e., the latest commit on the branch.
                    yield from tags_lookup.get(ref_commit, (ref,))

                    # Yield all other tagged commits on the branch:
                    for commit in tagged_commits_on_head:
                        if commit != ref_commit:
                            yield from tags_lookup[commit]

                # The release line is a tag.
                elif ref.startswith(b'refs/tags/'):
                    yield ref

        def _resolve_commit(self, rev):
            """Map a revision to a commit."""
            if len(rev) in (20, 40) and rev in self._repo.object_store:
                return rev

            return self._get_sha(self._repo[rev])

        def resolve_revision(self, commit):
            """Map a given commit to a named version (branch/tag) if possible."""
            lookup = defaultdict(set)
            for version in self.find_versions():
                lookup[self._resolve_commit(version)].add(version)
            return lookup.get(commit, {commit})

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
                return list(sorted(self.resolve_revision(current_commit)))[0]

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

    def _install_app_version(self, version):
        """Install a specific app version."""
        assert self._registry_data is not None
        assert self._release_line is not None

        with self._show_busy():

            if not re.fullmatch(r'git:((?P<commit>([0-9a-fA-F]{20}){1,2})|(?P<short_ref>.+))', version):
                raise ValueError(f"Unknown version format: '{version}'")

            if not os.path.isdir(self.path):  # clone first
                url = urldefrag(self._registry_data.git_url).url
                check_output(['git', 'clone', url, self.path], cwd=os.path.dirname(self.path), stderr=STDOUT)

            # Switch to desired version
            rev = self._release_line.resolve_revision(re.sub('git:', '', version)).pop().encode()
            if self._release_line.is_branch():
                branch = self._release_line.line
                check_output(['git', 'checkout', '--force', branch], cwd=self.path, stderr=STDOUT)
                check_output(['git', 'reset', '--hard', rev], cwd=self.path, stderr=STDOUT)
            else:
                check_output(['git', 'checkout', '--force', rev], cwd=self.path, stderr=STDOUT)

            self.refresh()
            return 'git:' + rev.decode()

    def install_app(self, version=None):
        """Installing the app."""
        if version is None:  # initial installation
            version = self._install_app_version(f'git:{self._release_line.line}')

            # switch to compatible version if possible
            available_versions = list(self._available_versions())
            if available_versions:
                return self._install_app_version(version=available_versions[0])

            return version

        # app already installed, just switch version
        return self._install_app_version(version=version)

    def update_app(self, _=None):
        """Perform app update."""
        assert self._registry_data is not None
        try:
            if self._remote_update_available():
                self._fetch_from_remote()
        except AppRemoteUpdateError:
            pass
        available_versions = list(self._available_versions())
        return self.install_app(version=available_versions[0])

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
            assert not self.detached
            remote_update_available = self._remote_update_available()
        except (AssertionError, AppRemoteUpdateError):
            self.set_trait('updates_available', None)
        else:
            available_versions = list(self._available_versions())
            if len(available_versions) > 0:
                local_update_available = self.installed_version != available_versions[0]
            else:
                local_update_available = None
            self.set_trait('updates_available', remote_update_available or local_update_available)

    def _available_versions(self):
        """Return all available and compatible versions."""
        if self.is_installed() and self._release_line is not None:
            versions = ['git:' + ref.decode() for ref in self._release_line.find_versions()]
        elif self._registry_data is not None:

            def is_tag(ref):
                return ref.startswith('refs/tags') and '^{}' not in ref

            def sort_key(ref):
                version = parse(ref[len('refs/tags/'):])
                return (not is_tag(ref), version, ref)

            versions = [
                'git:' + ref
                for ref in reversed(sorted(self._registry_data.gitinfo, key=sort_key))
                if is_tag(ref) or ref == f'refs/heads/{self._release_line.line}'
            ]
        else:
            versions = []

        for version in versions:
            if self._is_compatible(version):
                yield version

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

    @traitlets.default('compatible')
    def _default_compatible(self):  # pylint: disable=no-self-use
        return None

    def _is_compatible(self, app_version=None):
        """Determine whether the currently installed version is compatible."""
        if app_version is None:
            app_version = self.installed_version

        def get_version_identifier(version):
            "Get version identifier from version (e.g. git:refs/tags/v1.0.0 -> v1.0.0)."
            if version.startswith('git:refs/tags/'):
                return version[len('git:refs/tags/'):]
            if version.startswith('git:refs/heads/'):
                return version[len('git:refs/heads/'):]
            if version.startswith('git:refs/remotes/'):  # remote branch
                return re.sub(r'git:refs\/remotes\/(.+?)\/', '', version)
            return version

        class RegexMatchSpecifierSet:
            """Interpret 'invalid' specifier sets as regular expression pattern."""

            def __init__(self, specifiers=''):
                self.specifiers = specifiers

            def __contains__(self, version):
                return re.match(self.specifiers, version) is not None

        def specifier_set(specifiers=''):
            try:
                return SpecifierSet(specifiers=specifiers, prereleases=True)
            except InvalidSpecifier:
                return RegexMatchSpecifierSet(specifiers=specifiers)

        def fulfilled(requirements, packages):
            for requirement in requirements:
                if not any(package.fulfills(requirement) for package in packages):
                    logging.debug(f"{self.name}({app_version}): missing requirement '{requirement}'")  # pylint: disable=logging-fstring-interpolation
                    return False
            return True

        # Retrieve and convert the compatibility map from the app metadata.

        try:
            compat_map = self.metadata.get('requires', {'': []})
            compat_map = {
                specifier_set(app_version): [Requirement(r) for r in reqs] for app_version, reqs in compat_map.items()
            }
        except RuntimeError:  # not registered
            return None  # unable to determine compatibility
        else:
            if isinstance(app_version, str):
                app_version_identifier = get_version_identifier(app_version)
                matching_specs = [app_spec for app_spec in compat_map if app_version_identifier in app_spec]

                packages = find_installed_packages()
                return any(fulfilled(compat_map[spec], packages) for spec in matching_specs)

        return None  # compatibility indetermined since the app is not installed

    @throttled(calls_per_second=1)
    def refresh(self):
        """Refresh app state."""
        with self._show_busy():
            with self.hold_trait_notifications():
                self.available_versions = list(self._available_versions())
                self.installed_version = self._installed_version()
                self.set_trait('compatible', self._is_compatible())
                if self.is_installed() and self._has_git_repo():
                    self.installed_version = self._installed_version()
                    modified = self._repo.dirty()
                    self.set_trait('detached', self.installed_version is AppVersion.UNKNOWN or modified)
                    self.check_for_updates()
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
        if self._registry_data is not None and self._registry_data.metainfo:
            return dict(self._registry_data.metainfo)

        if self.is_installed():
            try:
                with open(os.path.join(self.path, 'metadata.json')) as json_file:
                    return json.load(json_file)
            except IOError:
                return dict()

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
