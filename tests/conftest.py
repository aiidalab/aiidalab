import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from aiidalab.app import AiidaLabApp, _AiidaLabApp


@pytest.fixture(scope="session")
def app_registry_path():
    return Path(__file__).parent.absolute() / "static/app_registry.yaml"


@pytest.fixture
def generate_app(monkeypatch, app_registry_path):
    """Fixture to construct a new AiiDALabApp instance for testing."""

    def _generate_app(
        name="quantum-espresso",
        aiidalab_apps_path="/tmp/apps",
        app_data=None,
        watch=False,
    ):
        if app_data is None:
            safe_yaml = YAML(typ="safe")
            with app_registry_path.open() as f:
                app_data = safe_yaml.load(f)

        # In the app_registry.yaml we defined the metadata which means
        # it is a installed app. Following monkeypatch make it more close
        # to the real scenario for test.
        monkeypatch.setattr(_AiidaLabApp, "is_installed", lambda _: True)
        app = AiidaLabApp(name, app_data, aiidalab_apps_path, watch=watch)

        return app

    return _generate_app


_MONKEYPATCHED_INSTALLED_PACKAGES = [
    {"name": "aiida-core", "version": "2.2.1"},
    {"name": "jupyter_client", "version": "7.3.5"},
]


@pytest.fixture
def installed_packages(monkeypatch):
    """change the return of pip_list.
    This is to mimic the pip list command output, which returns a json string represent
    the list of installed packages."""
    from aiidalab.utils import FIND_INSTALLED_PACKAGES_CACHE

    FIND_INSTALLED_PACKAGES_CACHE.clear()  # clear the cache
    monkeypatch.setattr(
        "aiidalab.utils._pip_list",
        lambda _: _MONKEYPATCHED_INSTALLED_PACKAGES,
    )


@pytest.fixture
def aiidalab_env(tmp_path, app_registry_path):
    """Set AIIDALAB_APPS to tmp_path and set a file-based AIIDALAB_REGISTRY"""
    # This is needed so that the config module is imported again env vars are re-parsed
    del sys.modules["aiidalab.config"]

    return {
        "AIIDALAB_REGISTRY": str(app_registry_path),
        "AIIDALAB_APPS": str(tmp_path),
    }
