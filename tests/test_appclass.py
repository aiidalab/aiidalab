import pytest
import traitlets

from aiidalab.app import AiidaLabApp


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


def test_watch_deprecation(generate_app):
    with pytest.warns(DeprecationWarning):
        generate_app(watch=False)
