# -*- coding: utf-8 -*-
"""Module to manage AiiDA lab apps."""

import re
import os
import shutil
import json
from contextlib import contextmanager
from time import sleep
from threading import Thread
from subprocess import check_output, STDOUT, CalledProcessError

import requests
import traitlets
import ipywidgets as ipw
from dulwich.porcelain import fetch
from dulwich.errors import NotGitRepository
from watchdog.observers import Observer
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
    available_versions = traitlets.Dict(traitlets.Unicode())

    def __init__(self, *args, **kwargs):
        style = {'description_width': '100px'}
        self.release_line = ipw.Dropdown(
            description='Release line',
            style=style,
        )
        self.installed_version = ipw.Text(
            description='Installed version',
            disabled=True,
            style=style,
        )
        self.info = StatusHTML('')

        super().__init__(
            children=[self.release_line, self.installed_version, self.info],
            layout={'min_width': '300px'},
            *args,
            **kwargs,
        )

    @traitlets.observe('disabled')
    def _observe_disabled(self, change):
        self.release_line.disabled = change['new']


class AiidaLabApp(traitlets.HasTraits):
    """Manage installation status of an AiiDA lab app.

    Arguments:

        name (str):
            Name of the Aiida lab app.
        app_data (dict):
            Dictionary containing the app metadata.
        aiidalab_apps_path (str):
            Path to directory at which the app is expected to be installed.
    """

    path = traitlets.Unicode(allow_none=True, readonly=True)
    install_info = traitlets.Unicode()

    available_release_lines = traitlets.Set(traitlets.Unicode)
    installed_release_line = traitlets.Unicode(allow_none=True)
    installed_version = traitlets.Unicode(allow_none=True)
    updates_available = traitlets.Bool(readonly=True, allow_none=True)

    busy = traitlets.Bool(readonly=True)
    modified = traitlets.Bool(readonly=True, allow_none=True)

    class AppPathFileSystemEventHandler(FileSystemEventHandler):
        """Internal event handeler for app path file system events."""

        def __init__(self, app):
            self.app = app

        def on_any_event(self, event):
            """Refresh app for any event."""
            self.app.refresh_async()

    def __init__(self, name, app_data, aiidalab_apps_path):
        super().__init__()

        if app_data is not None:
            self._git_url = app_data['git_url']
            self._meta_url = app_data['meta_url']
            self._git_remote_refs = app_data['gitinfo']
            self.categories = app_data['categories']
            self._meta_info = app_data['metainfo']
        else:
            self._git_url = None
            self._meta_url = None
            self._git_remote_refs = {}
            self.categories = None
            self._meta_info = None

        self._observer = None
        self._check_install_status_changed_thread = None

        self.name = name
        self.path = os.path.join(aiidalab_apps_path, self.name)
        self.refresh_async()
        self._watch_repository()

    @traitlets.default('modified')
    def _default_modified(self):
        if self.is_installed():
            return self._repo.dirty()
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

    def _watch_repository(self):
        """Watch the app repository for file system events.

        The app state is refreshed automatically for all events.
        """
        if self._observer is None and os.path.isdir(self.path):
            event_handler = self.AppPathFileSystemEventHandler(self)

            self._observer = Observer()
            self._observer.schedule(event_handler, self.path, recursive=True)
            self._observer.start()

        if self._check_install_status_changed_thread is None:

            def check_install_status_changed():
                installed = self.is_installed()
                while not self._check_install_status_changed_thread.stop_flag:
                    if installed != self.is_installed():
                        installed = self.is_installed()
                        self.refresh()
                    sleep(1)

            self._check_install_status_changed_thread = Thread(target=check_install_status_changed)
            self._check_install_status_changed_thread.stop_flag = False
            self._check_install_status_changed_thread.start()

    def _stop_watch_repository(self, timeout=None):
        """Stop watching the app repository for file system events."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=timeout)
            if not self._observer.isAlive():
                self._observer = None

        if self._check_install_status_changed_thread is not None:
            self._check_install_status_changed_thread.stop_flag = True
            self._check_install_status_changed_thread.join(timeout=timeout)
            if not self._check_install_status_changed_thread.is_alive():
                self._check_install_status_changed_thread = None

    def __del__(self):  # pylint: disable=missing-docstring
        self._stop_watch_repository(1)

    def in_category(self, category):
        # One should test what happens if the category won't be defined.
        return category in self.categories

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
        assert self._git_url is not None
        if version is None:
            version = 'git:refs/heads/' + AIIDALAB_DEFAULT_GIT_BRANCH

        with self._show_busy():
            assert version.startswith('git:refs/heads/')
            branch = re.sub(r'git:refs\/heads\/', '', version)

            if not os.path.isdir(self.path):  # clone first
                check_output(['git', 'clone', '--branch', branch, self._git_url, self.path],
                             cwd=os.path.dirname(self.path),
                             stderr=STDOUT)

            check_output(['git', 'checkout', '-f', branch], cwd=self.path, stderr=STDOUT)
            self.refresh()
            self._watch_repository()
            return branch

    def update_app(self, _=None):
        """Perform app update."""
        assert self._git_url is not None
        with self._show_busy():
            fetch(repo=self._repo, remote_location=self._git_url)
            tracked_branch = self._repo.get_tracked_branch()
            check_output(['git', 'reset', '--hard', tracked_branch], cwd=self.path, stderr=STDOUT)
            self.refresh_async()

    def uninstall_app(self, _=None):
        """Perfrom app uninstall."""
        # Perform uninstall process.
        with self._show_busy():
            self._stop_watch_repository()
            try:
                shutil.rmtree(self.path)
            except FileNotFoundError:
                raise RuntimeError("App was already uninstalled!")
            self.refresh()
            self._watch_repository()

    def check_for_updates(self):
        """Check whether there is an update available for the installed release line."""
        try:
            assert self._git_url is not None
            branch_ref = 'refs/heads/' + self._repo.branch().decode()
            assert self._repo.get_tracked_branch() is not None
            remote_update_available = self._git_remote_refs.get(branch_ref) != self._repo.head().decode()
            self.set_trait('updates_available', remote_update_available or self._repo.update_available())
        except (AssertionError, RuntimeError):
            self.set_trait('updates_available', None)

    def _available_release_lines(self):
        """"Return all available release lines (local and remote)."""
        for branch in self._repo.list_branches():
            yield 'git:refs/heads/' + branch.decode()
        for ref in self._git_remote_refs:
            if ref.startswith('refs/heads/'):
                yield 'git:' + ref

    @throttled(calls_per_second=1)
    def refresh(self):
        """Refresh app state."""
        with self._show_busy():
            with self.hold_trait_notifications():
                if self.is_installed() and self._has_git_repo():
                    self.available_release_lines = set(self._available_release_lines())
                    try:
                        self.installed_release_line = 'git:refs/heads/' + self._repo.branch().decode()
                    except RuntimeError:
                        self.installed_release_line = None
                    self.installed_version = self._repo.head()
                    self.check_for_updates()
                    self.set_trait('modified', self._repo.dirty())
                else:
                    self.available_release_lines = set()
                    self.installed_release_line = None
                    self.installed_version = None
                    self.set_trait('updates_available', None)
                    self.set_trait('modified', None)

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
        elif self._meta_info is not None:
            return dict(self._meta_info)
        elif self._meta_url is None:
            raise RuntimeError(
                f"Requested app '{self.name}' is not installed and is also not registered on the app registry.")
        else:
            return requests.get(self._meta_url).json()

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
        return self._git_url

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
            html_link = os.path.splitext(self._git_url)[0]

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

        self.modifications_indicator = ipw.HTML()
        self.modifications_ignore = ipw.Checkbox(description="Ignore")
        self.modifications_ignore.observe(self._refresh_widget_state)

        self.spinner = Spinner("color:#337ab7;font-size:1em;")
        ipw.dlink((self.app, 'busy'), (self.spinner, 'enabled'))

        children = [
            ipw.HBox([app.logo, body]),
            ipw.HBox([self.uninstall_button, self.install_button, self.update_button, self.spinner]),
            ipw.HBox([self.install_info]),
            ipw.HBox([self.modifications_indicator, self.modifications_ignore]),
        ]

        self.version_selector = VersionSelectorWidget()
        ipw.dlink((self.app, 'available_release_lines'), (self.version_selector.release_line, 'options'),
                  transform=lambda release_lines: [(self._format_release_line_name(release_line), release_line)
                                                   for release_line in release_lines])
        ipw.dlink((self.app, 'installed_release_line'), (self.version_selector.release_line, 'value'),
                  transform=lambda value: value if value else None)
        ipw.dlink((self.app, 'installed_version'), (self.version_selector.installed_version, 'value'),
                  transform=lambda version: '' if version is None else version)
        self.version_selector.release_line.observe(self._refresh_widget_state, names=['value'])
        ipw.dlink((self.app, 'busy'), (self.version_selector, 'disabled'))
        self.version_selector.layout.visibility = 'visible' if with_version_selector else 'hidden'
        self.version_selector.disabled = True
        children.insert(1, self.version_selector)

        super().__init__(children=children)

        self.app.observe(self._refresh_widget_state)
        self.app.refresh_async()  # init all widgets

    @staticmethod
    def _format_release_line_name(release_line):
        """Return a human-readable version of a release line name."""
        if re.match(r'git:refs\/heads\/.*', release_line):
            return re.sub(r'git:refs\/heads\/', '', release_line)
        return release_line

    def _refresh_widget_state(self, _=None):
        """Refresh the widget to reflect the current state of the app."""
        with self.hold_trait_notifications():
            # Collect information about app state.
            busy = self.app.busy
            modified = self.app.modified
            override = modified and self.modifications_ignore.value
            blocked = modified and not self.modifications_ignore.value

            # Prepare warning icons and messages depending on whether we override or not.
            # These messages and icons are only shown if needed.
            warn_or_ban_icon = "ban" if blocked else "warning"
            if override:
                tooltip = "Operation will lead to potential loss of local modifications!"
            else:
                tooltip = "Operation blocked due to local modifications."

            # Determine whether we can install, updated, and uninstall.
            requested_release_line = self.version_selector.release_line.value
            switch_release_line = requested_release_line is not None \
                and requested_release_line != self.app.installed_release_line
            can_install = switch_release_line or not self.app.is_installed()
            can_uninstall = self.app.is_installed()
            try:
                can_update = self.app.updates_available and not can_install
            except RuntimeError:
                can_update = None

            # Update the install button state.
            self.install_button.disabled = busy or blocked or not can_install
            self.install_button.button_style = 'info' if can_install else ''
            self.install_button.icon = '' if can_install and not modified else warn_or_ban_icon if can_install else ''
            self.install_button.tooltip = '' if can_install and not modified else tooltip if can_install else ''
            if switch_release_line:
                self.install_button.description = f'Install ({self._format_release_line_name(requested_release_line)})'
            else:
                self.install_button.description = 'Install'

            # Update the uninstall button state.
            self.uninstall_button.disabled = busy or blocked or not can_uninstall
            self.uninstall_button.button_style = 'danger' if can_uninstall else ''
            self.uninstall_button.icon = \
                "" if can_uninstall and not modified else warn_or_ban_icon if can_uninstall else ""
            self.uninstall_button.tooltip = '' if can_uninstall and not modified else tooltip if can_uninstall else ''

            # Update the update button state.
            self.update_button.disabled = busy or blocked or not can_update
            if self.app.is_installed() and can_update is None:
                self.update_button.icon = 'warning'
                self.update_button.tooltip = 'Unable to determine availability of updates.'
            else:
                self.update_button.icon = \
                    "circle-up" if can_update and not modified else warn_or_ban_icon if can_update else ""
                self.update_button.button_style = 'success' if can_update else ''
                self.update_button.tooltip = '' if can_update and not modified else tooltip if can_update else ''

            # Indicate whether there are local modifications and present option for user override.
            self.modifications_indicator.value = \
                f'<i class="fa fa-{warn_or_ban_icon}"> There are local modifications.' if modified else ''
            self.modifications_ignore.layout.visibility = 'visible' if modified else 'hidden'

    def _show_msg_success(self, msg):
        """Show a message indicating successful execution of a requested operation."""
        self.install_info.show_temporary_message(HTML_MSG_SUCCESS.format(msg))

    def _show_msg_failure(self, msg):
        """Show a message indicating failure to execute a requested operation."""
        self.install_info.show_temporary_message(HTML_MSG_FAILURE.format(msg))

    def _check_modified_state(self):
        """Check whether there are local modifications to the app that prevent any install etc. operations."""
        self.app.refresh()
        self._refresh_widget_state()
        blocked = self.app.modified and not self.modifications_ignore.value
        if blocked:
            raise RuntimeError("Unable to perform operation, there are local modifications to the app repository.")

    def _install_version(self, _):
        """Attempt to install the a specific version of the app."""
        release_line = self.version_selector.release_line.value
        try:
            self._check_modified_state()
            release_line = self.app.install_app(release_line)  # argument may be None
        except (AssertionError, RuntimeError, CalledProcessError) as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success(f"Installed app ({self._format_release_line_name(release_line)}).")

    def _update_app(self, _):
        """Attempt to uninstall the app."""
        try:
            self._check_modified_state()
            self.app.update_app()
        except (AssertionError, RuntimeError, CalledProcessError) as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success("Updated app.")

    def _uninstall_app(self, _):
        """Attempt to uninstall the app."""
        try:
            self._check_modified_state()
            self.app.uninstall_app()
        except RuntimeError as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success("Uninstalled app.")
