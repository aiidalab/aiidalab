# -*- coding: utf-8 -*-
"""Module to manage AiiDA lab apps."""

import re
import os
import shutil
import json
from subprocess import check_output, STDOUT

import requests
import traitlets
import ipywidgets as ipw
from dulwich.objects import Commit, Tag
from dulwich.errors import NotGitRepository
from jinja2 import Template

from .widgets import StatusHTML
from .git_util import GitManagedAppRepo as Repo

HTML_MSG_SUCCESS = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
{}"""

HTML_MSG_FAILURE = """"<i class="fa fa-times" style="color:red;font-size:4em;" ></i>
{}"""


class AppNotInstalledException(Exception):
    pass


class VersionSelectorWidget(ipw.VBox):
    """Class to choose app's version."""

    available_versions = traitlets.Dict(traitlets.Unicode())

    def __init__(self):
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
        )


class AiidaLabApp(traitlets.HasTraits):
    """Class to manage AiiDA lab app."""

    path = traitlets.Unicode(allow_none=True, readonly=True)
    install_info = traitlets.Unicode()

    available_release_lines = traitlets.Set(traitlets.Unicode)
    installed_release_line = traitlets.Unicode(allow_none=True)
    installed_version = traitlets.Unicode(allow_none=True)
    updates_available = traitlets.Bool(readonly=True, allow_none=True)

    modified = traitlets.Bool(readonly=True, allow_none=True)

    def __init__(self, name, app_data, aiidalab_apps):
        super().__init__()

        if app_data is not None:
            self._git_url = app_data['git_url']
            self._meta_url = app_data['meta_url']
            self._git_remote_refs = app_data['gitinfo']
            self.categories = app_data['categories']
        else:
            self._git_url = None
            self._git_remote_refs = {}

        self.aiidalab_apps = aiidalab_apps
        self.name = name
        self.path = os.path.join(self.aiidalab_apps, self.name)
        self._refresh_app_state()

    @traitlets.default('modified')
    def _default_modified(self):
        if self.is_installed():
            return self._repo.dirty()
        return None

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

    def install_app(self, version):
        """Installing the app."""
        assert version.startswith('git:refs/heads/')
        branch = re.sub(r'git:refs\/heads\/', '', version)
        check_output(['git', 'checkout', branch], cwd=self.path, stderr=STDOUT)
        self._refresh_app_state()

    def update_app(self, _=None):
        """Perform app update."""
        tracked_branch = self._repo.get_tracked_branch()
        check_output(['git', 'reset', '--hard', tracked_branch], cwd=self.path, stderr=STDOUT)
        self._refresh_app_state()

    def uninstall_app(self, _=None):
        """Perfrom app uninstall."""
        # Perform uninstall process.
        shutil.rmtree(self.path)
        self._refresh_app_state()

    @property
    def _refs_dict(self):
        """Returns a dictionary of references: branch names, tags."""
        refs = dict()
        for key, value in self._repo.get_refs().items():
            if key.endswith(b'HEAD') or key.startswith(b'refs/heads/'):
                continue
            obj = self._repo.get_object(value)
            if isinstance(obj, Tag):
                refs[key] = obj.object[1]
            elif isinstance(obj, Commit):
                refs[key] = value
        return refs

    def update_available(self):
        """Check whether there is an update available for the installed release line."""
        return self._repo.update_available()

    def _installed_version(self):
        if self.is_installed():
            return self._repo.head()
        return None

    def _refresh_app_state(self):
        """Refresh version."""
        with self.hold_trait_notifications():
            if self.is_installed() and self._has_git_repo():
                self.available_release_lines = \
                    {'git:refs/heads/' + branch.decode() for branch in self._repo.list_branches()}
                try:
                    self.installed_release_line = 'git:refs/heads/' + self._repo.branch().decode()
                except RuntimeError:
                    self.installed_release_line = None
                self.installed_version = self._repo.head()
                try:
                    self.set_trait('updates_available', self._repo.update_available())
                except RuntimeError:
                    self.set_trait('updates_available', None)
                self.set_trait('modified', self._repo.dirty())
            else:
                self.available_release_lines = set()
                self.installed_release_line = None
                self.installed_version = None
                self.set_trait('updates_available', None)
                self.set_trait('modified', None)

    @property
    def metadata(self):
        """Return metadata dictionary. Give the priority to the local copy (better for the developers)."""
        if self.is_installed():
            try:
                with open(os.path.join(self.path, 'metadata.json')) as json_file:
                    return json.load(json_file)
            except IOError:
                return dict()
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
        """"Display widget to manage the app."""
        if self._has_git_repo():
            widget = AppManagerWidget(self, with_version_selector=True)
        else:
            widget = ipw.HTML("""<center><h1>Enable <i class="fa fa-git"></i> first!</h1></center>""")
        return widget


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
        self.install_button = ipw.Button(description='Install')
        self.install_button.on_click(self._install_version)

        self.uninstall_button = ipw.Button(description='Uninstall')
        self.uninstall_button.on_click(self._uninstall_app)

        self.update_button = ipw.Button(description='Update')
        self.update_button.on_click(self._update_app)
        self.update_button.button_style = 'success'

        self.modifications_indicator = ipw.HTML()
        self.modifications_ignore = ipw.Checkbox(description="Ignore")

        children = [
            ipw.HBox([app.logo, body]),
            ipw.HBox([self.uninstall_button, self.install_button, self.update_button]),
            ipw.HBox([self.install_info]),
            ipw.HBox([self.modifications_indicator, self.modifications_ignore]),
        ]

        self.version_selector = VersionSelectorWidget()
        ipw.dlink((self.app, 'available_release_lines'), (self.version_selector.release_line, 'options'),
                  transform=lambda release_lines: [(self._format_release_line_name(release_line), release_line)
                                                   for release_line in release_lines])
        ipw.dlink((self.app, 'installed_release_line'), (self.version_selector.release_line, 'value'))
        ipw.dlink((self.app, 'installed_version'), (self.version_selector.installed_version, 'value'),
                  transform=lambda version: '' if version is None else version)
        self.version_selector.release_line.observe(self._refresh_widget_state, names=['value'])
        children.insert(1, self.version_selector)
        self.version_selector.layout.visibility = 'visible' if with_version_selector else 'hidden'

        self._refresh_widget_state()  # init all widgets
        self.app.observe(self._refresh_widget_state)
        self.modifications_ignore.observe(self._refresh_widget_state)

        super().__init__(children=children)

    @staticmethod
    def _format_release_line_name(release_line):
        """Return a human-readable version of a release line name."""
        if re.match(r'git:refs\/heads\/.*', release_line):
            return re.sub(r'git:refs\/heads\/', '', release_line)
        return release_line

    def _refresh_widget_state(self, _=None):
        """Refresh the widget to reflect the current state of the app."""
        modified = self.app.modified
        blocked = modified and not self.modifications_ignore.value

        warn_or_ban_icon = ("warning" if modified and self.modifications_ignore.value else "ban") if modified else ""

        can_install = self.version_selector.release_line.value != self.app.installed_release_line and not blocked
        can_uninstall = self.app.is_installed() and not blocked
        try:
            can_update = self.app.updates_available and not can_install
        except RuntimeError:
            can_update = False

        self.install_button.disabled = blocked or not can_install
        self.install_button.button_style = 'info' if can_install else ''
        self.install_button.icon = "" if can_install and not modified else warn_or_ban_icon if can_install else ''

        self.uninstall_button.disabled = blocked or not can_uninstall
        self.uninstall_button.button_style = 'danger' if can_uninstall else ''
        self.uninstall_button.icon = "" if can_uninstall and not modified else warn_or_ban_icon if can_uninstall else ''

        self.update_button.disabled = blocked or not can_update
        self.update_button.icon = "circle-up" if can_update and not modified else warn_or_ban_icon if can_update else ''
        self.update_button.button_style = 'success' if can_update else ''
        self.update_button.tooltip = "Unable to update due to local modifications." if modified and blocked else ''

        self.modifications_indicator.value = \
            f'<i class="fa fa-{warn_or_ban_icon}"> There are local modifications.' if modified else ''
        self.modifications_ignore.layout.visibility = 'visible' if modified else 'hidden'

    def _show_msg_success(self, msg):
        """Show a message indicating successful execution of a requested operation."""
        self.install_info.show_temporary_message(HTML_MSG_SUCCESS.format(msg))

    def _show_msg_failure(self, msg):
        """Show a message indicating failure to execute a requested operation."""
        self.install_info.show_temporary_message(HTML_MSG_FAILURE.format(msg))

    def _install_version(self, _):
        """Attempt to install the a specific version of the app."""
        release_line = self.version_selector.release_line.value
        try:
            self.app.install_app(release_line)
        except RuntimeError as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success(f"Installed app ({self._format_release_line_name(release_line)}).")

    def _update_app(self, _):
        """Attempt to uninstall the app."""
        try:
            self.app.update_app()
        except RuntimeError as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success("Updated app.")

    def _uninstall_app(self, _):
        """Attempt to uninstall the app."""
        try:
            self.app.uninstall_app()
        except RuntimeError as error:
            self._show_msg_failure(str(error))
        else:
            self._show_msg_success("Uninstalled app.")
