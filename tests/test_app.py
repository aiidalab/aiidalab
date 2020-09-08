"""Tests for the aiidalab.app module."""
# pylint: disable=unused-argument,redefined-outer-name,invalid-name,protected-access
import json
from pathlib import Path
from subprocess import run, CalledProcessError
from urllib.parse import urlsplit, urldefrag

import pytest
from dulwich.repo import Repo

import aiidalab
from aiidalab.app import AiidaLabApp
from aiidalab.config import AIIDALAB_DEFAULT_GIT_BRANCH as DEFAULT_BRANCH

HELLO_WORLD_APP_DIR = Path(__file__).parent.joinpath('data', 'aiidalab-hello-world').resolve()
TESTING_BRANCH = 'testing-3926140692'  # we expect that this branch does not exist


def clone(source, target):
    """Git clone source at target."""
    run(['git', 'clone', urldefrag(str(source)).url, str(target)], check=True)


def checkout(repo, ref):
    """Checkout ref."""
    run(['git', 'checkout', ref], cwd=repo, check=True)


def commit(repo, message):
    git = ['git', '-c', 'user.name=pytest', '-c', 'user.email=pytest@example.com']
    run(git + ['commit', '--allow-empty', '-m', message], cwd=str(repo), check=True)


def tag(repo, name, head='HEAD'):
    git = ['git', '-c', 'user.name=pytest', '-c', 'user.email=pytest@example.com']
    run(git + ['tag', name, head], cwd=str(repo), check=True)


def reset_hard(repo, commit):
    git = ['git', '-c', 'user.name=pytest', '-c', 'user.email=pytest@example.com']
    run(git + ['reset', '--hard', commit], cwd=str(repo), check=True)


@pytest.fixture
def empty_registry():
    return dict(apps=dict(), categories=dict())


@pytest.fixture
def environment(tmp_path, monkeypatch, empty_registry):
    """Setup a complete and valid AiiDAlab environment."""
    root = Path(tmp_path)
    registry_path = root / 'apps_meta.json'

    monkeypatch.setattr(aiidalab.config, 'AIIDALAB_HOME', str(root / 'project'))
    monkeypatch.setattr(aiidalab.config, 'AIIDALAB_APPS', str(root / 'project/apps'))
    monkeypatch.setattr(aiidalab.config, 'AIIDALAB_SCRIPTS', str(root / 'opt'))
    monkeypatch.setattr(aiidalab.config, 'AIIDALAB_REGISTRY', f'file://{registry_path}')

    Path(aiidalab.config.AIIDALAB_HOME).mkdir()
    Path(aiidalab.config.AIIDALAB_APPS).mkdir()
    registry_path.write_text(json.dumps(empty_registry) + '\n')

    monkeypatch.setattr(aiidalab.app.AiidaLabApp, 'refresh_async', aiidalab.app.AiidaLabApp.refresh)

    yield


@pytest.fixture
def _hello_world_app_remote_origin(environment):
    """Create and configure a temporary remote origin for the hello world app."""
    # Clone the hello-world-app repository into a local path that will
    # serve as the "remote" origin.
    origin = Path(aiidalab.config.AIIDALAB_HOME).joinpath('local', 'aiidalab-hello-world').resolve()
    origin.parent.mkdir()
    try:
        clone(source=str(HELLO_WORLD_APP_DIR), target=str(origin))
    except CalledProcessError as error:
        pytest.skip(f"missing submodules to run this test: {error}")
    else:
        # Create orphaned tag
        commit(origin, 'orphaned')
        tag(origin, 'orphaned-tag')
        reset_hard(origin, 'HEAD~')

        # Create two empty commits.
        for message in ('first', 'second'):
            commit(origin, message)
        # Create a second branch that is identical to the default branch.
        run(['git', 'branch', TESTING_BRANCH], cwd=str(origin), check=True)
        run(['git', 'tag', 'test-tag', 'HEAD~'], cwd=str(origin), check=True)

    yield origin


