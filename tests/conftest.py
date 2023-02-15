from pathlib import Path

import pytest
import yaml

from aiidalab.app import AiidaLabApp


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
            with open(
                Path(__file__).parent.absolute() / "static/app_registry.yaml"
            ) as f:
                app_data = yaml.safe_load(f)
        app = AiidaLabApp(name, app_data, aiidalab_apps_path, watch=watch)

        return app

    return _generate_app
