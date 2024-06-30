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

    assert result.exit_code == 0
    assert (
        __version__ in result.output.strip()
    ), "Version number should match library version."


def test_list_no_apps(aiidalab_env):
    """
    Smoke test for `aiidalab list` with no installed apps.
    """
    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(cli.cli, ["list"])

    assert result.exit_code == 0
    assert "No apps installed" in result.output


def test_install_no_apps():
    """
    Smoke test for `aiidalab install` with no apps to install.
    """
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["install", "--dry-run"])

    assert result.exit_code == 0
    assert "Nothing to install" in result.output


def test_uninstall_no_apps():
    """
    Smoke test for `aiidalab uninstall` with no apps to uninstall.
    """
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["uninstall", "--dry-run"])

    assert result.exit_code == 0
    assert "Nothing to uninstall" in result.output


def test_info_default():
    """
    Test `aiidalab info` with default environment values.
    """
    from aiidalab.config import AIIDALAB_APPS, AIIDALAB_REGISTRY

    runner = CliRunner()
    result = runner.invoke(cli.cli, ["info"])

    assert result.exit_code == 0
    assert AIIDALAB_REGISTRY in result.output
    assert AIIDALAB_APPS in result.output


def test_info_from_envvars(aiidalab_env):
    """
    Test `aiidalab info` with custom environment values.
    """

    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(cli.cli, ["info"])

    assert result.exit_code == 0
    assert aiidalab_env["AIIDALAB_REGISTRY"] in result.output
    assert aiidalab_env["AIIDALAB_APPS"] in result.output


def test_registry_build(tmp_path, aiidalab_env, apps_path, categories_path):
    """
    Test `registry build` - API endpoint only.
    """
    build_dir = tmp_path / "build"
    api_dir = build_dir / "api" / "v100"
    apps_dir = api_dir / "apps"
    index_file = api_dir / "apps_index.json"

    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(
        cli.cli,
        [
            "registry",
            "build",
            "--mock-schemas-endpoints",
            "--out",
            build_dir,
            "--apps",
            apps_path,
            "--categories",
            categories_path,
            "--html-path",
            "''",
            "--api-path",
            "api/v100",
        ],
    )

    assert result.output == ""
    assert result.exit_code == 0
    assert api_dir.is_dir()
    assert apps_dir.is_dir()
    assert index_file.is_file()
