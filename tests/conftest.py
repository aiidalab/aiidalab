import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML


@pytest.fixture(scope="session")
def static_path():
    return Path(__file__).parent.absolute() / "static"


@pytest.fixture(scope="session")
def apps_path(static_path):
    return static_path / "apps.yaml"


@pytest.fixture(scope="session")
def categories_path(static_path):
    return static_path / "categories.yaml"


@pytest.fixture(scope="session")
def app_registry_path(static_path):
    return static_path / "app_registry.yaml"


@pytest.fixture
def generate_app(monkeypatch, app_registry_path):
    """Fixture to construct a new AiiDALabApp instance for testing."""

    def _generate_app(
        name="quantum-espresso",
        aiidalab_apps_path="/tmp/apps",
        app_data=None,
        watch=False,
        registered=True,
    ):
        from aiidalab.app import AiidaLabApp, _AiidaLabApp

        if app_data is None:
            safe_yaml = YAML(typ="safe")
            with app_registry_path.open() as f:
                app_data = safe_yaml.load(f)

        # In the app_registry.yaml we defined the metadata which means
        # it is a installed app. Following monkeypatch make it more close
        # to the real scenario for test.
        monkeypatch.setattr(_AiidaLabApp, "is_installed", lambda _: True)
        app = AiidaLabApp(
            name, app_data, aiidalab_apps_path, watch=watch, registered=registered
        )

        return app

    return _generate_app


_MONKEYPATCHED_INSTALLED_PACKAGES = [
    {"name": "aiida-core", "version": "2.2.1"},
    {"name": "jupyter_client", "version": "7.3.5"},
]


@pytest.fixture(autouse=True, scope="function")
def forbid_external_commands(monkeypatch):
    """Don't allow running external commands such as `pip install` during tests.

    Patch utils.run_* functions and raise an error if anybody tries to call it.
    """

    # Can't use lambda to raise an exception
    def raise_exc(msg=""):
        # NOTE: We use SystemExit which is derived from BaseException
        # so that this is not accidentally caught in the code.
        raise SystemExit(msg)

    monkeypatch.setattr(
        "aiidalab.utils.run_pip_install",
        lambda python_bin: raise_exc("Running `pip install` not allowed in tests!"),  # noqa: ARG005
    )

    monkeypatch.setattr(
        "aiidalab.utils.run_post_install_script",
        lambda _: raise_exc("Running `./post_install` not allowed in tests!"),
    )

    monkeypatch.setattr(
        "aiidalab.utils.run_verdi_daemon_restart",
        lambda: raise_exc("Running `verdi daemon restart` not allowed in tests!"),
    )

    monkeypatch.setattr(
        "aiidalab.utils.load_app_registry_index",
        lambda: raise_exc("Fetching registry index not allowed in tests!"),
    )

    monkeypatch.setattr(
        "aiidalab.utils.load_app_registry_entry",
        lambda _: raise_exc("Fetching app registry entry not allowed in tests!"),
    )


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
    if "aiidalab.config" in sys.modules:
        del sys.modules["aiidalab.config"]

    return {
        "AIIDALAB_REGISTRY": str(app_registry_path),
        "AIIDALAB_APPS": str(tmp_path),
    }
