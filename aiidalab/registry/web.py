# -*- coding: utf-8 -*-
"""Generate the app registry website."""

import logging
import os
import shutil
from itertools import chain
from pathlib import Path

from ..utils import parse_app_repo
from . import api, yaml
from .apps_index import generate_apps_index
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

    apps_index, apps_data = generate_apps_index(
        data=data, scan_app_repository=parse_app_repo
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
        build_html(
            base_path=root,
            apps_index=apps_index,
            apps_data=apps_data,
        ),
        # Build the API endpoints.
        api.build_api_v1(
            base_path=root / "api" / "v1",
            apps_index=apps_index,
            apps_data=apps_data,
            scan_app_repository=parse_app_repo,
        ),
    ):
        logger.info(f"  - {outfile.relative_to(root)}")

    if validate_output:
        api.validate_api_v1(base_path=root / "api" / "v1", schemas=schemas)
