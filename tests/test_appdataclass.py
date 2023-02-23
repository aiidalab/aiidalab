"""Test the dataclass _AiidaLabApp.
We mock the app requirements and the medatada by a simple yaml file."""
import sys

import pytest

from aiidalab import utils
from aiidalab.app import _AiidaLabApp
from aiidalab.utils import Package

_MONKEYPATCHED_INSTALLED_PACKAGES = {
    "aiida-core": Package("aiida-core", "2.2.1"),
    "jupyter_client": Package("jupyter_client", "7.3.5"),
}


@pytest.fixture
def python_bin():
    """Return the path to the python executable."""
    return sys.executable


def test_strict_dependencies_met_default(monkeypatch, python_bin):
    """Test method _strict_dependencies_met of _AiidaLabApp.
    Checking the requirements of the app against the core packages."""
    monkeypatch.setattr(
        utils, "find_installed_packages", lambda _: _MONKEYPATCHED_INSTALLED_PACKAGES
    )

    # the requirements are met
    requirements = [
        "aiida-core~=2.0",
    ]

    assert _AiidaLabApp._strict_dependencies_met(requirements, python_bin)

    # the requirements are not met
    requirements = [
        "aiida-core~=1.0",
    ]

    assert not _AiidaLabApp._strict_dependencies_met(requirements, python_bin)


def test_strict_dependencies_met_package_name_canoticalized(monkeypatch, python_bin):
    """Test method _strict_dependencies_met of _AiidaLabApp for core packeges with
    name that is not canonicalized."""
    monkeypatch.setattr(
        utils, "find_installed_packages", lambda _: _MONKEYPATCHED_INSTALLED_PACKAGES
    )

    # the requirements are not met
    requirements = [
        "jupyter-client<6",
    ]

    assert not _AiidaLabApp._strict_dependencies_met(requirements, python_bin)
