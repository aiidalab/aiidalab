"""Tests for the aiidalab.app module."""
# pylint: disable=unused-argument,redefined-outer-name,invalid-name,protected-access
import json
from pathlib import Path
from subprocess import run, CalledProcessError
from urllib.parse import urlsplit

import pytest

import aiidalab
from aiidalab.app import AiidaLabApp
from aiidalab.config import AIIDALAB_DEFAULT_GIT_BRANCH as DEFAULT_BRANCH

HELLO_WORLD_APP_DIR = Path(__file__).parent.joinpath('data', 'aiidalab-hello-world').resolve()
TESTING_BRANCH = 'testing-3926140692'  # we expect that this branch does not exist


def clone(source, target):
    """Git clone source at target."""
    run(['git', 'clone', str(source), str(target)], check=True)


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
        run([
            'git', '-c', 'user.name=pytest', '-c', 'user.email=pytest@example.com', 'commit', '-m', 'latest',
            '--allow-empty'
        ],
            cwd=str(origin),
            check=True)
        run(['git', 'branch', TESTING_BRANCH], cwd=str(origin), check=True)
        run(['git', 'tag', 'test-tag', 'HEAD~~'], cwd=str(origin), check=True)
    yield origin


def _register_hello_world_app(url):
    """Register the hello world app with the given url in the app registry."""
    app_data = json.loads(HELLO_WORLD_APP_DIR.joinpath('metadata.json').read_text())
    app_registry_data = {
        "git_url": url,
        "meta_url": "https://raw.githubusercontent.com/aiidalab/aiidalab-hello-world/master/metadata.json",
        "categories": ["Utilities"],
        "groups": ["utilities"],
        "metainfo": app_data
    }
    assert aiidalab.config.AIIDALAB_REGISTRY.startswith('file://')
    registry_path = Path(aiidalab.config.AIIDALAB_REGISTRY[len('file://'):])
    registry = json.loads(registry_path.read_text())
    assert 'hello-world' not in registry['apps']
    registry['apps']['hello-world'] = app_registry_data
    registry_path.write_text(json.dumps(registry))
    return app_registry_data


@pytest.fixture(params=['', f'@{DEFAULT_BRANCH}', f'@{TESTING_BRANCH}'])
def hello_world_app(_hello_world_app_remote_origin, request):
    """Return a AiidaLabApp fixture based on the hello-world-app."""
    url = f"{_hello_world_app_remote_origin}{request.param}"
    app_registry_data = _register_hello_world_app(url)
    apps_path = Path(aiidalab.config.AIIDALAB_APPS)
    yield AiidaLabApp('hello-world', app_registry_data, apps_path, watch=False)


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
