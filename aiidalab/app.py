# -*- coding: utf-8 -*-

import re
import os
import requests
import ipywidgets as ipw
from collections import OrderedDict
from time import sleep
from os import path
from dulwich.repo import Repo

class AppNotInstalledException(Exception):
    pass

class Version(ipw.VBox):
    def __init__(self):
        self.change_btn = ipw.Button(description="choose seleted")
        self.selected = ipw.Select(
                options = {},
                description='Select version',
                disabled = False,
                style = {'description_width': 'initial'},
            )
        self.info = ipw.HTML('')
        super(Version, self).__init__([self.selected, self.change_btn, self.info])

class AppBase():
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
        # TODO: see what will happen if the category won't be defined
        return category in self.categories

    def _get_appdir(self):
        return path.join(self.aiidalab_apps, self.name)

    def is_installed(self):
        """The app is installed if the corresponding folder is present"""
        return path.isdir(self._get_appdir())

    def has_git_repo(self):
        from dulwich.errors import NotGitRepository
        try:
            Repo(self._get_appdir())
            return True
        except NotGitRepository:
            return False

    def found_uncommited_modifications(self):
        """Check whether the git-supervised files were modified"""
        from dulwich.porcelain import status
        s = status(self.repo)
        if s.unstaged:
            return True
        for _, value in s.staged.items():
            if value:
                return True
        return False

    def found_local_commits(self):
        """Check whether user did some work in the current branch.
        Here is the logic:
        - if it is a tag - return False
        - if it is a local branch - always return True (even though it
          can be that there are no local commits in it
        - if it is a remote branch - check properly"""
        # no local commits if it is a tag
        if self.current_version.startswith(b'refs/tags/'):
            return False
        # here it is assumed that if the branch is local, it has some stuff done in it,
        # therefore True is returned even though technically it is not always true
        if self.current_version.startswith(b'refs/heads/'):
            return True
        # if it is a remote branch
        if self.current_version.startswith(b'refs/remotes/'):
            try: # look for the local branches that track the remote ones
                local_branch = re.sub('refs/remotes/(\w+)/', 'refs/heads/', self.current_version)
                local_head_at = self.repo[bytes(local_branch)]
            except KeyError: # current branch is not tracking any remote one
                return False
            remote_head_at = self.repo[bytes(self.current_version)]
            if remote_head_at.id == local_head_at.id:
                return False
            # else
            # maybe remote head has some updates.
            # go back in the history and check if the current commit is in the remote branch history.
            for c in self.repo.get_walker(remote_head_at.id):
                if local_head_at.id == c.commit.id: # if yes - then local branch is just outdated
                    return False
            return True
        # something else - raise exception
        # else
        raise Exception("Unknown git reference type (should be either branch or tag), found: {}".format(self.current_version))

    def found_local_versions(self):
        """Find if local git branches are present"""
        pattern = re.compile("refs/heads/(\w+)")
        return any(pattern.match(value) for value in self.available_versions.values())

    def cannot_modify_app(self):
        to_return = ''
        if not self.has_git_repo():
            to_return = 'not a git repo'
        elif not self._git_url:
            to_return = 'no remote URL specified (risk to lose your work)'
        elif self.found_uncommited_modifications():
            to_return = 'found uncommited modifications (risk to lose your work)'
        elif self.found_local_commits():
            to_return = 'local commits found (risk to lose your work)'
        elif not self.available_versions:
            to_return = 'no branches found'
        return to_return

    def git_update_available(self):
        """Check whether there are updates available for the current branch in the remote repository"""
        # update_available = False
        if self.current_version is None:
            return False
        if not self._git_url:
            return False
        if self.current_version.startswith(b'refs/tags/'):
            # TODO: if it is a tag check for the newer tags
            return False
        # if it is a branch
        if self.current_version.startswith(b'refs/remotes/'):
            # learn about local repository
            local_branch = re.sub(b'refs/remotes/(\w+)/', b'refs/heads/', self.current_version)
            local_head_at = self.repo[bytes(local_branch)]
            remote_head_at = self.repo[bytes(self.current_version)]
            # learn about remote repository
            try:
                on_server_head_at = self._git_remote_refs[local_branch]
            except KeyError:
                return False
            if remote_head_at.id != on_server_head_at:  # maybe remote reference on the server is outdated.
                                                        # I check if the remote commit is present in my remote commit history
                for c in self.repo.get_walker(remote_head_at.id):
                    if c.commit.id == on_server_head_at:
                        return False
                # else
                return True
            if local_head_at != remote_head_at:
                for c in self.repo.get_walker(local_head_at.id):  # go back in the current branch commit history and
                                                                  # see if I can find the remote commit there
                    if c.commit.id == remote_head_at.id: # Found, so the remote branch is outdated - no update
                        return False
                # Not found, so the remote branch has additional commit(s)
                return True
            # else
            return False
        # local branches can't have an update
        if self.current_version.startswith(b'refs/heads'):
            return False
        # something else
        return False

    @property
    def install_button(self):
        if not hasattr(self, '_install_button'):
            self._install_button = ipw.Button(description="install")
            self._install_button.on_click(self._install_app)
            self._refresh_install_button()
        return self._install_button

    def _install_app(self, _):
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
        if not hasattr(self, '_update_button'):
            self._update_button = ipw.Button(description="update to the latest")
            self._update_button.on_click(self._update_app)
            self._refresh_update_button()
        return self._update_button

    def _update_app(self, _):
        from dulwich.porcelain import pull, fetch
        cannot_modify = self.cannot_modify_app()
        if cannot_modify:
            self.install_info.value = """"<i class="fa fa-times" style="color:red;font-size:4em;" ></i>
                    Can not update the repository: {}""".format(cannot_modify)
            sleep(3)
            self.install_info.value = ''
            return

        self.install_info.value = """<i class="fa fa-spinner fa-pulse" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1"><blink>Updating the app...</blink></font>"""
        fetch(repo = self.repo, remote_location=self._git_url)
        pull(repo = self.repo, remote_location=self._git_url, refspecs=self.version.selected.label)
        self.install_info.value = """<i class="fa fa-check" style="color:#337ab7;font-size:4em;" ></i>
        <font size="1">Success</font>"""
        self._refresh_update_button()
        sleep(1)
        self.install_info.value = ''

    def _refresh_update_button(self):
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
        if not hasattr(self, '_uninstall_button'):
            self._uninstall_button = ipw.Button(description="uninstall")
            self._uninstall_button.on_click(self._uninstall_app)
            self._refresh_uninstall_button()
        return self._uninstall_button

    def _uninstall_app(self, _):
        from shutil import rmtree
        cannot_modify = self.cannot_modify_app()
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
                self.version.selected.value = value # switching to the branch in value
                self._change_version(sleep_time=0) # actually switching the branch
                if self.found_local_commits():
                    cannot_modify = "you have local commits ({} branch)".format(key)
                    self.version.selected.value = initial_value # switch back to the initial version
                    self._change_version(sleep_time=0) # actually switching the branch
                    break
        # and finally: uninstall or not?
        if cannot_modify:
            self.install_info.value = """"<i class="fa fa-times" style="color:red;font-size:4em;" ></i>
                Can not delete the repository: {}""".format(cannot_modify)
            sleep(3)
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
        if self.is_installed():
            self.uninstall_button.disabled = False
            self.uninstall_button.button_style = 'danger'
        else:
            self.uninstall_button.disabled = True
            self.uninstall_button.button_style = ''

    @property
    def version(self):
        if not hasattr(self, '_version'):
            self._version = Version()
            self._version.change_btn.on_click(self._change_version)
            self._refresh_version()
        return self._version

    @property
    def refs_dict(self):
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
        """
        Function that looks for all the available branches. The branches can be both
        local and remote.

        : return : an OrderedDict that contains all available branches, for example
                   OrderedDict([('master', 'refs/remotes/origin/master')])
        """
        if not hasattr(self, '_available_versions'):
            # HEAD branch won't be included
            if not self.refs_dict: # if no branches were found - return None
                return {}

            # add remote branches
            available = OrderedDict({name.split(b'/')[-1].decode("utf-8"):name
                                     for name, _ in self.refs_dict.items()
                                     if name.startswith(b'refs/remotes/')})

            # add local branches that do not have tracked remotes
            for name in self.refs_dict:
                if name.startswith(b'refs/heads/'):
                    branch_label = name.replace(b'refs/heads/', b'').decode("utf-8")
                    pattern = re.compile("refs/remotes/.*/{}".format(branch_label))
                    # check if no tracked remotes that correspond to the current local branch
                    if not any(pattern.match(value) for value in available.values()):
                        available[branch_label] = name

            # add tags
            available.update(sorted({name.split(b'/')[-1].decode("utf-8"):name
                                     for name, _ in self.refs_dict.items()
                                     if name.startswith(b'refs/tags/')}.items(),reverse=True))
            self._available_versions = available
        return self._available_versions

    @property
    def current_version(self):
        """Function that returns the reference to the currently selected branch,
        for example 'refs/remotes/origin/master' """
        if not hasattr(self, '_current_version'):
            # if no branches were found - return None
            if not self.refs_dict:
                return None
            # get the current version
            available = self.available_versions
            try:
                # get local branch name, except if not yet exists

                current = self.repo.refs.follow(b'HEAD')[0][1]  # returns 'refs/heads/master'
                                                               # if it is a tag it will except here
                branch_label = current.replace(b'refs/heads/', b'') # becomes 'master'
                # find the corresponding (remote or local) branch among the ones that were
                # found before
                pattern = re.compile(b"refs/.*/%s" % branch_label)
                for key in {value for value in available.values()}:
                    if pattern.match(key):
                        current = key
            except IndexError: # In case this is not a branch, but a tag for example
                reverted_refs_dict = {value: key for key, value in self.refs_dict.items()}
                try:
                    current = reverted_refs_dict[self.repo.refs.follow(b'HEAD')[1]] # knowing the hash I can access the tag
                except KeyError:
                    print("Detached HEAD state ({} app)?".format(self.name))
                    return None
            self._current_version = current
        return self._current_version

    def _change_version(self, b=None, sleep_time=2):
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
            out = check_output(['git checkout {}'.format(self.version.selected.label)],
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
        if self.is_installed() and self.has_git_repo():
            self.version.selected.options = self.available_versions
            self.version.selected.value = self.current_version
            # TODO: replace with
            # self.version.layout.visibility = 'visibility'
            self.version.selected.layout.visibility = 'visible'
            self.version.change_btn.layout.visibility = 'visible'
        else:
            # deactivate version selector
            # TODO: replace with
            # self.version.layout.visibility = 'hidden'
            self.version.selected.layout.visibility = 'hidden'
            self.version.change_btn.layout.visibility = 'hidden'
        
    @property
    def metadata(self):
        """Return metadata dictionary. Give the priority to the local copy
        (better for the developers)"""
        try:
            return self._metadata
        except AttributeError:
            if self.is_installed():
                try:
                    with open(path.join(self._get_appdir(),'metadata.json')) as json_file:
                        import json
                        self._metadata = json.load(json_file)
                except IOError:
                    self._metadata = {}
            else:
                self._metadata = requests.get(self._meta_url).json()
            return self._metadata

    def _get_from_metadata(self, what):
        try:
            return "{}".format(self.metadata[what])
        except KeyError:
            if not path.isfile(path.join(self._get_appdir(),'metadata.json')):
                return '({}) metadata.json file is not present'.format(what)
            # else
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
        if self._git_url is None:
            return '-'
        # else
        return '<a href="{}">{}</a>'.format(self._git_url, self._git_url)

    @property
    def git_hidden_url(self):
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
        res = ipw.HTML('<img src="./aiidalab_logo_v4.svg">', layout={'width': '100px', 'height': '100px'})
        try:
            if self.is_installed():
                res.value = '<img src="{}">'.format(path.join('..', self.name, self.metadata['logo']))
            else:
                html_link = os.path.splitext(self._git_url)[0] # remove .git if present
                html_link += '/master/' + self.metadata['logo'] # we expect it to always be a git repository
                if 'github.com' in html_link:
                    html_link = html_link.replace('github.com', 'raw.githubusercontent.com')
                    if html_link.endswith('.svg'):
                        html_link += '?sanitize=true'
                res.value = '<img src="{}">'.format(html_link)
        except Exception:
            res.value = '<img src="./aiidalab_logo_v4.svg">'
            # for some reason standard ipw.Image() app does not work properly
        return res

    @property
    def repo(self):
        if not hasattr(self, '_repo'):
            if self.is_installed():
                self._repo = Repo(self._get_appdir())
            else:
                raise AppNotInstalledException("The app is not installed")
        return self._repo

    @property
    def update_info(self):
        if not self.has_git_repo():
            return """<font color="#D8000C"><i class='fa fa-times-circle'></i> Not a Git Repo</font>"""
        elif not self._git_url:
            return """<font color="#D8000C"><i class='fa fa-times-circle'></i> No remote URL</font>"""
        elif self.git_update_available():
            return """<font color="#9F6000"><i class='fa fa-warning'></i> Update Available</font>"""
        return """<font color="#270"><i class='fa fa-check'></i> Latest Version</font>"""