def _register_hello_world_app(url, head):
    """Register the hello world app with the given url in the app registry."""
    app_data = json.loads(HELLO_WORLD_APP_DIR.joinpath('metadata.json').read_text())
    app_registry_data = {
        "git_url": url,
        "meta_url": "https://raw.githubusercontent.com/aiidalab/aiidalab-hello-world/master/metadata.json",
        "categories": ["Utilities"],
        "groups": ["utilities"],
        "metainfo": app_data,
        "gitinfo": {
            f"refs/heads/{DEFAULT_BRANCH}": head.decode(),
            f"refs/heads/{TESTING_BRANCH}": head.decode(),
        },
    }
    assert aiidalab.config.AIIDALAB_REGISTRY.startswith('file://')
    registry_path = Path(aiidalab.config.AIIDALAB_REGISTRY[len('file://'):])
    registry = json.loads(registry_path.read_text())
    assert 'hello-world' not in registry['apps']
    registry['apps']['hello-world'] = app_registry_data
    registry_path.write_text(json.dumps(registry))
    return app_registry_data


@pytest.fixture(params=['', f'#{DEFAULT_BRANCH}', f'#{TESTING_BRANCH}'])
def hello_world_app(_hello_world_app_remote_origin, request):
    """Return a AiidaLabApp fixture based on the hello-world-app."""
    url = f"{_hello_world_app_remote_origin}{request.param}"
    head = Repo(_hello_world_app_remote_origin).head()
    app_registry_data = _register_hello_world_app(url, head)
    apps_path = Path(aiidalab.config.AIIDALAB_APPS)
    yield AiidaLabApp('hello-world', app_registry_data, apps_path, watch=False)


@pytest.fixture(params=['v1.0.0', 'orphaned-tag'])
def hello_world_app_tagged(_hello_world_app_remote_origin, request):
    """Return a AiidaLabapp fixture based on the hello-world-app pinned to a specific version."""
    tag = request.param
    url = f"{_hello_world_app_remote_origin}#{tag}"
    head = Repo(_hello_world_app_remote_origin).refs[f'refs/tags/{tag}'.encode()]
    app_registry_data = _register_hello_world_app(url, head)
    apps_path = Path(aiidalab.config.AIIDALAB_APPS)
    yield AiidaLabApp('hello-world', app_registry_data, apps_path, watch=False)


@pytest.fixture
def hello_world_app_unregistered(_hello_world_app_remote_origin):
    """Return an unregistered AiidaLabApp fixture based on the hello-world-app."""
    apps_path = Path(aiidalab.config.AIIDALAB_APPS)
    clone(_hello_world_app_remote_origin, apps_path / 'hello-world')  # manual install
    yield AiidaLabApp('hello-world', None, apps_path, watch=False)


def test_environment_configuration(environment):
    """Basic checks of the AiiDAlab environment fixture."""
    assert Path(aiidalab.config.AIIDALAB_HOME).is_dir()
    assert Path(aiidalab.config.AIIDALAB_APPS).is_dir()
    assert aiidalab.config.AIIDALAB_REGISTRY
    registry_url = urlsplit(aiidalab.config.AIIDALAB_REGISTRY)
    assert all([registry_url.scheme, registry_url.path])


def test_hello_world_app_setup(hello_world_app):
    """Check the basic function of the AiidaLabApp class."""
    app = hello_world_app
    assert app.name == 'hello-world'
    assert not app.is_installed()
    for key in 'authors', 'description', 'title':
        assert key in app.metadata
        assert getattr(app, key) == app.metadata[key]
    for key in 'logo', 'state', 'version':
        assert key in app.metadata


def test_hello_world_app_install_uninstall(hello_world_app):
    """Test that the app can be uninstalled and installed again."""
    app = hello_world_app
    assert not app.is_installed()
    app.install_app()
    assert Path(app.path).is_dir()
    assert app.is_installed()
    assert app.installed_version is not aiidalab.app.AppVersion.NOT_INSTALLED
    assert app._release_line.line in app.installed_version
    app.uninstall_app()
    assert not app.is_installed()
    assert not Path(app.path).exists()
    assert app.installed_version is aiidalab.app.AppVersion.NOT_INSTALLED


@pytest.mark.parametrize(
    'desired_version,corresponding_tag',
    [
        # tags on the default branch:
        ('git:refs/tags/v1.0.0', 'git:refs/tags/v1.0.0'),
        ('git:refs/tags/test-tag', 'git:refs/tags/test-tag'),
        # commits on the default branch (tagged)
        ('git:c5349173dbdac1644be7bb676d4f1040bf5d745c', 'git:refs/tags/v1.0.0'),
        ('git:c5349173dbdac1644be', 'git:refs/tags/v1.0.0'),
    ])
