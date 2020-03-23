# -*- coding: utf-8 -*-
"""Module to manage AiiDA lab apps."""

import re
import os
import shutil
import json
from time import sleep
from collections import OrderedDict
from subprocess import check_output, STDOUT
from contextlib import contextmanager

import requests
import traitlets
import ipywidgets as ipw
from dulwich.repo import Repo
from dulwich.objects import Commit, Tag
from dulwich.porcelain import status, clone, pull, fetch
from dulwich.errors import NotGitRepository
from cachetools.func import ttl_cache

from .config import AIIDALAB_DEFAULT_GIT_BRANCH
from .widgets import StatusHTML


HTML_MSG_SUCCESS = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
{}"""


HTML_MSG_FAIL = """"<i class="fa fa-times" style="color:red;font-size:4em;" ></i>
{}"""


class AppNotInstalledException(Exception):
    pass


class VersionSelectorWidget(ipw.VBox):
    """Class to choose app's version."""

    def __init__(self):
        self.selected = ipw.Select(
            options={},
            description='Select version',
            disabled=False,
            style={'description_width': 'initial'},
        )
        self.info = StatusHTML('')
        super().__init__([self.selected, self.info])


class AiidaLabApp(traitlets.HasTraits):  # pylint: disable=attribute-defined-outside-init,too-many-public-methods,too-many-instance-attributes
    """Class to manage AiiDA lab app."""

    path = traitlets.Unicode(allow_none=True)
    install_info = traitlets.Unicode()
    available_versions = traitlets.Dict(traitlets.Bytes)
    current_version = traitlets.Bytes(allow_none=True, readonly=True)
    updates_available = traitlets.Bool(allow_none=True)  # Use None if updates cannot be determined.

    def __init__(self, name, app_data, aiidalab_apps):  #, custom_update=False):
        super().__init__()

        if app_data is not None:
            self._git_url = app_data['git_url']
            self._meta_url = app_data['meta_url']
            self._git_remote_refs = app_data['gitinfo']
            self.categories = app_data['categories']
        else:
            self._git_url = None
            self._git_remote_refs = {}

        self._repo = None  # cached property

        self.aiidalab_apps = aiidalab_apps
        self.name = name
        self.path = os.path.join(self.aiidalab_apps, self.name)
        self._refresh_versions()

        self._change_version_mode = False

    def in_category(self, category):
        # One should test what happens if the category won't be defined.
        return category in self.categories

    def _get_appdir(self):  # deprecated
        return self.path

    def is_installed(self):
        """The app is installed if the corresponding folder is present."""
        return os.path.isdir(self._get_appdir())

    def has_git_repo(self):
        """Check if the app has a .git folder in it."""
        try:
            Repo(self._get_appdir())
            return True
        except NotGitRepository:
            return False

    def found_uncommited_modifications(self):
        """Check whether the git-supervised files were modified."""
        stts = status(self.repo)
        if stts.unstaged:
            return True
        for _, value in stts.staged.items():
            if value:
                return True
        return False

    def found_local_commits(self):
        """Check whether user did some work in the current branch.

        Here is the logic:
        - if it is a tag - return False
        - if it is a local branch - always return True (even though it
          can be that there are no local commits in it
        - if it is a remote branch - check properly."""

        # No local commits if it is a tag.
        if self.current_version.startswith(b'refs/tags/'):
            return False

        # Here it is assumed that if the branch is local, it has some stuff done in it,
        # therefore True is returned even though technically it is not always true.
        if self.current_version.startswith(b'refs/heads/'):
            return True

        # If it is a remote branch.
        if self.current_version.startswith(b'refs/remotes/'):

            # Look for the local branches that track the remote ones.
            try:
                local_branch = re.sub(rb'refs/remotes/(\w+)/', b'refs/heads/', self.current_version)  # pylint:disable=anomalous-backslash-in-string
                local_head_at = self.repo[local_branch]

            # Current branch is not tracking any remote one.
            except KeyError:
                return False
            remote_head_at = self.repo[self.current_version]
            if remote_head_at.id == local_head_at.id:
                return False

            # Maybe remote head has some updates.
            # Go back in the history and check if the current commit is in the remote branch history.
            for cmmt in self.repo.get_walker(remote_head_at.id):
                if local_head_at.id == cmmt.commit.id:  # If yes - then local branch is just outdated
                    return False
            return True

        # Something else - raise an exception.
        raise Exception("Unknown git reference type (should be either branch or tag), found: {}".format(
            self.current_version))

    def found_local_versions(self):
        """Find if local git branches are present."""
        pattern = re.compile(rb'refs/heads/(\w+)')  # pylint:disable=anomalous-backslash-in-string
        return any(pattern.match(value) for value in self.available_versions.values())

    @contextmanager
    def _for_all_versions(self):
        """Iterate through all versions to perform internal checks."""
        original_version = self.current_version
        with self.hold_trait_notifications():
            try:
                def _iterate_all_versions():
                    for branch in self.available_versions.values():
                        self.set_trait('current_version', branch)
                        yield

                yield _iterate_all_versions()
            finally:
                self.set_trait('current_version', original_version)

    def cannot_modify_app(self):
        """Check if there is any reason to not let modifying the app."""

        # It is not a git repo.
        if not self.has_git_repo():
            return 'not a git repo'

        # There is no remote URL specified.
        if not self._git_url:
            return 'no remote URL specified (risk to lose your work)'

        with self._for_all_versions() as branches:
            for branch in branches:

                # The repo has some uncommited modifications.
                if self.found_uncommited_modifications():
                    return "found uncommited modifications for branch '{}' (risk to lose your work)".format(branch)

                # Found local commits.
                if self.found_local_commits():
                    return "local commits found for branch '{}' (risk to lose your work)".format(branch)

        # Found no branches.
        if not self.available_versions:
            return 'no branches found'

        return ''

    def git_update_available(self):
        """Check whether there are updates available for the current branch in the remote repository."""

        if self.current_version is None or not self._git_url or self.current_version.startswith(b'refs/tags/'):
            # For later: if it is a tag check for the newer tags
            return False

        to_return = False

        # If it is a branch.
        if self.current_version.startswith(b'refs/remotes/'):

            # Learn about local repository.
            local_branch = re.sub(rb'refs/remotes/(\w+)/', b'refs/heads/', self.current_version)  # pylint:disable=anomalous-backslash-in-string
            local_head_id = self.repo[local_branch].id
            remote_head_id = self.repo[self.current_version].id

            # Check whether the current commit is not the same as remote commit.
            if local_head_id != remote_head_id:

                # Go back in the current branch commit history and see if I can find the remote commit there.
                for cmmt in self.repo.get_walker(local_head_id):

                    # Found, so the remote branch is outdated - no update.
                    if cmmt.commit.id == remote_head_id:
                        to_return = False
                        break

                # Not found, so the remote branch has additional commit(s).
                else:
                    to_return = True

            # Learn about remote repository, if possible
            try:
                on_server_head_at = bytes(self._git_remote_refs[local_branch.decode()], 'utf-8')
            except KeyError:
                return False

            # Check whether the remote reference on the server is outdated.
            if remote_head_id != on_server_head_at:

                # Check if the commit on remote server is present in my remote commit history.
                # It means the remote server is outdated.
                for cmmt in self.repo.get_walker(remote_head_id):
                    if cmmt.commit.id == on_server_head_at:
                        to_return = False
                        break
                else:
                    to_return = True

        return to_return

    update_available = git_update_available  # TODO: deprecate git-specific variant

    def _install_app(self, _):
        """Installing the app."""
        self.install_info = """<i class="fa fa-spinner fa-pulse" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1"><blink>Installing the app...</blink></font>"""
        clone(source=self._git_url, target=self._get_appdir())
        self.install_info = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1">Success</font>"""
        check_output(['git checkout {}'.format(AIIDALAB_DEFAULT_GIT_BRANCH)],
                     cwd=self._get_appdir(),
                     stderr=STDOUT,
                     shell=True)
        self._refresh_versions()
        sleep(1)
        self.install_info = ''

    def _update_app(self, _):
        """Perform app update."""
        cannot_modify = self.cannot_modify_app()
        if cannot_modify:
            self.install_info = """<i class="fa fa-times" style="color:red;font-size:4em;" >
            </i>Can not update the repository: {}""".format(cannot_modify)
            sleep(3)
            self.install_info = ''
            return

        self.install_info = """<i class="fa fa-spinner fa-pulse" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1"><blink>Updating the app...</blink></font>"""
        fetch(repo=self.repo, remote_location=self._git_url)
        pull(repo=self.repo, remote_location=self._git_url, refspecs=self.current_version)
        self.install_info = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1">Success</font>"""
        sleep(1)
        self.install_info = ''

    def uninstall_app(self, _=None):
        """Perfrom app uninstall."""
        cannot_modify = self.cannot_modify_app()

        # Check if one cannot install the app.
        if cannot_modify:
            pass
        elif self.name == 'home':
            cannot_modify = "can't remove the home app"
        elif self.found_local_versions():
            cannot_modify = "you have local branches"
        else:
            # look for the local commited modifications all the available branches
            with self._for_all_versions() as branches:
                for branch in branches:
                    if self.found_local_commits():
                        raise RuntimeError(
                            "Can not delete the repository, there are local commits "
                            "on branch '{}'.".format(branch))

        # Perform uninstall process.
        shutil.rmtree(self._get_appdir())
        self._refresh_versions()

    @property
    def refs_dict(self):
        """Returns a dictionary of references: branch names, tags."""
        refs_dict = {}
        for key, value in self.repo.get_refs().items():
            if key.endswith(b'HEAD') or key.startswith(b'refs/heads/'):
                continue
            obj = self.repo.get_object(value)
            if isinstance(obj, Tag):
                refs_dict[key] = obj.object[1]
            elif isinstance(obj, Commit):
                refs_dict[key] = value
        return refs_dict

    def _available_versions(self):
        """Function that looks for all the available branches. The branches can be both
        local and remote.

        : return : an OrderedDict that contains all available branches, for example
                   OrderedDict([('master', 'refs/remotes/origin/master')])."""

        # HEAD branch won't be included
        if not self.refs_dict:  # if no branches were found - return None
            return {}

        # Add remote branches.
        available = OrderedDict({
            name.split(b'/')[-1].decode("utf-8"): name
            for name, _ in self.refs_dict.items()
            if name.startswith(b'refs/remotes/')
        })

        # Add local branches that do not have tracked remotes.
        for name in self.refs_dict:
            if name.startswith(b'refs/heads/'):
                branch_label = name.replace(b'refs/heads/', b'').decode("utf-8")
                pattern = re.compile("refs/remotes/.*/{}".format(branch_label))
                # check if no tracked remotes that correspond to the current local branch
                if not any(pattern.match(value) for value in available.values()):
                    available[branch_label] = name

        # Add tags.
        available.update(
            sorted({
                name.split(b'/')[-1].decode("utf-8"): name
                for name, _ in self.refs_dict.items()
                if name.startswith(b'refs/tags/')
            }.items(),
                   reverse=True))

        return available

    def _current_version(self):
        """Function that returns the reference to the currently selected branch,
        for example 'refs/remotes/origin/master'."""

        # If no branches were found - return None
        if not self.refs_dict:
            return None

        # Get the current version
        available = self.available_versions
        try:

            # Get local branch name, except if not yet exists.
            current = self.repo.refs.follow(b'HEAD')[0][1]  # returns 'refs/heads/master'

            # If it is a tag it will except here
            branch_label = current.replace(b'refs/heads/', b'')  # becomes 'master'

            # Find the corresponding (remote or local) branch among the ones that were found before.
            pattern = re.compile(b"refs/.*/%s" % branch_label)
            for key in set(available.values()):
                if pattern.match(key):
                    current = key

        # In case this is not a branch, but a tag for example.
        except IndexError:
            reverted_refs_dict = {value: key for key, value in self.refs_dict.items()}
            try:
                current = reverted_refs_dict[self.repo.refs.follow(b'HEAD')
                                             [1]]  # knowing the hash I can access the tag
            except KeyError:
                print(("Detached HEAD state ({} app)?".format(self.name)))
                return None

        return current

    @contextmanager
    def request_version_change(self):
        """Use this context manager to safely request a version change.

        In case that the version cannot be changed, all changes are automatically
        rolled back.
        """
        assert not self._change_version_mode, "Can't enter context manager more than once."
        self._change_version_mode = True

        def request_version(new_version):
            self.set_trait('current_version', new_version)

        try:
            objection = self.cannot_modify_app()
            if objection:
                raise RuntimeError(objection)
            else:
                yield request_version
        finally:
            self._change_version_mode = False

    @traitlets.validate('current_version')
    def _valid_current_version(self, proposal):
        """Validate new version proposal."""

        if self.current_version is not None and self.current_version != proposal['value']:
            if self.found_uncommited_modifications():
                raise traitlets.TraitError(
                    "Can not switch to version {}: you have uncommitted modifications.""".format(proposal['value']))
        return proposal['value']

    @traitlets.observe('current_version')
    def _observe_current_version(self, change):
        """Change the app's current version."""
        if change['new'] is not None:
            check_output(['git', 'checkout', change['new']], cwd=self._get_appdir(), stderr=STDOUT)

    def _refresh_versions(self):
        """Refresh version."""
        with self.hold_trait_notifications():
            if self.is_installed() and self.has_git_repo():
                self.available_versions = self._available_versions()
                self.set_trait('current_version', self._current_version())
                self.updates_available = self._updates_available()
            else:
                self.available_versions = dict()
                self.set_trait('current_version', None)
                self.updates_available = None

    @property
    @ttl_cache()
    def metadata(self):
        """Return metadata dictionary. Give the priority to the local copy (better for the developers)."""
        if self.is_installed():
            try:
                with open(os.path.join(self._get_appdir(), 'metadata.json')) as json_file:
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
            if not os.path.isfile(os.path.join(self._get_appdir(), 'metadata.json')):
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

    git_url = url  # deprecated

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
    def repo(self):
        """Returns Git repository."""
        if self._repo is None:
            if self.is_installed():
                self._repo = Repo(self._get_appdir())
            else:
                raise AppNotInstalledException("The app is not installed")
        return self._repo

    def _updates_available(self):
        if self.has_git_repo() and self._git_url:
            return self.git_update_available()
        else:
            return None

    def render_app_manager_widget(self):
        """"Display widget to manage the app."""
        if self.has_git_repo():
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

    BODY_MAIN = """<b> <div style="font-size: 30px; text-align:center;">{title}</div></b>
    <br>
    <b>Authors:</b> {authors}
    <br>
    <b>Description:</b> {description}"""

    BODY_URL = """<br>
    <b>URL:</b> <a href="{url}">{url}</a>"""

    def __init__(self, app, with_version_selector=False):
        self.app = app

        body = ipw.HTML(self.BODY_MAIN.format(title=app.title, authors=app.authors, description=app.description))
        if app.url is not None:
            body.value += self.BODY_URL.format(url=app.url)

        # Setup install_info
        self.install_info = StatusHTML()

        # Setup buttons
        self.install_button = ipw.Button(description='install')
        self.install_button.on_click(app._install_app)

        self.uninstall_button = ipw.Button(description='uninstall')
        self.uninstall_button.on_click(self._uninstall_app)

        self.update_button = ipw.Button(description='update')
        self.update_button.on_click(app._update_app)

        self.app.observe(self._refresh, names=['path', 'install_info'])

        children = [
            ipw.HBox([app.logo, body]),
            ipw.HBox([self.uninstall_button, self.update_button, self.install_button]),
            ipw.HBox([self.install_info])]

        if with_version_selector:
            self.version_selector = VersionSelectorWidget()
            ipw.dlink(
                (self.app, 'available_versions'),
                (self.version_selector.selected, 'options'))
            ipw.dlink(
                (self.app, 'current_version'),
                (self.version_selector.selected, 'value'))
            self.version_selector.selected.observe(self._change_version, names=['value'])
            children.append(self.version_selector)

        self._refresh()  # init all widgets

        super().__init__(children=children)

    def _change_version(self, change):
        """Attempt to change the app version."""
        assert hasattr(self, 'version_selector')
        if change['new'] == self.app.current_version:
            return

        try:
            with self.app.request_version_change() as request:
                request(change['new'])

        except RuntimeError as error:
            self.version_selector.info.show_temporary_message(
                HTML_MSG_FAIL.format("Failed to switch version, error: '{}'".format(error)))
        else:
            self.version_selector.info.show_temporary_message(
                HTML_MSG_SUCCESS.format("Switched to version '{}'.".format(change['new'].decode())))

    def _refresh(self, _=None):
        """Refresh interface based on potentially changed app install and version state."""
        with self.hold_trait_notifications():
            installed = self.app.path and os.path.exists(self.app.path)
            update_available = self.app.git_update_available() if installed else False

            self.install_button.disabled = installed or self.app.url is None
            self.install_button.button_style = '' if installed else 'info'

            self.uninstall_button.disabled = not installed
            self.uninstall_button.button_style = 'danger' if installed else ''

            self.update_button.disabled = not update_available
            self.update_button.button_style = 'warning' if update_available else ''

    def _uninstall_app(self, _):
        """Attempt to uninstall the app."""
        try:
            self.app.uninstall_app()
        except RuntimeError as error:
            self.install_info.show_temporary_message(HTML_MSG_FAIL.format(error))
        else:
            self.install_info.show_temporary_message(HTML_MSG_SUCCESS.format("Uninstalled app."))
            self.uninstall_button.disabled = True
