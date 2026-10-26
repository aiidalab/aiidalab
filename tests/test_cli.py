import json
import tarfile
import zipfile
from pathlib import Path
from textwrap import dedent
from typing import Any, ClassVar

import pytest

# To learn more about testing Click applications see
# http://click.pocoo.org/5/testing/
from click.testing import CliRunner
from dulwich import porcelain

import aiidalab.__main__ as cli
from aiidalab import __version__


def test_version_displays_library_version():
    """
    Run `aiidalab --version` and check the output matches the library version.
    """
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output.strip(), (
        "Version number should match library version."
    )


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


def test_dry_install(aiidalab_env, static_path):
    """
    Test `aiidalab install --dry-run`.
    """
    app_path = static_path / "app_with_setupcfg"
    app = f"hello-world @ file://{app_path}"

    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(cli.cli, ["-v", "install", "--dry-run", "--yes", app])

    assert result.exit_code == 0, result.output
    assert "Would install" in result.output, result.output

    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(cli.cli, ["list"])

    assert result.exit_code == 0, result.output
    assert "No apps installed" in result.output, result.output


def test_install_uninstall(monkeypatch, aiidalab_env, static_path):
    """
    Test `aiidalab install` followed by `aiidalab uninstall`.
    """
    monkeypatch.setattr(
        "aiidalab.utils.load_app_registry_entry",
        lambda _: None,
    )

    aiidalab_apps = Path(aiidalab_env["AIIDALAB_APPS"])
    app_name = "hello-world"
    app_path = static_path / "app_with_setupcfg"
    app_req = f"{app_name} @ file://{app_path}"

    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(cli.cli, ["-v", "install", "--yes", app_req])

    assert result.exit_code == 0, result.output
    assert f"Installed '{app_name}'" in result.output, result.output

    installed_app = Path(aiidalab_apps / app_name)
    assert installed_app.is_dir()

    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(cli.cli, ["list"])

    assert result.exit_code == 0, result.output
    assert app_name in result.output, result.output

    runner = CliRunner(env=aiidalab_env)
    result = runner.invoke(
        cli.cli, ["-v", "uninstall", "--fully-remove", "--yes", app_name]
    )

    assert result.exit_code == 0, result.output
    assert f"Uninstalled '{app_name}'" in result.output, result.output

    assert not installed_app.exists()


@pytest.mark.registry
def test_registry_build_api(tmp_path, apps_path, categories_path):
    """
    Test `registry build` - API endpoint only.
    """
    build_dir = tmp_path / "build"
    api_dir = build_dir / "api" / "v100"
    apps_dir = api_dir / "apps"
    index_file = api_dir / "apps_index.json"

    runner = CliRunner()
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


@pytest.mark.registry
def test_registry_build_html(tmp_path, apps_path, categories_path):
    """
    Test `registry build` - HTML only.
    """
    build_dir = tmp_path / "build"
    api_dir = build_dir / "api"
    html_dir = build_dir / "html"

    runner = CliRunner()
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
            "html",
            "--api-path",
            "''",
        ],
    )

    assert result.output == ""
    assert result.exit_code == 0
    assert not api_dir.is_dir()
    assert html_dir.is_dir()


