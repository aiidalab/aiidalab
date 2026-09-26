"""
Tests for AiidaLabApp._has_python_package / _get_python_pkg_name / _uninstall_python_package.
"""

from __future__ import annotations

import io
import logging

import pytest

import aiidalab.utils
from aiidalab.app import _AiidaLabApp

PYTHON_BIN = "/usr/bin/python3"


def make_app(path, name="my-app"):
    """Build an app instance without going through the real __init__."""
    app = _AiidaLabApp(path=path, name=name, metadata={})
    return app


class FakeProcess:
    """Stand-in for the subprocess.Popen-like object run_pip_uninstall returns."""

    def __init__(self, stdout_bytes: bytes = b"", returncode: int = 0):
        self.stdout = io.BytesIO(stdout_bytes)
        self.returncode = returncode
        self.wait_called = False

    def wait(self):
        self.wait_called = True


@pytest.fixture(autouse=True)
def _capture_logs(caplog):
    caplog.set_level(logging.INFO)
    return caplog


class TestHasPythonPackage:
    def test_false_when_neither_file_present(self, tmp_path):
        app = make_app(tmp_path)
        assert app._has_python_package() is False

    def test_true_when_setup_py_present(self, tmp_path):
        (tmp_path / "setup.py").write_text("")
        app = make_app(tmp_path)
        assert app._has_python_package() is True

    def test_true_when_pyproject_toml_present(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("")
        app = make_app(tmp_path)
        assert app._has_python_package() is True

    def test_true_when_both_present(self, tmp_path):
        (tmp_path / "setup.py").write_text("")
        (tmp_path / "pyproject.toml").write_text("")
        app = make_app(tmp_path)
        assert app._has_python_package() is True


class TestGetPythonPkgName:
    def test_empty_string_when_no_python_package(self, tmp_path):
        app = make_app(tmp_path, name="whatever")
        assert app._get_python_pkg_name() == ""

    def test_falls_back_to_app_name_when_no_setup_cfg(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("")
        app = make_app(tmp_path, name="My_App")
        assert app._get_python_pkg_name() == "my-app"

    def test_setup_cfg_name(self, tmp_path):
        (tmp_path / "setup.py").write_text("")
        (tmp_path / "setup.cfg").write_text(
            "[metadata]\nname = totally-different-package\n"
        )
        app = make_app(tmp_path, name="my-app")
        assert app._get_python_pkg_name() == "totally-different-package"


class TestUninstallPythonPackage:
    def test_noop_when_no_python_package(self, tmp_path, monkeypatch):
        called = []
        monkeypatch.setattr(
            aiidalab.utils, "run_pip_uninstall", lambda *a, **kw: called.append((a, kw))
        )
        app = make_app(tmp_path, name="my-app")
        app._uninstall_python_package(PYTHON_BIN)
        assert called == []

    @pytest.mark.parametrize(
        "awb_name", ["aiidalab-widgets-base", "aiidalab_widgets_base"]
    )
    def test_awb_is_never_uninstalled(self, tmp_path, monkeypatch, caplog, awb_name):
        (tmp_path / "setup.py").write_text("")
        called = []
        monkeypatch.setattr(
            aiidalab.utils, "run_pip_uninstall", lambda *a, **kw: called.append((a, kw))
        )
        app = make_app(tmp_path, name=awb_name)
        app._uninstall_python_package(PYTHON_BIN)
        assert called == []
        assert "Keeping aiidalab-widgets-base python package installed" in caplog.text

    def test_waits_on_process_and_logs_stdout(self, tmp_path, monkeypatch, caplog):
        (tmp_path / "setup.py").write_text("")
        fake_process = FakeProcess(stdout_bytes=b"line one\nline two\n", returncode=0)
        monkeypatch.setattr(
            aiidalab.utils, "run_pip_uninstall", lambda *a, **kw: fake_process
        )
        app = make_app(tmp_path, name="my-app")
        app._uninstall_python_package(PYTHON_BIN)

        assert fake_process.wait_called is True
        assert "line one" in caplog.text
        assert "line two" in caplog.text
        assert "pip failed to uninstall" not in caplog.text

    def test_logs_failure_message_on_nonzero_returncode(
        self, tmp_path, monkeypatch, caplog
    ):
        (tmp_path / "setup.py").write_text("")
        fake_process = FakeProcess(stdout_bytes=b"", returncode=1)
        monkeypatch.setattr(
            aiidalab.utils, "run_pip_uninstall", lambda *a, **kw: fake_process
        )
        app = make_app(tmp_path, name="my-app")
        app._uninstall_python_package(PYTHON_BIN)

        assert "Running 'pip uninstall my-app'" in caplog.text
        assert "pip failed to uninstall python package my-app" in caplog.text
