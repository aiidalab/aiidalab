"""Test the dataclass _AiidaLabApp.
We mock the app requirements and the medatada by a simple yaml file."""

import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from aiidalab.app import AppRemoteUpdateStatus, AppVersion, _AiidaLabApp


@pytest.fixture
def python_bin():
    """Return the path to the python executable."""
    return sys.executable


def test_core_dependencies_met_default(installed_packages, python_bin):
    """Test method _core_dependencies_met of _AiidaLabApp.
    Checking the requirements of the app against the core packages."""
    # the requirements are met
    requirements = [
        Requirement("aiida-core~=2.0"),
    ]

    assert _AiidaLabApp._core_dependencies_met(requirements, python_bin)

    # the requirements are not met
    requirements = [
        Requirement("aiida-core~=1.0"),
    ]

    assert not _AiidaLabApp._core_dependencies_met(requirements, python_bin)


def test_core_dependencies_met_package_name_canonicalized(
    installed_packages,
    python_bin,
):
    """Test method _core_dependencies_met of _AiidaLabApp for core packeges with
    name that is not canonicalized."""
    # the requirements are not met
    requirements = [
        Requirement("jupyter-client<6"),
    ]

    assert not _AiidaLabApp._core_dependencies_met(requirements, python_bin)


def test_invalid_requirements_skipped():
    """Test that invalid Python requirements are skipped."""
    app_data = _AiidaLabApp(
        metadata={},
        name="test",
        path=Path("test"),
        releases={
            "v1.0.0": {
                "environment": {
                    "python_requirements": [
                        "valid==2.0",
                        "invalid==1.0 # this comment makes this invalid",
                    ],
                },
                "metadata": {},
                "url": "",
            },
        },
    )
    all_reqs = app_data.releases["v1.0.0"]["environment"]["python_requirements"]
    assert len(all_reqs) == 2

    parsed_reqs = app_data.parse_python_requirements(all_reqs)
    assert len(parsed_reqs) == 1
    assert "valid" in parsed_reqs[0].name


def test_find_dependencies_to_install(monkeypatch, installed_packages, python_bin):
    """Test find_dependencies_to_install method of _AiidaLabApp.
    By mocking the _AiidallabApp class with its attributes set."""
    monkeypatch.setattr(_AiidaLabApp, "is_registered", lambda _: True)

    aiidalab_app_data = _AiidaLabApp(
        metadata={},
        name="test",
        path=Path("test"),
        releases={
            "stable": {
                "environment": {
                    "python_requirements": [
                        "aiida-core~=2.0",
                        "jupyter_client<6",  # this is not canonicalized and will be converted to jupyter-client
                    ],
                },
                "metadata": {},
                "url": "",
            },
            "v0.1.0": {
                "environment": {
                    "python_requirements": [
                        "aiida-core~=1.0",
                        "jupyter_client<6",  # this is not canonicalized
                    ],
                },
                "metadata": {},
                "url": "",
            },
        },
    )

    dependencies = aiidalab_app_data.find_dependencies_to_install("stable", python_bin)
    dependencies_name = [dep.get("installed").canonical_name for dep in dependencies]

    assert "aiida-core" not in dependencies_name
    assert "jupyter-client" in dependencies_name


def test_update_status_of_unregistred_app(
    monkeypatch, installed_packages, python_bin, tmp_path
):
    """Test default behaviour of an unregistred app."""
    # The app is installed in the path but the app name is not found from the registry.
    # This leads to the app being unregistred and the version will be read from the metadata.
    # If the version is not found in the metadata, the app is considered as `AppVersion.UNKNOWN`
    # The path need to be exist otherwise the app considered to be not installed, in the test
    # we monkeypatch in as installed.
    monkeypatch.setattr(_AiidaLabApp, "is_installed", lambda _: True)
    monkeypatch.setattr(_AiidaLabApp, "is_registered", lambda _: False)

    aiidalab_app_data = _AiidaLabApp(
        metadata={},
        name="test",
        path=tmp_path,
        releases={},
    )

    assert (
        aiidalab_app_data.remote_update_status() is AppRemoteUpdateStatus.NOT_REGISTERED
    )
    assert aiidalab_app_data.installed_version() is AppVersion.UNKNOWN


def test_update_status_latest_version_incompatible(
    monkeypatch, installed_packages, python_bin
):
    """Test issue #360 where when the highest version is core dependencies unmet and hidden."""
    monkeypatch.setattr(_AiidaLabApp, "is_registered", lambda _: True)
    monkeypatch.setattr(_AiidaLabApp, "is_installed", lambda _: True)
    monkeypatch.setattr(_AiidaLabApp, "installed_version", lambda _: "v0.1.0")

    aiidalab_app_data = _AiidaLabApp(
        metadata={},
        name="test",
        path=Path("test"),
        releases={
            "v0.2.0": {
                "environment": {
                    "python_requirements": [
                        "aiida-core~=3.0",  # where the core is not compatible so the version is hidden
                    ],
                },
                "metadata": {},
                "url": "",
            },
            "v0.1.0": {  # installed version where the aiida-core compatible
                "environment": {
                    "python_requirements": [
                        "aiida-core~=2.0",
                    ],
                },
                "metadata": {},
                "url": "",
            },
        },
    )

    assert aiidalab_app_data.remote_update_status() is AppRemoteUpdateStatus.UP_TO_DATE


