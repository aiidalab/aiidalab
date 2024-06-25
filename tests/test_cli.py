import sys

# To learn more about testing Click applications see
# http://click.pocoo.org/5/testing/
from click.testing import CliRunner

import aiidalab.__main__ as cli
from aiidalab import __version__


def test_version_displays_library_version():
    """
    Run `aiidalab --version` and check the output matches the library version.
    """
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["--version"])
    assert (
        __version__ in result.output.strip()
    ), "Version number should match library version."


def test_list_no_apps(tmp_path):
    """
    Smoke test for `aiidalab list` with no installed apps.
    """
    env = {
        "AIIDALAB_APPS": str(tmp_path),
    }
    # This is needed so that the module is imported again env vars are re-parsed
    del sys.modules["aiidalab.config"]

    runner = CliRunner(env=env)
    result = runner.invoke(cli.cli, ["list"])

    assert "No apps installed" in result.output


def test_info_default():
    """
    Test `aiidalab info` with default environment values.
    """
    from aiidalab.config import AIIDALAB_APPS, AIIDALAB_REGISTRY

    runner = CliRunner()
    result = runner.invoke(cli.cli, ["info"])

    assert AIIDALAB_REGISTRY in result.output
    assert AIIDALAB_APPS in result.output


def test_info_from_envvars(monkeypatch):
    """
    Test `aiidalab info` with custom environment values.
    """
    env = {
        "AIIDALAB_REGISTRY": "spam_registry",
        "AIIDALAB_APPS": "/eggs/apps",
    }
    # This is needed so that the module is imported again env vars are re-parsed
    del sys.modules["aiidalab.config"]

    runner = CliRunner(env=env)
    result = runner.invoke(cli.cli, ["info"], env=env)

    assert env["AIIDALAB_REGISTRY"] in result.output
    assert env["AIIDALAB_APPS"] in result.output
