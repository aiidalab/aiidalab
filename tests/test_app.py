"""Tests for the aiidalab.app module."""
# pylint: disable=unused-argument,redefined-outer-name
import json
from pathlib import Path
from subprocess import run, CalledProcessError
from urllib.parse import urlsplit

import pytest

import aiidalab
from aiidalab.app import AiidaLabApp


def clone(source, target):
    """Git clone source at target."""
    run(['git', 'clone', str(source), str(target)], check=True)


@pytest.fixture
def empty_registry():
    return dict(apps=dict(), categories=dict())


HELLO_WORLD_APP_DIR = Path(__file__).parent.joinpath('data', 'aiidalab-hello-world').resolve()


@pytest.fixture
def hello_world_app(environment):
    """Return a AiidaLabApp fixture based on the hello-world-app."""
    # Clone the hello-world-app repository into a local path that will
    # serve as the "remote" origin.
    origin = Path(aiidalab.config.AIIDALAB_HOME).joinpath('local', 'aiidalab-hello-world').resolve()
    origin.parent.mkdir()
    try:
        clone(source=str(HELLO_WORLD_APP_DIR), target=str(origin))
    except CalledProcessError as error:
        pytest.skip(f"missing submodules to run this test: {error}")

    # Clone the app from origin into the apps/ folder.
    apps_path = Path(aiidalab.config.AIIDALAB_APPS)
    app_path = apps_path.joinpath('hello-world').resolve()
    clone(source=str(origin), target=str(app_path))

    # Register app in app registry
    app_data = json.loads(app_path.joinpath('metadata.json').read_text())
    app_registry_data = {
        "git_url": str(origin),
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

    # Finally, yield AiidaLabApp
    yield AiidaLabApp('hello-world', app_registry_data, apps_path, watch=False)


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
    yield


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
    assert Path(app.path).is_dir()
    assert app.is_installed()
    for key in 'authors', 'description', 'title':
        assert key in app.metadata
        assert getattr(app, key) == app.metadata[key]
    for key in 'logo', 'state', 'version':
        assert key in app.metadata
