# -*- coding: utf-8 -*-
"""Module to manage AiiDA lab apps."""

import re
import os
import shutil
import json
import errno
from contextlib import contextmanager
from enum import Enum, auto
from time import sleep
from threading import Thread
from subprocess import check_output, STDOUT, CalledProcessError
from dataclasses import dataclass, field, asdict

from typing import List, Dict

import traitlets
import ipywidgets as ipw
from dulwich.porcelain import fetch
from dulwich.errors import NotGitRepository
from dulwich.objects import Tag, Commit
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from jinja2 import Template

from .config import AIIDALAB_DEFAULT_GIT_BRANCH
from .widgets import StatusHTML, Spinner
from .git_util import GitManagedAppRepo as Repo
from .utils import throttled

HTML_MSG_SUCCESS = """<i class="fa fa-check" style="color:#337ab7;font-size:1em;" ></i>
{}"""

HTML_MSG_FAILURE = """<i class="fa fa-times" style="color:red;font-size:1em;" ></i>
{}"""


class AppNotInstalledException(Exception):
    pass


class VersionSelectorWidget(ipw.VBox):
    """Class to choose app's version."""

    disabled = traitlets.Bool()

    def __init__(self, *args, **kwargs):
        style = {'description_width': '100px'}
        self.version_to_install = ipw.Dropdown(
            description='Install version',
            disabled=True,
            style=style,
        )
        self.installed_version = ipw.Text(
            description='Installed version',
            disabled=True,
            style=style,
        )
        self.info = StatusHTML('')

        super().__init__(
            children=[self.installed_version, self.version_to_install, self.info],
            layout={'min_width': '300px'},
            *args,
            **kwargs,
        )

    @traitlets.observe('disabled')
    def _observe_disabled(self, change):
        self.version_to_install.disabled = change['new']


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
    AiiDA lab app. This is achieved by monitoring the app repository
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
    """Manage installation status of an AiiDA lab app.

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

        A release line is specified via the app url as the part after the '@'.

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
            # Check if short-ref is a head (branch):
            if f'refs/heads/{short_ref}'.encode() in self._repo.refs.allkeys():
                return f'refs/heads/{short_ref}'.encode()

            # Check if short-ref is a tag:
            if f'refs/tags/{short_ref}'.encode() in self._repo.refs.allkeys():
                return f'refs/tags/{short_ref}'.encode()

            # Check if short-ref is among the remote refs:
            for ref in self._repo.refs.allkeys():
                if re.match(r'refs\/remotes\/(.*)?\/' + short_ref, ref.decode()):
                    return ref

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
                if ref.startswith(b'refs/heads/'):
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

    def __init__(self, name, app_data, aiidalab_apps_path, watch=True):
        super().__init__()

        if app_data is None:
            self._registry_data = None
            self._release_line = None
        else:
            self._registry_data = self.AppRegistryData(**app_data)

            if '@' in self._registry_data.git_url:
                self._release_line = self._GitReleaseLine(self, self._registry_data.git_url.split('@')[1])
            else:
                self._release_line = self._GitReleaseLine(self, AIIDALAB_DEFAULT_GIT_BRANCH)

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
                url = self._registry_data.git_url.split('@')[0]

                check_output(['git', 'clone', url, self.path], cwd=os.path.dirname(self.path), stderr=STDOUT)

            # Switch to desired version
            rev = self._release_line.resolve_revision(re.sub('git:', '', version))
            check_output(['git', 'checkout', '--force', rev], cwd=self.path, stderr=STDOUT)

            self.refresh()
            return 'git:' + rev

    def update_app(self, _=None):
        """Perform app update."""
        assert self._registry_data is not None
        with self._show_busy():
            fetch(repo=self._repo, remote_location=self._registry_data.git_url.split('@')[0])
            tracked_branch = self._repo.get_tracked_branch()
            check_output(['git', 'reset', '--hard', tracked_branch], cwd=self.path, stderr=STDOUT)
            self.refresh_async()

    def uninstall_app(self, _=None):
        """Perfrom app uninstall."""
        # Perform uninstall process.
        with self._show_busy():
            try:
                shutil.rmtree(self.path)
            except FileNotFoundError:
                raise RuntimeError("App was already uninstalled!")
            self.refresh()

    def check_for_updates(self):
        """Check whether there is an update available for the installed release line."""
        try:
            assert self._registry_data is not None
            branch_ref = 'refs/heads/' + self._repo.branch().decode()
            assert self._repo.get_tracked_branch() is not None
            remote_ref = self._registry_data.gitinfo.get(branch_ref)
            remote_update_available = remote_ref is not None and remote_ref != self._repo.head().decode()
            self.set_trait('updates_available', remote_update_available or self._repo.update_available())
        except (AssertionError, RuntimeError):
            self.set_trait('updates_available', None)

    def _available_versions(self):
        if self.is_installed() and self._release_line is not None:
            for version in self._release_line.find_versions():
                yield 'git:' + version.decode()

    def _installed_version(self):
        """Determine the currently installed version."""
        if self.is_installed():
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
    def logo(self):
        """Return logo object. Give the priority to the local version"""

        # For some reason standard ipw.Image() app does not work properly.
        res = ipw.HTML('<img src="./aiidalab_logo_v4.svg">', layout={'width': '100px', 'height': '100px'})

        # Checking whether the 'logo' key is present in metadata dictionary.
        if 'logo' not in self.metadata:
            res.value = '<img src="./aiidalab_logo_v4.svg">'

        # If 'logo' key is present and the app is installed.
        elif self.is_installed():
            res.value = '<img src="{}">'.format(os.path.join('..', self.name, self.metadata['logo']))

        # If not installed, getting file from the remote git repository.
        else:
            # Remove .git if present.
            html_link = os.path.splitext(self._registry_data.git_url)[0]

            # We expect it to always be a git repository
            html_link += '/master/' + self.metadata['logo']
            if 'github.com' in html_link:
                html_link = html_link.replace('github.com', 'raw.githubusercontent.com')
                if html_link.endswith('.svg'):
                    html_link += '?sanitize=true'
            res.value = '<img src="{}">'.format(html_link)

        return res

    @property
    def _repo(self):
        """Returns Git repository."""
        if not self.is_installed():
            raise AppNotInstalledException("The app is not installed")
        return Repo(self.path)

    def render_app_manager_widget(self):
        """Display widget to manage the app."""
        try:
            return AppManagerWidget(self, with_version_selector=True)
        except Exception as error:  # pylint: disable=broad-except
            return ipw.HTML(
                '<div style="font-size: 30px; text-align:center;">'
                f'Unable to show app widget due to error: {error}'
                '</div>',
                layout={'width': '600px'})


class AppManagerWidget(ipw.VBox):
    """Widget for management of apps.

    Shows basic information about the app (description, authors, etc.) and provides
    an interface to install, uninstall, and update the application, as well as change
    versions if possible.
    """

    TEMPLATE = Template("""<b> <div style="font-size: 30px; text-align:center;">{{ app.title }}</div></b>
    <br>
    <b>Authors:</b> {{ app.authors }}
    <br>
    <b>Description:</b> {{ app.description }}
    {% if app.url %}
    <br>
    <b>URL:</b> <a href="{{ app.url }}">{{ app.url }}</a>
    {% endif %}""")

    def __init__(self, app, with_version_selector=False):
        self.app = app

        body = ipw.HTML(self.TEMPLATE.render(app=app))
        body.layout = {'width': '600px'}

        # Setup install_info
        self.install_info = StatusHTML()

        # Setup buttons
        self.install_button = ipw.Button(description='Install', disabled=True)
        self.install_button.on_click(self._install_version)

        self.uninstall_button = ipw.Button(description='Uninstall', disabled=True)
        self.uninstall_button.on_click(self._uninstall_app)

        self.update_button = ipw.Button(description='Update', disabled=True)
        self.update_button.on_click(self._update_app)

        self.detachment_indicator = ipw.HTML()
        self.detachment_ignore = ipw.Checkbox(description="Ignore")
        self.detachment_ignore.observe(self._refresh_widget_state)

        self.spinner = Spinner("color:#337ab7;font-size:1em;")
        ipw.dlink((self.app, 'busy'), (self.spinner, 'enabled'))

        children = [
            ipw.HBox([app.logo, body]),
            ipw.HBox([self.uninstall_button, self.install_button, self.update_button, self.spinner]),
            ipw.HBox([self.install_info]),
            ipw.HBox([self.detachment_indicator, self.detachment_ignore]),
        ]

        self.version_selector = VersionSelectorWidget()
        ipw.dlink((self.app, 'available_versions'), (self.version_selector.version_to_install, 'options'),
                  transform=lambda versions: [(self._formatted_version(version), version) for version in versions])
        ipw.dlink((self.app, 'installed_version'), (self.version_selector.installed_version, 'value'),
                  transform=self._formatted_version)
        self.version_selector.layout.visibility = 'visible' if with_version_selector else 'hidden'
        self.version_selector.disabled = True
        self.version_selector.version_to_install.observe(self._refresh_widget_state, 'value')
        children.insert(1, self.version_selector)

        super().__init__(children=children)

        self.app.observe(self._refresh_widget_state)
        self.app.refresh_async()  # init all widgets

    @staticmethod
    def _formatted_version(version):
        """Format the unambigious version identifiee to a human-friendly representation."""
        if version is AppVersion.NOT_INSTALLED:
            return '[not installed]'

        if version is AppVersion.UNKNOWN:
            return '[unknown version]'

        if not version:  # will be displayed during transition phases
            return '[n/a]'

        if version.startswith('git:refs/heads/'):  # branch
            return f"{version[len('git:refs/heads/'):]} (latest)"

        if version.startswith('git:refs/tags/'):  # tag
            return version[len('git:refs/tags/'):]

        if version.startswith('git:'):  # commit
            return version[4:4 + 8]

        raise ValueError("Unknown version format: '{}'".format(version))

    def _refresh_widget_state(self, _=None):
        """Refresh the widget to reflect the current state of the app."""
        with self.hold_trait_notifications():
            # Collect information about app state.
            installed = self.app.is_installed()
            installed_version = self.app.installed_version
            busy = self.app.busy
            detached = self.app.detached
            available_versions = self.app.available_versions

            override = detached and self.detachment_ignore.value
            blocked = detached and not self.detachment_ignore.value

            # Prepare warning icons and messages depending on whether we override or not.
            # These messages and icons are only shown if needed.
            warn_or_ban_icon = "ban" if blocked else "warning"
            if override:
                tooltip = "Operation will lead to potential loss of local modifications!"
            else:
                tooltip = "Operation blocked due to local modifications."

            # Determine whether we can install, updated, and uninstall.
            can_switch = installed_version != self.version_selector.version_to_install.value and available_versions
            can_install = can_switch or not installed
            can_uninstall = self.app.is_installed()
            try:
                can_update = self.app.updates_available and not can_install
            except RuntimeError:
                can_update = None

            # Update the install button state.
            self.install_button.disabled = busy or blocked or not can_install
            self.install_button.button_style = 'info' if can_install else ''
            self.install_button.icon = '' if can_install and not detached else warn_or_ban_icon if can_install else ''
            self.install_button.tooltip = '' if can_install and not detached else tooltip if can_install else ''
            self.install_button.description = 'Install' if not (installed and can_switch) \
                    else f'Install ({self._formatted_version(self.version_selector.version_to_install.value)})'

            # Update the uninstall button state.
            self.uninstall_button.disabled = busy or blocked or not can_uninstall
            self.uninstall_button.button_style = 'danger' if can_uninstall else ''
            self.uninstall_button.icon = \
                "" if can_uninstall and not detached else warn_or_ban_icon if can_uninstall else ""
            self.uninstall_button.tooltip = '' if can_uninstall and not detached else tooltip if can_uninstall else ''

            # Update the update button state.
            self.update_button.disabled = busy or blocked or not can_update
            if self.app.is_installed() and can_update is None:
                self.update_button.icon = 'warning'
                self.update_button.tooltip = 'Unable to determine availability of updates.'
            else:
                self.update_button.icon = \
                    "circle-up" if can_update and not detached else warn_or_ban_icon if can_update else ""
                self.update_button.button_style = 'success' if can_update else ''
                self.update_button.tooltip = '' if can_update and not detached else tooltip if can_update else ''

            # Update the version_selector widget state.
            more_than_one_version = len(self.version_selector.version_to_install.options) > 1
            self.version_selector.disabled = busy or blocked or not more_than_one_version

            # Indicate whether there are local modifications and present option for user override.
            if detached:
                self.detachment_indicator.value = \
                    f'<i class="fa fa-{warn_or_ban_icon}"> The app is modified or the installed version '\
                    'is not on the specified release line.'
            else:
                self.detachment_indicator.value = ''
            self.detachment_ignore.layout.visibility = 'visible' if detached else 'hidden'

    def _show_msg_success(self, msg):
        """Show a message indicating successful execution of a requested operation."""
        self.install_info.show_temporary_message(HTML_MSG_SUCCESS.format(msg))

    def _show_msg_failure(self, msg):
        """Show a message indicating failure to execute a requested operation."""
        self.install_info.show_temporary_message(HTML_MSG_FAILURE.format(msg))

    def _check_detached_state(self):
        """Check whether the app is in a detached state which would prevent any install or other operations."""
        self.app.refresh()
        self._refresh_widget_state()
        blocked = self.app.detached and not self.detachment_ignore.value
        if blocked:
            raise RuntimeError("Unable to perform operation, the app is in a detached state.")

    def _install_version(self, _=None):
        """Attempt to install the a specific version of the app."""
        version = self.version_selector.version_to_install.value  # can be None
        try:
            self._check_detached_state()
            version = self.app.install_app(version=version)  # argument may be None
        except (AssertionError, RuntimeError, CalledProcessError) as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success(f"Installed app ({self._formatted_version(version)}).")

    def _update_app(self, _):
        """Attempt to uninstall the app."""
        try:
            self._check_detached_state()
            self.app.update_app()
        except (AssertionError, RuntimeError, CalledProcessError) as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success("Updated app.")

    def _uninstall_app(self, _):
        """Attempt to uninstall the app."""
        try:
            self._check_detached_state()
            self.app.uninstall_app()
        except RuntimeError as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success("Uninstalled app.")
