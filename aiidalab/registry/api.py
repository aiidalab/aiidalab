# -*- coding: utf-8 -*-
"""Generate API endpoints."""
import json

from .apps_index import validate_apps_index_and_apps


def build_api_v1(base_path, apps_index, apps_data, scan_app_repository):
    """Build tree for API endpoint v1."""

    # Create base path if necessary.
    base_path.mkdir(parents=True, exist_ok=True)

    # Write apps_index.json file.
    outfile = base_path / "apps_index.json"
    rendered = json.dumps(apps_index, ensure_ascii=False)
    outfile.write_text(rendered, encoding="utf-8")
    yield outfile

    base_path.joinpath("apps").mkdir(exist_ok=True)
    for app_id, app_data in apps_data.items():
        # Write apps/{appId}.json
        outfile = base_path / "apps" / f"{app_id}.json"
        rendered = json.dumps(app_data, ensure_ascii=False)
        outfile.write_text(rendered, encoding="utf-8")
        yield outfile


def validate_api_v1(base_path, schemas):
    """Validate tree for API endpoint v1."""
    apps_index = json.loads(base_path.joinpath("apps_index.json").read_text())
    apps = [
        json.loads(base_path.joinpath("apps", f"{app_id}.json").read_text())
        for app_id in apps_index["apps"]
    ]
    validate_apps_index_and_apps(
        apps_index,
        apps_index_schema=schemas.apps_index,
        apps=apps,
        app_schema=schemas.app,
    )