def test_hello_world_app_switch_version(hello_world_app, desired_version, corresponding_tag):
    """Test that we can switch the app's version and back."""
    app = hello_world_app

    app.install_app()
    assert app.is_installed()
    original_version = app.installed_version
    tracked_branch = app._repo.get_tracked_branch()

    app.install_app(version=desired_version)
    assert app.installed_version == corresponding_tag
    assert tracked_branch == app._repo.get_tracked_branch()
    assert app.updates_available

    app.install_app(version=original_version)
    assert app.installed_version == original_version
    assert tracked_branch == app._repo.get_tracked_branch()


def test_hello_world_app_detached_head_state(hello_world_app):
    """Test whether the app recovers from a detached HEAD state after version switch."""
    app = hello_world_app

    app.install_app()
    assert app.is_installed()
    original_version = app.installed_version
    tracked_branch = app._repo.get_tracked_branch()

    checkout(app.path, 'HEAD~')  # switch to detached HEAD state
    with pytest.raises(RuntimeError):
        assert tracked_branch == app._repo.get_tracked_branch()

    app.install_app(version=original_version)
    assert app.installed_version == original_version
    assert tracked_branch == app._repo.get_tracked_branch()


def test_hello_world_app_update_available(hello_world_app):
    """Test the update_available trait."""
    app = hello_world_app

    app.install_app()
    assert app.is_installed()
    assert not app.updates_available
    original_version = app.installed_version
    tracked_branch = app._repo.get_tracked_branch()

    v1 = 'git:refs/tags/v1.0.0'
    app.install_app(version=v1)
    assert app.installed_version == v1
    assert tracked_branch == app._repo.get_tracked_branch()
    assert app.updates_available

    app.install_app(version=original_version)
    assert app.installed_version == original_version
    assert tracked_branch == app._repo.get_tracked_branch()
    assert not app.updates_available


def test_hello_world_app_remote_update_available(hello_world_app):
    """Test the update_available trait for remote updates."""
    # Check the remote updates
    app = hello_world_app

    app.install_app()
    assert not app.updates_available

    # First reset the local branch.
    run(['git', 'reset', '--hard', 'HEAD~'], cwd=app.path, check=True)
    app.refresh()
    assert app.updates_available

    # Next also reset the local ref to the remote branch.
    # However, the app should still know about the update, because of the gitinfo in the
    # registry data.
    run(['git', 'update-ref', 'refs/remotes/origin/master', 'HEAD'], cwd=app.path, check=True)
    app.refresh()
    assert app.updates_available


def test_hello_world_app_update(hello_world_app):
    """Test the update_available trait."""
    app = hello_world_app

    app.install_app()
    assert app.is_installed()
    assert not app.updates_available
    original_version = app.installed_version
    tracked_branch = app._repo.get_tracked_branch()

    v1 = 'git:refs/tags/v1.0.0'
    app.install_app(version=v1)
    assert app.installed_version == v1
    assert tracked_branch == app._repo.get_tracked_branch()
    assert app.updates_available

    app.update_app()
    assert app.installed_version == original_version
    assert tracked_branch == app._repo.get_tracked_branch()
    assert not app.updates_available


def test_hello_world_app_tagged_switch_version(hello_world_app_tagged):
    """Test that we can switch the app's version and back."""
    app = hello_world_app_tagged
    assert app._release_line.line in ('v1.0.0', 'orphaned-tag')

    app.install_app()
    assert app.is_installed()
    original_version = app.installed_version
    assert original_version in ('git:refs/tags/v1.0.0', 'git:refs/tags/orphaned-tag')
    assert not app.updates_available

    app.install_app(version='git:refs/tags/test-tag')
    assert app.installed_version == aiidalab.app.AppVersion.UNKNOWN
    assert not app.updates_available

    app.install_app(version=original_version)
    assert app.installed_version == original_version
    assert not app.updates_available


def test_hello_world_app_unregistered(hello_world_app_unregistered):
    """Test behavior of an unregistered app."""
    app = hello_world_app_unregistered

    assert app.is_installed()
    assert app.installed_version is aiidalab.app.AppVersion.UNKNOWN
    assert app.updates_available is None
    app.uninstall_app()
    assert not app.is_installed()
    assert app.installed_version is aiidalab.app.AppVersion.NOT_INSTALLED
    assert app.updates_available is None