class TestRegistryParseAppRepo:
    """Tests for `aiidalab registry parse-app-repo`.

    Parsing of the setup.cfg contents itself is covered in test_metadata.py,
    here we test the CLI command and the handling of different URL types.
    """

    SETUP_CFG = dedent(
        """
        [aiidalab]
        title = Test App

        [metadata]
        version = 1.0.0

        [options]
        install_requires =
            numpy
            # comment
            aiida-core>=2.0
        """
    )

    EXPECTED_METADATA: ClassVar[dict[str, Any]] = {
        "title": "Test App",
        "description": "",
        "authors": "",
        "state": "registered",
        "documentation_url": "",
        "external_url": "",
        "logo": "",
        "categories": [],
        "version": "1.0.0",
        "citations": [],
    }

    EXPECTED_ENVIRONMENT: ClassVar[dict[str, list[str]]] = {
        "python_requirements": ["numpy", "aiida-core>=2.0"]
    }

    @staticmethod
    def invoke(url):
        # Click < 8.2 mixes stderr into stdout by default,
        # click >= 8.2 always captures them separately and removed `mix_stderr`.
        try:
            runner = CliRunner(mix_stderr=False)
        except TypeError:
            runner = CliRunner()
        return runner.invoke(cli.cli, ["registry", "parse-app-repo", str(url)])

    @pytest.fixture
    def app_dir(self, tmp_path):
        app = tmp_path / "app"
        app.mkdir()
        app.joinpath("setup.cfg").write_text(self.SETUP_CFG)
        return app

    def assert_parsed(self, result):
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.stdout)
        assert parsed == {
            "metadata": self.EXPECTED_METADATA,
            "environment": self.EXPECTED_ENVIRONMENT,
        }

    def test_static_app(self, static_path):
        """Parse a Hello World app defined in `tests/static/app_with_setupcfg/`"""
        app_path = static_path / "app_with_setupcfg"
        result = self.invoke(app_path)

        assert result.exit_code == 0, result.output
        assert result.stderr == f"Parsing '{app_path}'\n"
        parsed = json.loads(result.stdout)
        assert parsed["metadata"]["title"] == "Hello World"
        assert parsed["metadata"]["version"] == "0.1.1"
        assert parsed["metadata"]["authors"] == "AiiDAlab team"
        assert parsed["metadata"]["categories"] == ["quantum"]
        assert parsed["environment"] == {
            "python_requirements": [
                "pip",
                "pytest # This comment makes this requirement invalid",
            ]
        }

    def test_absolute_path(self, app_dir):
        self.assert_parsed(self.invoke(app_dir))

    def test_relative_path(self, app_dir, monkeypatch):
        monkeypatch.chdir(app_dir.parent)
        self.assert_parsed(self.invoke(app_dir.name))

    def test_file_url(self, app_dir):
        self.assert_parsed(self.invoke(f"file://{app_dir}"))

    @pytest.mark.parametrize("mode", ["w", "w:gz"])
    def test_tar_archive(self, app_dir, tmp_path, mode):
        archive = tmp_path / "app.tar"
        with tarfile.open(archive, mode) as tar:
            tar.add(app_dir, arcname="app")
        self.assert_parsed(self.invoke(archive))

    def test_zip_archive(self, app_dir, tmp_path):
        archive = tmp_path / "app.zip"
        with zipfile.ZipFile(archive, "w") as zip_file:
            zip_file.write(app_dir / "setup.cfg", arcname="app/setup.cfg")
        self.assert_parsed(self.invoke(archive))

    def test_git_local_repo(self, app_dir):
        repo = porcelain.init(str(app_dir))
        porcelain.add(repo, [str(app_dir / "setup.cfg")])
        porcelain.commit(repo, message=b"Initial commit")
        self.assert_parsed(self.invoke(f"git+file://{app_dir}"))

    def test_git_local_repo_at_tag(self, app_dir):
        repo = porcelain.init(str(app_dir))
        porcelain.add(repo, [str(app_dir / "setup.cfg")])
        porcelain.commit(repo, message=b"Initial commit")
        porcelain.tag_create(repo, b"v1.0.0")

        # Changes after the tag must not be visible
        app_dir.joinpath("setup.cfg").write_text("[aiidalab]\ntitle = Changed\n")
        porcelain.add(repo, [str(app_dir / "setup.cfg")])
        porcelain.commit(repo, message=b"Change title")

        self.assert_parsed(self.invoke(f"git+file://{app_dir}@v1.0.0"))

        result = self.invoke(f"git+file://{app_dir}")
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["metadata"]["title"] == "Changed"

    def test_empty_directory(self, tmp_path):
        result = self.invoke(tmp_path)

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {
            "metadata": None,
            "environment": {"python_requirements": []},
        }

    def assert_failed(self, result, url, message):
        assert result.exit_code == 1, result.output
        assert result.stdout == ""
        assert result.stderr.startswith(f"Parsing '{url}'\n")
        assert f"Error: Failed to parse metadata from '{url}': " in result.stderr
        assert message in result.stderr
        # No traceback, the error is handled by click
        assert isinstance(result.exception, SystemExit)

    def test_unsupported_scheme(self):
        url = "ftp://example.com/app.zip"
        result = self.invoke(url)
        self.assert_failed(result, url, "Unsupported scheme: ftp.")

    def test_nonexistent_path(self, tmp_path):
        url = tmp_path / "missing"
        result = self.invoke(url)
        self.assert_failed(result, url, "No such file or directory")

    def test_invalid_archive(self, tmp_path):
        url = tmp_path / "app.zip"
        url.write_text("not an archive")
        result = self.invoke(url)
        self.assert_failed(result, url, "Failed to extract archive from file.")

    def test_not_a_git_repo(self, tmp_path):
        url = f"git+file://{tmp_path}"
        result = self.invoke(url)
        self.assert_failed(result, url, "No git repository was found")

    @pytest.mark.parametrize(
        "setup_cfg,message",
        [
            ("title = no section header", "File contains no section headers."),
            ("[aiidalab]\ntitle = a\ntitle = b\n", "option 'title'"),
        ],
    )
    def test_malformed_setup_cfg(self, tmp_path, setup_cfg, message):
        tmp_path.joinpath("setup.cfg").write_text(setup_cfg)
        result = self.invoke(tmp_path)
        self.assert_failed(result, tmp_path, message)

    def test_missing_url_argument(self):
        runner = CliRunner()
        result = runner.invoke(cli.cli, ["registry", "parse-app-repo"])

        assert result.exit_code == 2
        assert "Missing argument 'URL'" in result.output
