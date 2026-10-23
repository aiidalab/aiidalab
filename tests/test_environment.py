from textwrap import dedent

import pytest

from aiidalab.environment import Environment

SETUP_CFG = dedent(
    """
    [metadata]
    name = my-app

    [options]
    install_requires =
        aiida-core~=2.0
        numpy>=1.20
    """
)

PYPROJECT_TOML = dedent(
    """
    [project]
    name = "my-app"
    dependencies = ["aiida-core~=2.1", "scipy"]
    """
)


def test_no_config_files(tmp_path):
    assert Environment.scan(tmp_path) == Environment(python_requirements=[])


class TestSetupCfg:
    def test_install_requires(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text(SETUP_CFG)
        env = Environment.scan(tmp_path)
        assert env.python_requirements == ["aiida-core~=2.0", "numpy>=1.20"]

    def test_single_line_install_requires(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text(
            "[options]\ninstall_requires = aiida-core~=2.0\n"
        )
        env = Environment.scan(tmp_path)
        assert env.python_requirements == ["aiida-core~=2.0"]

    def test_comments_and_blank_lines_are_ignored(self, tmp_path):
        setup_cfg = dedent(
            """
            [options]
            install_requires =
                # a comment
                aiida-core~=2.0

                numpy
            """
        )
        tmp_path.joinpath("setup.cfg").write_text(setup_cfg)
        env = Environment.scan(tmp_path)
        assert env.python_requirements == ["aiida-core~=2.0", "numpy"]

    @pytest.mark.parametrize(
        "setup_cfg",
        [
            "",
            "[metadata]\nname = my-app\n",
            "[options]\npackages = find:\n",
            "[options]\ninstall_requires =\n",
        ],
    )
    def test_no_install_requires(self, tmp_path, setup_cfg):
        tmp_path.joinpath("setup.cfg").write_text(setup_cfg)
        assert Environment.scan(tmp_path).python_requirements == []

    def test_takes_precedence_over_other_files(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text(SETUP_CFG)
        tmp_path.joinpath("pyproject.toml").write_text(PYPROJECT_TOML)
        env = Environment.scan(tmp_path)
        assert env.python_requirements == ["aiida-core~=2.0", "numpy>=1.20"]

    def test_takes_precedence_even_without_install_requires(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text("[metadata]\nname = my-app\n")
        tmp_path.joinpath("pyproject.toml").write_text(PYPROJECT_TOML)
        assert Environment.scan(tmp_path).python_requirements == []

    def test_malformed_setup_cfg_logs_error(self, tmp_path, caplog):
        tmp_path.joinpath("setup.cfg").write_text("install_requires = numpy")
        assert Environment.scan(tmp_path).python_requirements == []
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse setup.cfg")


class TestPyprojectToml:
    def test_dependencies(self, tmp_path, caplog):
        tmp_path.joinpath("pyproject.toml").write_text(PYPROJECT_TOML)
        env = Environment.scan(tmp_path)
        assert env.python_requirements == ["aiida-core~=2.1", "scipy"]
        assert caplog.text == ""

    @pytest.mark.parametrize(
        "pyproject_toml",
        [
            "",
            "[tool.ruff]\nline-length = 88\n",
            '[project]\nname = "my-app"\n',
            "[project]\ndependencies = []\n",
        ],
    )
    def test_no_dependencies(self, tmp_path, caplog, pyproject_toml):
        tmp_path.joinpath("pyproject.toml").write_text(pyproject_toml)
        assert Environment.scan(tmp_path).python_requirements == []
        assert caplog.text == ""

    def test_dynamic_dependencies_warn(self, tmp_path, caplog):
        pyproject_toml = dedent(
            """
            [project]
            name = "my-app"
            dynamic = ["dependencies"]

            [tool.setuptools.dynamic]
            dependencies = {file = ["requirements.txt"]}
            """
        )
        tmp_path.joinpath("pyproject.toml").write_text(pyproject_toml)
        tmp_path.joinpath("requirements.txt").write_text("aiida-core~=2.2\nase\n")
        assert Environment.scan(tmp_path).python_requirements == []
        assert len(caplog.messages) == 1
        assert (
            "Dynamic dependencies in pyproject.toml are not supported"
            in (caplog.messages[0])
        )

    @pytest.mark.parametrize(
        "dependencies", ['"aiida-core"', "42", '{aiida-core = "~=2.0"}']
    )
    def test_dependencies_not_a_list(self, tmp_path, caplog, dependencies):
        tmp_path.joinpath("pyproject.toml").write_text(
            f"[project]\ndependencies = {dependencies}\n"
        )
        assert Environment.scan(tmp_path).python_requirements == []
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse dependencies")
        assert caplog.messages[0].endswith("ERROR: Expected a list")

    @pytest.mark.parametrize(
        "invalid_dependency", ["42", '{name = "numpy"}', '["numpy"]']
    )
    def test_invalid_dependency_is_skipped(self, tmp_path, caplog, invalid_dependency):
        tmp_path.joinpath("pyproject.toml").write_text(
            f'[project]\ndependencies = ["aiida-core", {invalid_dependency}, "ase"]\n'
        )
        assert Environment.scan(tmp_path).python_requirements == ["aiida-core", "ase"]
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse invalid dependency")
        assert caplog.messages[0].endswith("ERROR: Expected a string")

    def test_malformed_pyproject_toml_logs_error(self, tmp_path, caplog):
        tmp_path.joinpath("pyproject.toml").write_text("[project\ndependencies = []")
        assert Environment.scan(tmp_path).python_requirements == []
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse pyproject.toml")

    def test_project_not_a_table(self, tmp_path, caplog):
        tmp_path.joinpath("pyproject.toml").write_text('project = "my-app"\n')
        assert Environment.scan(tmp_path).python_requirements == []
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse project")
        assert caplog.messages[0].endswith("ERROR: Expected a table")
