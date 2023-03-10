"""Test the dataclass _AiidaLabApp.
We mock the app requirements and the medatada by a simple yaml file."""
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from aiidalab.app import AppRemoteUpdateStatus, _AiidaLabApp


@pytest.fixture
def python_bin():
    """Return the path to the python executable."""
    return sys.executable


def test_strict_dependencies_met_default(installed_packages, python_bin):
    """Test method _strict_dependencies_met of _AiidaLabApp.
    Checking the requirements of the app against the core packages."""
    # the requirements are met
    requirements = [
        Requirement("aiida-core~=2.0"),
    ]

    assert _AiidaLabApp._strict_dependencies_met(requirements, python_bin)

    # the requirements are not met
    requirements = [
        Requirement("aiida-core~=1.0"),
    ]

    assert not _AiidaLabApp._strict_dependencies_met(requirements, python_bin)


def test_strict_dependencies_met_package_name_canonicalized(
    installed_packages,
    python_bin,
):
    """Test method _strict_dependencies_met of _AiidaLabApp for core packeges with
    name that is not canonicalized."""
    # the requirements are not met
    requirements = [
        Requirement("jupyter-client<6"),
    ]

    assert not _AiidaLabApp._strict_dependencies_met(requirements, python_bin)


def test_find_dependencies_to_install(monkeypatch, installed_packages, python_bin):
    """Test find_dependencies_to_install method of _AiidaLabApp.
    By mocking the _AiidallabApp class with its attributes set."""
    monkeypatch.setattr(_AiidaLabApp, "is_registered", True)

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


def test_update_status_issue_360(monkeypatch, installed_packages, python_bin):
    """Test issue #360 where when the highest version is core dependencies unmet and hidden."""
    monkeypatch.setattr(_AiidaLabApp, "is_registered", True)
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