@pytest.mark.parametrize(
    ("installed_version", "expected"),
    [
        ("v0.1.0", AppRemoteUpdateStatus.UPDATE_AVAILABLE),
        ("0.1.5", AppRemoteUpdateStatus.UPDATE_AVAILABLE),
        ("v0.2.0", AppRemoteUpdateStatus.UP_TO_DATE),
        ("0.3.0", AppRemoteUpdateStatus.UP_TO_DATE),
        ("0.3.0b1", AppRemoteUpdateStatus.UP_TO_DATE),
        ("my-release-1", AppRemoteUpdateStatus.UPDATE_AVAILABLE),
    ],
)
def test_update_status_compares_versions(
    monkeypatch, installed_packages, installed_version, expected
):
    """An update is only available if the installed version is older than the latest release."""
    monkeypatch.setattr(_AiidaLabApp, "is_registered", lambda _: True)
    monkeypatch.setattr(_AiidaLabApp, "is_installed", lambda _: True)
    monkeypatch.setattr(_AiidaLabApp, "installed_version", lambda _: installed_version)
    release = {"environment": {}, "metadata": {}, "url": ""}

    aiidalab_app_data = _AiidaLabApp(
        metadata={},
        name="test",
        path=Path("test"),
        releases={"v0.2.0": release, "v0.1.0": release},
    )

    assert aiidalab_app_data.remote_update_status() is expected


def test_compatibility_check_with_local_repo_if_detached(
    monkeypatch, tmp_path, installed_packages
):
    """Test compatibility check with local repo if detached."""
    from aiidalab.environment import Environment

    monkeypatch.setattr(_AiidaLabApp, "is_installed", lambda _: True)
    monkeypatch.setattr(_AiidaLabApp, "is_registered", lambda _: True)

    aiidalab_app_data = _AiidaLabApp(
        metadata={},
        name="test",
        path=tmp_path,
        releases={},
    )

    assert aiidalab_app_data.installed_version() is AppVersion.UNKNOWN
    assert aiidalab_app_data.is_detached()

    # test to show the code path that the local repo requirements check is hinted.
    # because the Environment.scan method is used for check the compatibility of local repo.

    # monkeypatch the scan method to return a fake environment
    # the fake environment has the aiida-core version that is compatible with the app
    monkeypatch.setattr(
        Environment,
        "scan",
        lambda _: Environment(python_requirements=["aiida-core~=2.0"]),
    )
    assert len(list(aiidalab_app_data.find_incompatibilities("v0.1.0"))) == 0

    # the fake environment has the aiida-core version that is not compatible with the app
    monkeypatch.setattr(
        Environment,
        "scan",
        lambda _: Environment(python_requirements=["aiida-core~=3.0"]),
    )
    assert len(list(aiidalab_app_data.find_incompatibilities("v0.1.0"))) == 1


def test_find_incompatibilities_python_skips_inapplicable_markers(
    installed_packages, python_bin
):
    """A missing package is not an incompatibility if its marker does not apply."""
    requirements = [
        Requirement("not-installed-package; sys_platform == 'no-such-platform'"),
        Requirement("not-installed-package-2; sys_platform != 'no-such-platform'"),
    ]

    incompatibilities = list(
        _AiidaLabApp._find_incompatibilities_python(requirements, python_bin)
    )

    assert [req.name for req in incompatibilities] == ["not-installed-package-2"]


@pytest.fixture
def app_archive(tmp_path):
    """Return a function creating an app archive in the given format."""
    import shutil

    source = tmp_path / "source"
    (source / "app").mkdir(parents=True)
    (source / "app" / "start.py").write_text("print('hello')\n")

    def _app_archive(archive_format):
        return Path(
            shutil.make_archive(tmp_path / "app", archive_format, root_dir=source)
        )

    return _app_archive


def _archive_app(path, url):
    return _AiidaLabApp(
        metadata={},
        name="test",
        path=path,
        releases={"v1.0.0": {"metadata": {}, "url": url}},
    )


@pytest.mark.parametrize("archive_format", ["zip", "gztar", "tar"])
def test_install_from_local_archive(
    installed_packages, tmp_path, app_archive, archive_format
):
    app = _archive_app(tmp_path / "apps" / "test", str(app_archive(archive_format)))

    app.install("v1.0.0", install_dependencies=False, post_install_triggers=False)

    assert (app.path / "start.py").read_text() == "print('hello')\n"


@pytest.mark.parametrize("archive_format", ["zip", "gztar"])
def test_install_from_https_archive(
    monkeypatch, installed_packages, tmp_path, app_archive, archive_format
):
    from aiidalab import fetch

    content = app_archive(archive_format).read_bytes()
    requests_kwargs = []

    class Response:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    def fake_get(url, **kwargs):
        requests_kwargs.append(kwargs)
        return Response(content)

    monkeypatch.setattr(fetch.requests, "get", fake_get)
    app = _archive_app(tmp_path / "apps" / "test", "https://example.com/app-archive")

    app.install("v1.0.0", install_dependencies=False, post_install_triggers=False)

    assert (app.path / "start.py").read_text() == "print('hello')\n"
    assert requests_kwargs == [{"timeout": fetch.REQUESTS_TIMEOUT}]
