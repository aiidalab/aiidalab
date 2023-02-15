import aiida
import pytest
from packaging import version

from aiidalab.app import AiidaLabApp


def test_init_refresh(generate_app):
    app = generate_app()
    assert len(app.available_versions) == 0
    # After refresh the availale_versions traitlets is updated
    app.refresh()
    assert len(app.available_versions) != 0


def test_prereleases(generate_app):
    app = generate_app()

    # without prereleases tick
    app.refresh()
    assert app.has_prereleases
    assert app.include_prereleases is False

    # tick prereleases tick
    app.include_prereleases = True
    assert "v23.01.0b1" in app.available_versions


@pytest.mark.skipif(
    version.parse(aiida.__version__).major != 2, reason="only pass for aiida 2.x"
)
def test_dependencies(generate_app):
    app: AiidaLabApp = generate_app()
    app.refresh()

    # The version `v22.11.0` is incompatible while `v22.11.1` is compatible
    app.version_to_install = "v22.11.0"
    assert app.strict_dependencies_satisfied is False

    app.version_to_install = "v22.11.1"
    assert app.strict_dependencies_satisfied is True
