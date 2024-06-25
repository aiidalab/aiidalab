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


def test_list_no_apps(aiidalab_env):
    """
    Smoke test for `aiidalab list` with no installed apps.
    """
    runner = CliRunner(env=aiidalab_env)
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


def test_info_from_envvars(aiidalab_env):
    """
    Test `aiidalab info` with custom environment values.
    """

    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(cli.cli, ["info"])

    assert aiidalab_env["AIIDALAB_REGISTRY"] in result.output
    assert aiidalab_env["AIIDALAB_APPS"] in result.output
