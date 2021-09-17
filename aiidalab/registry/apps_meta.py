# -*- coding: utf-8 -*-
"""Generate the aggregated registry metadata from the registry data."""

import logging
import re
from collections import OrderedDict
from copy import deepcopy
from urllib.parse import urlsplit, urlunsplit

import jsonschema

from . import git_util, util

logger = logging.getLogger(__name__)


def generate_metainfo(app_name, metadata, git_url):
    """Generate the metainfo object from the app metadata."""
    metainfo = {
        key: metadata[key]
        for key in (
            "authors",
            "description",
            "documentation_url",
            "external_url",
            "requires",
            "state",
            "title",
            "version",
        )
        if key in metadata
    }

    metainfo.setdefault("state", "registered")
    metainfo.setdefault("title", app_name)
    metainfo.setdefault("authors", git_util.get_git_author(git_url))
    return metainfo


def extract_git_url_from_releases(releases):
    for release in releases:
        split = urlsplit(release if isinstance(release, str) else release["url"])
        if split.scheme == "git+https" and re.match(r".+?@(.*):", split.path):
            adjusted_path = re.sub("(.+?)@(.*):", r"\1#\2", split.path)
            return urlunsplit(split._replace(scheme="https", path=adjusted_path))
    raise ValueError("Unable to determine git_url!")


def fetch_app_data(app_data, app_name):
    """Fetch additional data for the given app data."""
    # Migrate categories and logo:
    app_data.setdefault("categories", app_data["metadata"].get("categories", []))
    app_data.setdefault("logo", app_data["metadata"].get("logo"))

    # Check if categories are specified, warn if not
    if "categories" not in app_data:
        logger.info("  >> WARNING: No categories specified.")
        app_data["categories"] = []

    # Get Git URL, fail build if git_url is not found or wrong
    app_data["git_url"] = extract_git_url_from_releases(app_data.pop("releases"))

    hosted_on = util.get_hosted_on(app_data["git_url"])
    if hosted_on:
        app_data["hosted_on"] = hosted_on
    app_data["gitinfo"] = git_util.get_git_branches(app_data["git_url"])

    app_data["metainfo"] = generate_metainfo(
        app_name, app_data.pop("metadata"), app_data["git_url"]
    )

    return deepcopy(app_data)


def validate_apps_meta(apps_meta, apps_meta_schema):
    """Validate the apps_meta file against the corresponding JSON-schema."""

    jsonschema.validate(instance=apps_meta, schema=apps_meta_schema)

    for appdata in apps_meta["apps"].values():
        for category in appdata["categories"]:
            assert category in apps_meta["categories"]


def generate_apps_meta(data):
    """Generate the comprehensive app registry index.

    This function produces the apps_meta file, a comprehensive metadata directory that
    combines the apps data and additionally fetched data (such as the git info).

    The apps_meta file can be used to generate the app registery website and if
    published online, by other platforms that want to operate on the app registry
    and, e.g., integrate with registered apps.
    """

    apps_meta = {
        "apps": OrderedDict(),
        "categories": data.categories,
    }
    logger.info("Fetching app data...")
    for app_id in sorted(data.apps.keys()):
        assert util.get_html_app_fname(app_id) == f"{app_id}.html"
        logger.info(f"  - {app_id}")
        app_data = fetch_app_data(data.apps[app_id], app_id)
        app_data["name"] = app_id
        app_data["subpage"] = f"apps/{app_id}/index.html"
        app_data["meta_url"] = ""
        apps_meta["apps"][app_id] = app_data

    return apps_meta
