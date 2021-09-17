# -*- coding: utf-8 -*-
"""Generate the apps index including all aggregated metadata."""
import logging
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict

import jsonschema
from packaging.version import parse

from . import util
from .releases import gather_releases

logger = logging.getLogger(__name__)


def _determine_app_name(app_id):
    """Currently the app name is identical to its id."""
    assert util.get_html_app_fname(app_id) == f"{app_id}.html"
    return app_id


def _migrate_app_data(app_data):
    if "metadata" in app_data:
        # Set defaults
        app_data["metadata"].setdefault("categories", app_data.pop("categories", []))
        app_data["metadata"].setdefault("logo", app_data.pop("logo", None))

        # Remove deprecated keys from app metadata.
        for key in (
            "requires",
            "version",
        ):
            if key in app_data["metadata"]:
                del app_data["metadata"][key]


def _fetch_app_data(app_id, app_data, scan_app_repository):
    # Gather all release data.
    _migrate_app_data(app_data)

    app_data["name"] = _determine_app_name(app_id)
    app_data["releases"] = {
        version: asdict(release)
        for version, release in gather_releases(app_data, scan_app_repository)
    }
    return app_data


def generate_apps_index(data, scan_app_repository):
    """Generate the comprehensive app index.

    This index is built from the apps data and includes additional information
    such as the releases.
    """

    apps_data = OrderedDict()
    index = {
        "apps": OrderedDict(),
        "categories": data.categories,
    }
    logger.info("Fetching app data...")

    for app_id in sorted(data.apps.keys()):
        logger.info(f"  - {app_id}")
        apps_data[app_id] = _fetch_app_data(
            app_id, deepcopy(data.apps[app_id]), scan_app_repository
        )

        # Sort all releases semantically to determine the latest version.
        releases = sorted(apps_data[app_id]["releases"], key=parse, reverse=True)

        if len(releases):  # Only add app to index if it had at least one release.
            # Source the categories from the metadata of the latest release.
            app_metadata = apps_data[app_id]["releases"][releases[0]]["metadata"]

            index["apps"][app_id] = {
                "name": apps_data[app_id]["name"],
                "categories": app_metadata.get("categories", []),
            }

    return index, apps_data


def validate_apps_index_and_apps(apps_index, apps_index_schema, apps, app_schema):
    """Validate the apps_index file."""

    # Validate apps index against schema
    jsonschema.validate(instance=apps_index, schema=apps_index_schema)

    # Validate index categories
    for apps_index_entry in apps_index["apps"].values():
        for category in apps_index_entry["categories"]:
            assert category in apps_index["categories"]

    # Validate all apps
    for app in apps:
        jsonschema.validate(instance=app, schema=app_schema)
