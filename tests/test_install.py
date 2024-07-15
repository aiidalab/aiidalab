"""Test (un)installation of AiiDAlab applications"""

import pytest


def test_forbidden_functions():
    """Ensure that we fail if we try to run `pip install`
    and other functions that might influence global environment
    """
    from aiidalab.utils import (
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
