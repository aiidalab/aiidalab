# -*- coding: utf-8 -*-
"""Generate the app registry website."""

import logging
import os
import shutil
from copy import deepcopy
from itertools import chain
from pathlib import Path

from aiidalab.environment import Environment
from aiidalab.fetch import fetch_from_url
from aiidalab.metadata import Metadata

from . import api, yaml
from .core import AppRegistryData, AppRegistrySchemas
from .html import build_html

logger = logging.getLogger(__name__)


def copy_static_tree(base_path, static_src):
    for root, _, files in os.walk(static_src):
        # Create directory
        base_path.joinpath(Path(root).relative_to(static_src)).mkdir(
            parents=True, exist_ok=True
        )

        # Copy all files
        for filename in files:
            src = Path(root).joinpath(filename)
            dst = base_path.joinpath(Path(root).relative_to(static_src), filename)
            dst.write_bytes(src.read_bytes())
            yield dst


def build(
    apps_path: Path,
    categories_path: Path,
    html_path: Path,
    static_path: Path = None,
    validate_output: bool = True,
    validate_input: bool = False,
):
    """Build the app registry website (including schema files)."""

    # Parse the schemas shipped with the package.
    schemas = AppRegistrySchemas.from_package()

    # Parse the apps and categories data from the given paths.
    data = AppRegistryData(
        apps=yaml.load(apps_path),
        categories=yaml.load(categories_path),
    )
    if validate_input:
        data.validate(schemas)

    root = html_path

    # Remove previous build (if present) and re-create root directory.
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    # Prepare environment command
    def scan_app_repository(url):
        search_dirs = [".aiidalab/", "./"]
        with fetch_from_url(url) as repo:
            for path in (repo.joinpath(dir_) for dir_ in search_dirs):
                if path.is_dir():
                    try:
                        metadata = Metadata.parse(path)
                    except TypeError as error:
                        logger.debug(f"Failed to parse metadata for '{url}': {error}")
                        metadata = None
                    return dict(
                        environment=Environment.scan(path),
                        metadata=metadata,
                    )

    # Build the website and API endpoints.
    for outfile in chain(
        # Copy static files (if specified)
        (
            copy_static_tree(base_path=root, static_src=static_path)
            if static_path
            else ()
        ),
        # Build the html pages.
        build_html(base_path=root, data=deepcopy(data)),
        # Build the API endpoints.
        api.build_api_v1(
            base_path=root / "api" / "v1",
            data=deepcopy(data),
            scan_app_repository=scan_app_repository,
        ),
    ):
        logger.info(f"  - {outfile.relative_to(root)}")

    if validate_output:
        api.validate_api_v1(base_path=root / "api" / "v1", schemas=schemas)
