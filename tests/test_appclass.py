import sys
import threading
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import ClassVar

import pytest
import traitlets
from inline_snapshot import HasRepr, snapshot
from packaging.requirements import Requirement

from aiidalab.app import AiidaLabApp, AiidaLabAppWatch, AppVersion


def test_init_refresh(generate_app):
    app = generate_app()

    # App is being refreshed already in the `generate_app` fixture
    assert len(app.available_versions) != 0

    # Test that invalid versions are skipped
    assert "invalid_version" not in app.available_versions


def test_prereleases(generate_app):
    app = generate_app()

    # without prereleases (which is the default)
    assert app.has_prereleases
    assert app.include_prereleases is False
    assert "v23.01.0b1" not in app.available_versions
    assert len(app.available_versions) == 2

    # with prereleases
    app.include_prereleases = True
    assert "v23.01.0b1" in app.available_versions
    assert len(app.available_versions) == 3


def test_reinstall_app(generate_app, monkeypatch):
    app = generate_app()
    calls = []

    monkeypatch.setattr(
        app._app,
        "_install_dependencies",
        lambda python_bin, stdout: calls.append(("install", python_bin, stdout)),
    )
    monkeypatch.setattr(
        app._app,
        "_post_install_triggers",
        lambda: calls.append(("post_install",)),
    )
    stdout = object()

    app.reinstall_app(stdout=stdout)

    assert calls == [("install", sys.executable, stdout), ("post_install",)]


class TestAppCompatibility:
    app_data: ClassVar[dict] = {
        "metadata": {
            "authors": "Who Cares, Lorem von Ipsum et al",
            "categories": ["crazy_stuff"],
            "logo": "whatever.png",
            "title": "TestApp",
            "version": "1.0",
        },
        "name": "test-app",
        "releases": {
            "1.0": {
                "environment": {"python_requirements": []},
            },
        },
    }

    def set_python_requirements(self, python_reqs: list[str]) -> dict:
        app_data = deepcopy(self.app_data)
        app_data["releases"]["1.0"]["environment"]["python_requirements"] = python_reqs
        return app_data

    def test_app_without_python_reqs_is_compatible(self, generate_app):
        app = generate_app(app_data=self.app_data)
        assert list(app._app.available_versions()) == snapshot(["1.0"])
        assert app.compatibility_info == snapshot({"1.0": []})
        assert app.compatible

    def test_compatible_app(self, generate_app, installed_packages):
        # The installed packages fixture mocks the python environemnt to already "contain"
        # aiida-core and ipywidgets so the following reqs should be compatible
        app_data = self.set_python_requirements(["ipywidgets~=7.4", "aiida-core>=2.0"])

        app = generate_app(app_data=app_data)

        assert app.compatibility_info == snapshot({"1.0": []})
        assert list(app._app.find_dependencies_to_install("1.0")) == snapshot([])
        assert app.compatible

    def test_incompatible_app(self, generate_app):
        app_data = self.set_python_requirements(
            ["nonexistent-pkg==2.0", "another-invalid-pkg"]
        )

        app = generate_app(app_data=app_data)

        assert app.compatibility_info == snapshot(
            {"1.0": ["(python) nonexistent-pkg==2.0", "(python) another-invalid-pkg"]}
        )
        assert list(app._app.find_dependencies_to_install("1.0")) == snapshot(
            [
                {
                    "installed": None,
                    "required": HasRepr(
                        Requirement, "<Requirement('nonexistent-pkg==2.0')>"
                    ),
                },
                {
                    "installed": None,
                    "required": HasRepr(
                        Requirement, "<Requirement('another-invalid-pkg')>"
                    ),
                },
            ]
        )
        assert not app.compatible


@pytest.mark.usefixtures("installed_packages")
def test_dependencies(generate_app):
    app: AiidaLabApp = generate_app()

    # The version `v22.11.0` is incompatible while `v22.11.1` is compatible
    with pytest.raises(traitlets.TraitError):
        app.version_to_install = "v22.11.0"
    app.version_to_install = "v22.11.1"


@pytest.mark.usefixtures("installed_packages")
def test_app_is_not_registered(generate_app, monkeypatch, tmp_path):
    """test the app is not registered and the available versions are empty."""

    app = generate_app()
    # monkeypatch and make the app not registered
    monkeypatch.setattr(app._app, "is_registered", lambda: False)
    app.refresh()

    assert app.is_installed() is True

    # if the app is not registered, the version is read from the metadata of app installed
    # the available versions will be empty since the app is not registered
    assert app.installed_version == "23.1.0"
    assert len(app.available_versions) == 0


def test_empty_app_citations(generate_app):
    app = generate_app()
    assert app.citations == []


def test_app_watch(tmp_path):
    """Test the aiidalab app watch responsive to the app path changes."""

    @dataclass
    class DummyApp:
        path: Path
        x: int = 0

        def refresh_async(self):
            self.x += 1

    app = DummyApp(path=Path(tmp_path))
    app_watch = AiidaLabAppWatch(app)
    app_watch.start()

    # The observer is start in a thread so need to wait until it is alive
    while app_watch._observer is None or not app_watch._observer.is_alive():
        sleep(0.1)

    # Trigger action by file events
    # touch a file will trigger action 4 times: create and close file and two modifies of folder
    testfile = tmp_path / "test0"
    testfile.touch()

    # check the threating is working
    assert threading.active_count() > 1

    app_watch.stop()
    app_watch.join(timeout=5.0)

    # check the threating is stopped and joined
    assert threading.active_count() == 1

    assert app_watch.is_alive() is False
    assert app_watch._observer.is_alive() is False
    assert app.x == 4

    # The stop of watch monitor thread will trigger stop of observer's thread.
    # After the observer is stopped, file system events should no longer trigger `refresh_async`
    testfile = tmp_path / "test1"
    testfile.touch()

    assert app.x == 4


def test_app_version_compatibility(generate_app):
    """Test the version compatibility check.

    The registered versions are tag format (e.g., "v26.06.11"), whereas the app metadata version
    is of format 26.6.11. This leads to failed version comparisons. This is resolved by using the
    `packaging.version.Version` class to parse and compare versions correctly. However, since Git
    tags can be anything (e.g., "my-release-1"), we try/except the use of `Version`, defaulting to
    the raw string comparison if parsing fails.

    This test checks the various scenarios.
    """
    app = generate_app()

    assert app._app._versions_equal("v26.06.11", "26.6.11")
    assert app._app._versions_equal("26.06.11", "26.6.11")
    assert not app._app._versions_equal("v26.06.11", "26.6.12")

    assert app._app._versions_equal("my-release-1", "my-release-1")
    assert not app._app._versions_equal("my-release-1", "my-release-2")
    assert not app._app._versions_equal("my-release-1", "26.6.11")

    assert app._app._versions_equal(AppVersion.UNKNOWN, AppVersion.UNKNOWN)
    assert app._app._versions_equal(AppVersion.NOT_INSTALLED, AppVersion.NOT_INSTALLED)

    assert not app._app._versions_equal(AppVersion.UNKNOWN, AppVersion.NOT_INSTALLED)
    assert not app._app._versions_equal(AppVersion.UNKNOWN, "26.6.11")
    assert not app._app._versions_equal("26.6.11", AppVersion.UNKNOWN)
