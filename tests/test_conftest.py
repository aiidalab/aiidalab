"""Test fixtures defined in conftest.py"""

import pytest


def test_forbidden_functions():
    """Ensure that we fail if we try to run `pip install`
    and other functions that might influence global environment.
    """
    from aiidalab.utils import (
        load_app_registry_entry,
        load_app_registry_index,
        run_pip_install,
        run_post_install_script,
        run_verdi_daemon_restart,
    )

    with pytest.raises(SystemExit):
        process = run_pip_install(python_bin="python")
        process.wait()

    with pytest.raises(SystemExit):
        process = run_verdi_daemon_restart()
        process.wait()

    with pytest.raises(SystemExit):
        process = run_post_install_script("post_install")
        process.wait()

    with pytest.raises(SystemExit):
        load_app_registry_index()

    with pytest.raises(SystemExit):
        load_app_registry_entry("app")
