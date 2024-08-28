import threading
from dataclasses import dataclass
from pathlib import Path
from time import sleep

import pytest
import traitlets

from aiidalab.app import AiidaLabApp, AiidaLabAppWatch


def test_init_refresh(generate_app):
    app = generate_app()
    assert len(app.available_versions) == 0
    # After refresh the available_versions traitlet is updated
    app.refresh()
    assert len(app.available_versions) != 0

    # Test that invalid versions are skipped
    assert "invalid_version" not in app.available_versions


def test_prereleases(generate_app):
    app = generate_app()

    # without prereleases tick
    app.refresh()
    assert app.has_prereleases
    assert app.include_prereleases is False
    assert "v23.01.0b1" not in app.available_versions

    # tick prereleases tick
    app.include_prereleases = True
    assert "v23.01.0b1" in app.available_versions


@pytest.mark.usefixtures("installed_packages")
def test_dependencies(generate_app):
    app: AiidaLabApp = generate_app()
    app.refresh()

    # The version `v22.11.0` is incompatible while `v22.11.1` is compatible
    with pytest.raises(traitlets.TraitError):
        app.version_to_install = "v22.11.0"
    app.version_to_install = "v22.11.1"


@pytest.mark.usefixtures("installed_packages")
def test_app_is_not_registered(generate_app, monkeypatch, tmp_path):
    """test the app is not registered and the available versions are empty."""

    app: AiidaLabApp = generate_app()
    # monkeypatch and make the app not registered
    monkeypatch.setattr(app._app, "is_registered", lambda: False)
    app.refresh()

    assert app.is_installed() is True

    # if the app is not registered, the version is read from the metadata of app installed
    # the available versions will be empty since the app is not registered
    assert app.installed_version == "23.1.0"
    assert len(app.available_versions) == 0


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
