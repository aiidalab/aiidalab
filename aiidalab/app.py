# -*- coding: utf-8 -*-
"""Module to manage AiiDA lab apps."""

import re
import os
from os import path
from time import sleep
from collections import OrderedDict

import requests
import ipywidgets as ipw
from dulwich.repo import Repo


class AppNotInstalledException(Exception):
    pass


class VersionSelectorWidget(ipw.VBox):
    """Class to choose app's version."""

    def __init__(self):
        self.change_btn = ipw.Button(description="choose seleted")
        self.selected = ipw.Select(
            options={},
            description='Select version',
            disabled=False,
            style={'description_width': 'initial'},
        )
        self.info = ipw.HTML('')
        super().__init__([self.selected, self.change_btn, self.info])


class AiidaLabApp():  # pylint: disable=attribute-defined-outside-init,too-many-public-methods,too-many-instance-attributes
    """Class to manage AiiDA lab app."""

    def __init__(self, name, app_data, aiidalab_apps):  #, custom_update=False):
        if app_data is not None:
            self._git_url = app_data['git_url']
            self._meta_url = app_data['meta_url']
            self._git_remote_refs = app_data['gitinfo']
            self.categories = app_data['categories']
        else:
            self._git_url = None
            self._git_remote_refs = {}
        self.install_info = ipw.HTML()
        self.aiidalab_apps = aiidalab_apps
        self.name = name

    def in_category(self, category):
        # One should test what happens if the category won't be defined.
        return category in self.categories

    def _get_appdir(self):
        return path.join(self.aiidalab_apps, self.name)

    def is_installed(self):
        """The app is installed if the corresponding folder is present."""
        return path.isdir(self._get_appdir())

    def has_git_repo(self):
        """Check if the app has a .git folder in it."""
        from dulwich.errors import NotGitRepository
        try:
            Repo(self._get_appdir())
            return True
        except NotGitRepository:
            return False

    def found_uncommited_modifications(self):
        """Check whether the git-supervised files were modified."""
        from dulwich.porcelain import status
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
                local_branch = re.sub(b'refs/remotes/(\w+)/', b'refs/heads/', self.current_version)  # pylint:disable=anomalous-backslash-in-string
                local_head_at = self.repo[bytes(local_branch)]

            # Current branch is not tracking any remote one.
            except KeyError:
                return False
            remote_head_at = self.repo[bytes(self.current_version)]
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
        pattern = re.compile(b'refs/heads/(\w+)')  # pylint:disable=anomalous-backslash-in-string
        return any(pattern.match(value) for value in self.available_versions.values())

    def cannot_modify_app(self):
        """Check if there is any reason to not let modifying the app."""

        # It is not a git repo.
        if not self.has_git_repo():
            return 'not a git repo'

        # There is no remote URL specified.
        if not self._git_url:
            return 'no remote URL specified (risk to lose your work)'

        # The repo has some uncommited modifications.
        if self.found_uncommited_modifications():
            return 'found uncommited modifications (risk to lose your work)'

        # Found local commits.
        if self.found_local_commits():
            return 'local commits found (risk to lose your work)'

        # Found no branches.
        if not self.available_versions:
            return 'no branches found'

        return ''

    def git_update_available(self):
        """Check whether there are updates available for the current branch in the remote repository."""

        if self.current_version is None or not self._git_url or self.current_version.startswith(b'refs/tags/'):
            # For later: if it is a tag check for the newer tags
            to_return = False

        # If it is a branch.
        elif self.current_version.startswith(b'refs/remotes/'):

            # Learn about local repository.
            local_branch = re.sub(b'refs/remotes/(\w+)/', b'refs/heads/', self.current_version)  # pylint:disable=anomalous-backslash-in-string
            local_head_at = self.repo[bytes(local_branch)]
            remote_head_at = self.repo[bytes(self.current_version)]

            # Learn about remote repository.
            try:
                on_server_head_at = self._git_remote_refs[local_branch]
            except KeyError:
                return False

            # Is remote reference on the server is outdated?
            if remote_head_at.id != on_server_head_at:

                # I check if the remote commit is present in my remote commit history.
                for cmmt in self.repo.get_walker(remote_head_at.id):
                    if cmmt.commit.id == on_server_head_at:
                        to_return = False
                        break
                else:
                    to_return = True

            elif local_head_at != remote_head_at:

                # Go back in the current branch commit history and see if I can find the remote commit there.
                for cmmt in self.repo.get_walker(local_head_at.id):

                    # Found, so the remote branch is outdated - no update.
                    if cmmt.commit.id == remote_head_at.id:
                        to_return = False
                        break

                # Not found, so the remote branch has additional commit(s).
                else:
                    to_return = True
            # else
            #return False
        # local branches can't have an update
        #if self.current_version.startswith(b'refs/heads'):
        #    return False
        # something else
        return to_return

    @property
    def install_button(self):
        """Button to install the app."""
        if not hasattr(self, '_install_button'):
            self._install_button = ipw.Button(description="install")
            self._install_button.on_click(self._install_app)
            self._refresh_install_button()
        return self._install_button

    def _install_app(self, _):
        """Installing the app."""
        from dulwich.porcelain import clone
        self.install_info.value = """<i class="fa fa-spinner fa-pulse" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1"><blink>Installing the app...</blink></font>"""
        clone(source=self._git_url, target=self._get_appdir())
        self.install_info.value = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1">Success</font>"""
        self._refresh_version()
        self._refresh_install_button()
        self._refresh_update_button()
        self._refresh_uninstall_button()
        sleep(1)
        self.install_info.value = ''

    def _refresh_install_button(self):
        """Refreshing install app button."""
        if self.is_installed():
            self._install_button.disabled = True
            self._install_button.button_style = ''
        else:
            if self._git_url is None:
                self._install_button.disabled = True
                self._install_button.button_style = 'no url provided'
            else:
                # activate install button
                self.update_button.description = 'install first'
                self._install_button.disabled = False
                self._install_button.button_style = 'info'

    @property
    def update_button(self):
        """Button to updated the app."""
        if not hasattr(self, '_update_button'):
            self._update_button = ipw.Button(description="update to the latest")
            self._update_button.on_click(self._update_app)
            self._refresh_update_button()
        return self._update_button

    def _update_app(self, _):
        """Perform app update."""
        from dulwich.porcelain import pull, fetch
        cannot_modify = self.cannot_modify_app()
        if cannot_modify:
            self.install_info.value = """<i class="fa fa-times" style="color:red;font-size:4em;" >
            </i>Can not update the repository: {}""".format(cannot_modify)
            sleep(3)
            self.install_info.value = ''
            return

        self.install_info.value = """<i class="fa fa-spinner fa-pulse" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1"><blink>Updating the app...</blink></font>"""
        fetch(repo=self.repo, remote_location=self._git_url)
        pull(repo=self.repo, remote_location=self._git_url, refspecs=self.version.selected.label)
        self.install_info.value = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1">Success</font>"""
        self._refresh_update_button()
        sleep(1)
        self.install_info.value = ''

    def _refresh_update_button(self):
        """Refresh update buttons."""
        if self.is_installed():
            if self.git_update_available():
                self.update_button.disabled = False
                self.update_button.button_style = 'warning'
                self.update_button.description = 'update'
            else:
                self.update_button.disabled = True
                self.update_button.button_style = ''
                self.update_button.description = 'no update available'
        else:
            self.update_button.disabled = True
            self.update_button.button_style = ''
            self.update_button.description = 'Install first'

    @property
    def uninstall_button(self):
        """Button to uninstall the app."""
        if not hasattr(self, '_uninstall_button'):
            self._uninstall_button = ipw.Button(description="uninstall")
            self._uninstall_button.on_click(self._uninstall_app)
            self._refresh_uninstall_button()
        return self._uninstall_button

    def _uninstall_app(self, _):
        """Perfrom app uninstall."""
        from shutil import rmtree
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
            initial_value = self.current_version
            for key, value in self.available_versions.items():
                self.version.selected.value = value  # switching to the branch in value
                self._change_version(sleep_time=0)  # actually switching the branch
                if self.found_local_commits():
                    cannot_modify = "you have local commits ({} branch)".format(key)
                    self.version.selected.value = initial_value  # switch back to the initial version
                    self._change_version(sleep_time=0)  # actually switching the branch
                    break

        # And finally: uninstall or not?
        if cannot_modify:
            self.install_info.value = """<i class="fa fa-times" style="color:red;font-size:4em;" >
            </i>Can not delete the repository: {}""".format(cannot_modify)
            sleep(3)

        # Perform uninstall process.
        else:
            self.install_info.value = """<i class="fa fa-spinner fa-pulse" style="color:#337ab7;font-size:4em;" ></i>
            <font size="1"><blink>Unistalling the app...</blink></font>"""
            sleep(1)
            rmtree(self._get_appdir())
            if hasattr(self, '_current_version'):
                delattr(self, '_current_version')
            if hasattr(self, '_available_versions'):
                delattr(self, '_available_versions')
            self.install_info.value = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
            <font size="1">Success</font>"""
            self._refresh_version()
            self._refresh_install_button()
            self._refresh_update_button()
            self._refresh_uninstall_button()
            sleep(1)
        self.install_info.value = ''

    def _refresh_uninstall_button(self):
        """Refresh uninstall button."""
        if self.is_installed():
            self.uninstall_button.disabled = False
            self.uninstall_button.button_style = 'danger'
        else:
            self.uninstall_button.disabled = True
            self.uninstall_button.button_style = ''

    @property
    def version(self):
        """App's version."""
        if not hasattr(self, '_version'):
            self._version = VersionSelectorWidget()
            self._version.change_btn.on_click(self._change_version)
            self._refresh_version()
        return self._version

    @property
    def refs_dict(self):
        """Returns a dictionary of references: branch names, tags."""
        if not hasattr(self, '_refs_dict'):
            from dulwich.objects import Commit, Tag
            self._refs_dict = {}
            for key, value in self.repo.get_refs().items():
                if key.endswith(b'HEAD'):
                    continue
                elif key.startswith(b'refs/heads/'):
                    continue
                obj = self.repo.get_object(value)
                if isinstance(obj, Tag):
                    self._refs_dict[key] = obj.object[1]
                elif isinstance(obj, Commit):
                    self._refs_dict[key] = value
        return self._refs_dict

    @property
    def available_versions(self):
        """Function that looks for all the available branches. The branches can be both
        local and remote.

        : return : an OrderedDict that contains all available branches, for example
                   OrderedDict([('master', 'refs/remotes/origin/master')])."""

        if not hasattr(self, '_available_versions'):
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
            self._available_versions = available
        return self._available_versions

    @property
    def current_version(self):
        """Function that returns the reference to the currently selected branch,
        for example 'refs/remotes/origin/master'."""

        if not hasattr(self, '_current_version'):

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
                for key in {value for value in available.values()}:
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
            self._current_version = current
        return self._current_version

    def _change_version(self, _=None, sleep_time=2):
        """Change app's version."""

        import subprocess
        from subprocess import check_output
        if not self.current_version == self.version.selected.value:
            if self.found_uncommited_modifications():
                self.version.info.value = """"<i class="fa fa-times" style="color:red;font-size:4em;" ></i>
                Can not switch to the branch {}:
                you have uncommited modifitaions""".format(self.version.selected.label)
                sleep(2)
                self.version.info.value = ''
                return

            check_output(['git checkout {}'.format(self.version.selected.label)],
                         cwd=self._get_appdir(),
                         stderr=subprocess.STDOUT,
                         shell=True)
            if hasattr(self, '_current_version'):
                delattr(self, '_current_version')
            self.version.info.value = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
            <font size="1">Success, changed to {}</font>""".format(self.version.selected.label)
            sleep(sleep_time)
            self.version.info.value = ''
            self._refresh_version()

        else:
            self.version.info.value = """<i class="fa fa-times" style="color:red;font-size:4em;" ></i>
            <font size="1">Same branch, so no changes</font>"""
            sleep(sleep_time)
            self.version.info.value = ''

    def _refresh_version(self):
        """Refresh version."""
        if self.is_installed() and self.has_git_repo():
            self.version.selected.options = self.available_versions
            self.version.selected.value = self.current_version

            # Check if it is possible to replace with
            # self.version.layout.visibility = 'visibility'
            self.version.selected.layout.visibility = 'visible'
            self.version.change_btn.layout.visibility = 'visible'
        else:
            # Deactivate version selector.

            # Check if it is possible to replace with
            # self.version.layout.visibility = 'hidden'
            self.version.selected.layout.visibility = 'hidden'
            self.version.change_btn.layout.visibility = 'hidden'

    @property
    def metadata(self):
        """Return metadata dictionary. Give the priority to the local copy (better for the developers)."""
        try:
            return self._metadata
        except AttributeError:
            if self.is_installed():
                try:
                    with open(path.join(self._get_appdir(), 'metadata.json')) as json_file:
                        import json
                        self._metadata = json.load(json_file)
                except IOError:
                    self._metadata = {}
            else:
                self._metadata = requests.get(self._meta_url).json()
            return self._metadata

    def _get_from_metadata(self, what):
        """Get information from metadata."""

        try:
            return "{}".format(self.metadata[what])
        except KeyError:
            if not path.isfile(path.join(self._get_appdir(), 'metadata.json')):
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
    def git_url(self):
        """Provide explicit link to Git repository."""
        if self._git_url is None:
            return '-'
        # else
        return '<a href="{}">{}</a>'.format(self._git_url, self._git_url)

    @property
    def git_hidden_url(self):
        """Provide a link to Git repository."""
        if self._git_url is None:
            return 'No Git url'
        # else
        return '<a href="{}"><button>Git URL</button></a>'.format(self._git_url)

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
            res.value = '<img src="{}">'.format(path.join('..', self.name, self.metadata['logo']))

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
        if not hasattr(self, '_repo'):
            if self.is_installed():
                self._repo = Repo(self._get_appdir())
            else:
                raise AppNotInstalledException("The app is not installed")
        return self._repo

    @property
    def update_info(self):
        """Update app info."""
        if not self.has_git_repo():
            return """<font color="#D8000C"><i class='fa fa-times-circle'></i> Not a Git Repo</font>"""
        if not self._git_url:
            return """<font color="#D8000C"><i class='fa fa-times-circle'></i> No remote URL</font>"""
        if self.git_update_available():
            return """<font color="#9F6000"><i class='fa fa-warning'></i> Update Available</font>"""
        return """<font color="#270"><i class='fa fa-check'></i> Latest Version</font>"""

    def render_app_manager_widget(self):
        """"Display widget to manage the app."""
        if self.has_git_repo():
            description = ipw.HTML("""<b> <div style="font-size: 30px; text-align:center;">{}</div></b>
            <br>
            <b>Authors:</b> {}
            <br>
            <b>Description:</b> {}
            <br>
            <b>Git URL:</b> {}""".format(self.title, self.authors, self.description, self.git_url))
            logo = self.logo
            logo.layout.margin = "100px 0px 0px 0px"
            description.layout = {'width': '800px'}
            displayed_app = ipw.VBox([
                ipw.HBox([self.logo, description]),
                ipw.HBox([self.uninstall_button, self.update_button, self.install_button]),
                ipw.HBox([self.install_info]), self.version
            ])
        else:
            displayed_app = ipw.HTML("""<center><h1>Enable <i class="fa fa-git"></i> first!</h1></center>""")

        return displayed_app
