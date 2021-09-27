# -*- coding: utf-8 -*-
"""Generate the app registry website."""

import logging
import os
import os.path
from itertools import chain
from pathlib import Path

import pkg_resources

from ..utils import parse_app_repo
from . import api, yaml
from .apps_index import generate_apps_index
from .core import AppRegistryData, AppRegistrySchemas
from .html import build_html

logger = logging.getLogger(__name__)


def copy_static_tree_from_path(base_path, static_path):

    for root, _, files in os.walk(static_path):
        # Create directory
        base_path.joinpath(Path(root).relative_to(static_path)).mkdir(
            parents=True, exist_ok=True
        )

        # Copy all files
        for filename in files:
            src = Path(root).joinpath(filename)
            dst = base_path.joinpath(Path(root).relative_to(static_path), filename)
            dst.write_bytes(src.read_bytes())
            yield dst


def _walk_pkg_resources(package, root):
    paths = pkg_resources.resource_listdir(package, root)
    for path in paths:
        dir_paths = [
            path
            for path in paths
            if pkg_resources.resource_isdir(package, os.path.join(root, path))
        ]
        yield root, list(set(paths).difference(dir_paths))
        for dir_path in dir_paths:
            yield from _walk_pkg_resources(package, os.path.join(root, dir_path))


def copy_static_tree_from_package(html_path, root="static"):
    for directory, files in _walk_pkg_resources(__package__, root):
        stem = html_path.joinpath(Path(directory).relative_to(root))
        stem.mkdir(parents=True, exist_ok=True)
        for fn in files:
            src = pkg_resources.resource_stream(
                __package__, os.path.join(directory, fn)
            )
            dst = stem.joinpath(fn)
            dst.write_bytes(src.read())
            yield dst


def build(
    apps_path: Path,
    categories_path: Path,
    base_path: Path,
    html_path: Path,
    api_path: Path,
    static_path: Path = None,
    templates_path: Path = None,
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

    # Scan previous build (if present) and re-create the base directory.
    logger.info("Scanning current directory...")
    previous_paths = list(base_path.glob("**/*"))
    base_path.mkdir(parents=True, exist_ok=True)

    apps_index, apps_data = generate_apps_index(
        data=data, scan_app_repository=parse_app_repo
    )

    # Build the website and API endpoints.
    new_paths = list()
    for outfile in chain(
        # Copy static files from package
        copy_static_tree_from_package(html_path=base_path / html_path),
        # Copy static files (if specified)
        copy_static_tree_from_path(base_path / html_path, static_path)
        if static_path
        else (),
        # Build the html pages.
        build_html(
            base_path=base_path / html_path,
            apps_index=apps_index,
            apps_data=apps_data,
            templates_path=templates_path,
        ),
        # Build the API endpoints.
        api.build_api_v1(
            api_path=base_path / api_path,
            apps_index=apps_index,
            apps_data=apps_data,
            scan_app_repository=parse_app_repo,
        ),
    ):
        new_paths.append(outfile)
        logger.info(f"  - {outfile.relative_to(base_path)}")

    # Remove all obsolete files:
    for path in set(previous_paths).difference(new_paths):
        if path.is_file():
            logger.info(f"  - rm {path.relative_to(base_path)}")
            path.unlink()

    # Remove all obsolete directories:
    previous_dirs = {path for path in previous_paths if path.is_dir()}
    current_dirs = {parent for path in new_paths for parent in path.parents}
    for path in previous_dirs.difference(current_dirs):
        logger.info(f"  - rmdir {path.relative_to(base_path)}")
        path.rmdir()

    if validate_output:
        api.validate_api_v1(api_path=base_path / api_path, schemas=schemas)
