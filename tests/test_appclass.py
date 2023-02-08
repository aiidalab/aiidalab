import aiida
import pytest
from packaging import version

from aiidalab.app import AiidaLabApp


def test_init_refresh(generate_app):
    app = generate_app()
    assert len(app.available_versions) == 0
    # After refresh the availale_versions traitslet is updated
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
    assert app.strict_dependencies_validation is False

    app.version_to_install = "v22.11.1"
    assert app.strict_dependencies_validation is True


# The data for test purpose as fixture
@pytest.fixture
def generate_app():
    """Fixture to construct a new AiiDALabApp instance for testing."""

    def _generate_app(
        name="quantum-espresso",
        aiidalab_apps_path="/home/jovyan/apps",
        app_data=None,
        watch=False,
    ):
        if app_data is None:
            app_data = EXAMPLE_APP_REGISTRY_ENTRY

        app = AiidaLabApp(name, app_data, aiidalab_apps_path, watch=False)

        return app

    return _generate_app


EXAMPLE_APP_REGISTRY_ENTRY = {
    "releases": {
        "v22.11.0": {
            "environment": {
                "python_requirements": [
                    "Jinja2~=2.11.3",
                    "aiida-core~=1.0",
                    "aiida-quantumespresso~=3.5",
                    "aiidalab-qe-workchain@https://github.com/aiidalab/aiidalab-qe/releases/download/v22.11.0/aiidalab_qe_workchain-22.11.0-py3-none-any.whl",
                    "aiidalab-widgets-base~=1.4.1",
                    "filelock~=3.3.0",
                    "importlib-resources~=5.2.2",
                    "widget-bandsplot~=0.2.8",
                ]
            },
            "metadata": {
                "title": "Quantum ESPRESSO",
                "description": "Perform Quantum ESPRESSO calculations",
                "authors": "Carl Simon Adorf, Aliaksandr Yakutovich, Marnik Bercx, Jusong Yu",
                "state": "registered",
                "documentation_url": "https://github.com/aiidalab/aiidalab-qe#readme",
                "external_url": "https://github.com/aiidalab/aiidalab-qe",
                "logo": "https://raw.githubusercontent.com/aiidalab/aiidalab-qe/master/miscellaneous/logos/QE.jpg",
                "categories": ["quantum"],
                "version": "22.11.0",
            },
            "url": "git+https://github.com/aiidalab/aiidalab-qe.git@d608f3a02f109b34a1088b6eca47223125168d14",
        },
        "v22.11.1": {
            "environment": {
                "python_requirements": [
                    "Jinja2~=3.0",
                    "aiida-core~=2.1",
                    "aiida-quantumespresso~=4.1",
                    "aiidalab-qe-workchain@https://github.com/aiidalab/aiidalab-qe/releases/download/v22.12.0/aiidalab_qe_workchain-22.12.0-py3-none-any.whl",
                    "aiidalab-widgets-base==2.0.0b0",
                    "filelock~=3.8",
                    "importlib-resources~=5.2.2",
                    "numpy~=1.23",
                    "widget-bandsplot~=0.5.0",
                ]
            },
            "metadata": {
                "title": "Quantum ESPRESSO",
                "description": "Perform Quantum ESPRESSO calculations",
                "authors": "Carl Simon Adorf, Aliaksandr Yakutovich, Marnik Bercx, Jusong Yu",
                "state": "registered",
                "documentation_url": "https://github.com/aiidalab/aiidalab-qe#readme",
                "external_url": "https://github.com/aiidalab/aiidalab-qe",
                "logo": "https://raw.githubusercontent.com/aiidalab/aiidalab-qe/master/miscellaneous/logos/QE.jpg",
                "categories": ["quantum"],
                "version": "22.12.0",
            },
            "url": "git+https://github.com/aiidalab/aiidalab-qe.git@58463d34ac143fa76be410ba3ff409968d938828",
        },
        "v23.01.0b1": {
            "environment": {
                "python_requirements": [
                    "Jinja2~=3.0",
                    "aiida-core>=2.1,<3",
                    "aiida-quantumespresso~=4.1",
                    "aiidalab-qe-workchain@https://github.com/aiidalab/aiidalab-qe/releases/download/v23.01.0b1/aiidalab_qe_workchain-23.1.0b1-py3-none-any.whl",
                    "aiidalab-widgets-base==2.0.0b1",
                    "filelock~=3.8",
                    "importlib-resources~=5.2.2",
                    "widget-bandsplot~=0.5.0",
                ]
            },
            "metadata": {
                "title": "Quantum ESPRESSO",
                "description": "Perform Quantum ESPRESSO calculations",
                "authors": "Carl Simon Adorf, Aliaksandr Yakutovich, Marnik Bercx, Jusong Yu",
                "state": "registered",
                "documentation_url": "https://github.com/aiidalab/aiidalab-qe#readme",
                "external_url": "https://github.com/aiidalab/aiidalab-qe",
                "logo": "https://raw.githubusercontent.com/aiidalab/aiidalab-qe/master/miscellaneous/logos/QE.jpg",
                "categories": ["quantum"],
                "version": "23.1.0b1",
            },
            "url": "git+https://github.com/aiidalab/aiidalab-qe.git@d89b58390c0a691bf16dfaa50036bc290fca017c",
        },
    },
    "name": "quantum-espresso",
    "metadata": {
        "title": "Quantum ESPRESSO",
        "description": "Perform Quantum ESPRESSO calculations",
        "authors": "Carl Simon Adorf, Aliaksandr Yakutovich, Marnik Bercx, Jusong Yu",
        "state": "registered",
        "documentation_url": "https://github.com/aiidalab/aiidalab-qe#readme",
        "external_url": "https://github.com/aiidalab/aiidalab-qe",
        "logo": "https://raw.githubusercontent.com/aiidalab/aiidalab-qe/master/miscellaneous/logos/QE.jpg",
        "categories": ["quantum"],
        "version": "23.1.0",
    },
}
