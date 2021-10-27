# -*- coding: utf-8 -*-
"""Module that implements a basic command line interface (CLI) for AiiDAlab."""
import json
import logging
import shutil
from collections import defaultdict
from contextlib import contextmanager, nullcontext
from dataclasses import asdict
from fnmatch import fnmatch
from pathlib import Path
from textwrap import indent, wrap

import click
import pkg_resources
import requests_mock
from click_spinner import spinner
from jsonref import JsonRefError
from jsonschema.exceptions import RefResolutionError, ValidationError
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import parse
from tabulate import tabulate

from . import __version__
from .app import AppVersion
from .app import _AiidaLabApp as AiidaLabApp
from .config import AIIDALAB_APPS, AIIDALAB_REGISTRY
from .fetch import fetch_from_url
from .metadata import Metadata
from .registry import build as build_registry
from .utils import PEP508CompliantUrl, load_app_registry_index
from .utils import parse_app_repo as _parse_app_repo

SCHEMAS_CANONICAL_BASE_URL = "https://raw.githubusercontent.com/aiidalab/aiidalab/v21.10.0/aiidalab/registry/schemas"


ICON_DETACHED = "\U000025AC"  # ▬
ICON_MODIFIED = "\U00002022"  # •


@contextmanager
def _spinner_with_message(message, message_final="Done.\n", **kwargs):
    try:
        click.echo(message, err=True, nl=False)
        with spinner():
            yield
    except Exception:
        click.echo()  # create new line
        raise
    else:
        click.echo(message_final, err=True)


def _list_apps(apps_path):
    if apps_path.is_dir():
        for path in apps_path.iterdir():
            if path.is_dir():
                if path.stem.startswith(".") or path.stem == "__pycache__":
                    continue  # exclude hidden directories and the Python cache directory.
                app_name = str(path.relative_to(apps_path))
                try:
                    yield path, app_name, AiidaLabApp.from_id(app_name)
                except KeyError:
                    yield path, app_name, None
    elif apps_path.exists():
        raise click.ClickException(
            f"The apps path ('{apps_path}') appears to not be a valid directory."
        )


@click.group()
@click.version_option(version=__version__, prog_name="AiiDAlab")
@click.option("-v", "--verbose", count=True)
def cli(verbose):
    logging.basicConfig(level=max(0, logging.WARNING - 10 * verbose))


@cli.command()
def info():
    """Show information about the AiiDAlab configuration."""
    click.echo(f"AiiDAlab, version {__version__}")
    click.echo(f"Apps path:      {Path(AIIDALAB_APPS).resolve()}")
    click.echo(f"Apps registry:  {AIIDALAB_REGISTRY}")


@cli.command()
@click.argument("app-query", default="*")
@click.option(
    "--pre",
    "prereleases",
    is_flag=True,
    # The default value for this flag is 'None', because we do not explicitly
    # _disallow_ prereleases when the option is not set, but it depends on the
    # provided requirement. That means when the query includes a prerelease
    # version (e.g. my-app>=1.0rc), then results will include prereleases,
    # whether this option is set or not. Otherwise, the results will only
    # include prereleases when this option is set.
    default=None,
    help="Include prereleases among the search candidates. Note: Prereleases "
    "are automatically included if an app has only prereleases.",
)
def search(app_query, prereleases):
    """Search for apps within the registry.

    Accepts either a search query with app names that contain wildcards ('*', '?')
    or a specific app requirement (e.g. 'hello-world>1.0').

    Examples:

    Find all apps where the name starts with "hello":

        search 'hello*'

    Find all apps with name "hello-world" with version greater or equal than 1.0:

        search 'hello-world>=1.0'

    """

    with _spinner_with_message("Collecting apps and releases... "):
        try:
            app_requirements = [Requirement(app_query)]
        except InvalidRequirement:  # interpreted as general search query
            try:
                registry = load_app_registry_index()
            except RuntimeError as error:
                raise click.ClickException(error)
            app_requirements = [
                Requirement(app_name)
                for app_name in registry["apps"].keys()
                if fnmatch(app_name, app_query)
            ]

    for app_requirement in app_requirements:
        try:
            app = AiidaLabApp.from_id(app_requirement.name)
        except KeyError:
            raise click.ClickException(
                f"Did not find entry for app with name '{app_requirement.name}'."
            )
        matching_releases = [
            version
            for version in app.find_matching_releases(
                app_requirement.specifier, prereleases
            )
        ]
        if matching_releases:
            click.echo(
                "\n".join(f"{app.name}=={version}" for version in matching_releases)
            )


def _tabulate_apps(apps, headers=("App name", "Version", "Path"), **kwargs):
    rows = []
    for app_path, app_name, app in sorted(apps):
        if app is None:
            version = ICON_DETACHED
        else:
            version = f"{app.installed_version()}{ICON_MODIFIED if app.dirty() else ''}"
        rows.append([app_name, version, str(app_path)])
    yield tabulate(rows, headers=headers, colalign=("left", "left", "left"), **kwargs)
    if rows:
        yield f"\n{ICON_DETACHED}:detached {ICON_MODIFIED}:modified"


@cli.command(name="list")
def list_apps():
    """List all installed apps.

    This command will list all apps, their version, and their full path.
    """

    apps = list(_list_apps(Path(AIIDALAB_APPS)))
    if len(apps) > 0:
        click.echo("\n".join(_tabulate_apps(apps)))
    else:
        click.echo("No apps installed.", err=True)


def _parse_requirement(app_requirement):
    try:
        return Requirement(app_requirement)
    except InvalidRequirement as error:
        from urllib.parse import urlsplit

        if urlsplit(app_requirement).scheme and "@" not in app_requirement:
            raise click.ClickException(
                "It looks like you tried to install directly from a PEP 508 "
                "compliant URL. Make sure to use the 'app-name @ url' syntax "
                "to provide a name for the app."
            )
        raise click.ClickException(
            f"Invalid requirement '{app_requirement}': {error!s}\n"
        )


def _find_registered_app_from_id(name):
    """Find app for a given requirement."""
    try:
        app = AiidaLabApp.from_id(name)
        if app.is_registered:
            return app
        else:
            raise click.ClickException(
                f"App '{app}' was installed locally and/or is not registered."
            )
    except KeyError:
        raise click.ClickException(f"Did not find entry for app with name '{name}'.")


def _find_app_and_releases(app_requirement):
    """Find app and a suitable release for a given requirement."""
    app = _find_registered_app_from_id(app_requirement.name)
    matching_releases = app.find_matching_releases(app_requirement.specifier)
    return app, matching_releases


@cli.command()
@click.argument("app-requirement", nargs=-1)
@click.option(
    "--indent", type=int, help="Specify level of identation of the JSON output."
)
def show_environment(app_requirement, indent):
    """Show environment specification of apps.

    Example:

    Show the environment specification for the latest version of the hello-world app:

        show-environment hello-world

    Show the combined environment for version 0.1.0 of the 'hello-world'
    app and 0.12-compatible release of 'other-app':

        show-environment hello-world==0.1.0 other-app~=0.12

    """

    with _spinner_with_message(
        "Collecting apps and their environment specifications... "
    ):
        apps_and_releases = {
            requirement: _find_app_and_releases(requirement)
            for requirement in map(_parse_requirement, app_requirement)
        }

    if not len(apps_and_releases):
        # We show a warning if no apps are selected, but we still show the JSON
        # environment specification. Less potential to break scripted pipelines
        # that might operate on zero or more selected apps.
        click.secho("No apps selected.", err=True, fg="yellow")

    aggregated_environment = defaultdict(list)
    for requirement, (app, selected_versions) in apps_and_releases.items():
        try:
            environment = app.releases[selected_versions[0]].get("environment")
        except IndexError:  # no matching release
            raise click.ClickException(
                f"{app.name}: No matching release for '{requirement.specifier}'. "
                f"Available releases: {','.join(map(str, sorted(map(parse, app.releases))))}"
            )
        else:
            click.echo(f"Selected '{app.name}=={selected_versions[0]}'", err=True)
            if environment:
                for key in environment:
                    aggregated_environment[key].extend(environment[key])
            else:
                click.secho(
                    f"No environment declared for '{app.name}'.",
                    fg="yellow",
                )

    click.echo(json.dumps(aggregated_environment, indent=indent))


def _find_version_to_install(
    app_requirement, force, dependencies, python_bin, prereleases
):
    if app_requirement.url is not None:
        with fetch_from_url(app_requirement.url) as repo:
            metadata = Metadata.parse(repo)
            registry_entry = dict(name=app_requirement.name, metadata=asdict(metadata))
            app = AiidaLabApp.from_id(
                app_requirement.name, registry_entry=registry_entry
            )
            if not (force or (dependencies in ("install", "ignore"))):
                raise click.ClickException(
                    f"Unable to check compatibility for {app_requirement} prior to installation."
                )

        if force or not app.is_installed():
            return app, PEP508CompliantUrl(app_requirement.url)
        else:
            return app, None

    app = _find_registered_app_from_id(app_requirement.name)

    assert dependencies in ("install", "require", "ignore")
    matching_releases = app.find_matching_releases(
        app_requirement.specifier, prereleases
    )
    compatible_releases = [
        version
        for version in matching_releases
        if force
        or (dependencies in ("install", "ignore"))
        or app.is_compatible(version, python_bin=python_bin)
    ]

    # Best case scenario: matching and compatible release found!
    if compatible_releases:
        version_to_install = compatible_releases[0]
        if force or version_to_install != app.installed_version():
            return app, version_to_install
        else:
            return app, None  # app already installed in that version

    # There are matching releases, but none are compatible, inform user.
    elif len(matching_releases) > 0:
        raise click.ClickException(
            f"There are releases matching '{app_requirement}' ("
            f"{','.join(map(str, sorted(map(parse, matching_releases))))}), however "
            "none of these are compatible with this environment."
        )

    # No matching releases, inform user about available releases.
    else:
        raise click.ClickException(
            f"No matching release for '{app_requirement}'. "
            f"Available releases: {','.join(map(str, sorted(map(parse, app.releases))))}"
        )


@cli.command()
@click.argument("app-requirement", nargs=-1)
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    help="Show what app (version) would be installed, but do not actually perform the installation.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Ignore all warnings and perform potentially dangerous operations anyways.",
)
@click.option(
    "-d",
    "--dependencies",
    type=click.Choice(["install", "require", "ignore"]),
    default="install",
    help="Select whether to install app dependencies (the default), "
    "require them to be installed prior to installation, "
    "or completely ignore them.",
    show_default=True,
)
@click.option(
    "--python",
    "python_bin",
    default=shutil.which("python"),
    type=click.Path(dir_okay=False, exists=True),
    help="The Python binary to use to install Python dependencies or to check their presence.",
    show_default=True,
)
@click.option(
    "--pre",
    "prereleases",
    is_flag=True,
    # The default value for this flag is 'None', because we do not explicitly
    # _disallow_ prereleases when the option is not set, but it depends on the
    # provided requirement. That means when the query includes a prerelease
    # version (e.g. my-app>=1.0rc), then the list of potential installation
    # candidates will include prereleases regardless of whether this option is
    # set or not.  Otherwise, prereleases are only considered when this option
    # is set.
    default=None,
    help="Include prereleases among the candidates for installation.",
)
def install(
    app_requirement, yes, dry_run, force, dependencies, python_bin, prereleases
):
    """Install apps.

    This command will install the latest version of an app matching the given requirement.

    Examples:

    Install the 'hello-world' app with the latest version that matches the specification '>=1.0':

        install hello-world>=1.0

    Install the 'hello-world' app directly with a PEP 508 compliant URL:

        install hello-world@git+https://github.com/aiidalab/aiidalab-hello-world.git

    Note: It is necessary to explicitly specify the app name before the '@'.
    """
    with _spinner_with_message("Collecting apps matching requirements... "):
        install_candidates = {
            requirement: _find_version_to_install(
                requirement,
                dependencies=dependencies,
                force=force,
                python_bin=python_bin,
                prereleases=prereleases,
            )
            for requirement in map(_parse_requirement, set(app_requirement))
        }

    if all(version is None for (_, version) in install_candidates.values()):
        click.echo("Nothing to install, exiting.", err=True)
        return

    elif any(version is None for (_, version) in install_candidates.values()):
        for requirement, (_, version) in install_candidates.items():
            if version is None:
                click.secho(
                    f"Requirement '{requirement}' already satisfied.",
                    err=True,
                    fg="yellow",
                )
        click.secho(
            "Use the '-f/--force' option to re-install anyways.\n",
            err=True,
            fg="yellow",
        )

    apps_table = tabulate(
        [
            [app.name, version, app.path]
            for _, (app, version) in install_candidates.items()
            if version is not None
        ],
        headers=["App", "Version", "Path"],
    )
    click.echo(f"Would install:\n\n{indent(apps_table, '  ')}\n")
    if yes or click.confirm("Proceed?", default=True):
        for app, version in install_candidates.values():
            if version is not None:
                if dry_run:
                    click.secho(
                        f"Would install '{app.name}' version '{version}'.", fg="green"
                    )
                else:
                    try:
                        app.install(
                            version=version,
                            install_dependencies=dependencies == "install",
                            python_bin=python_bin,
                        )
                    except RuntimeError as error:
                        click.secho(f"Error: {error}", fg="red")
                        break
                    else:
                        click.secho(
                            f"Installed '{app.name}' version '{version}'.", fg="green"
                        )


@cli.command()
@click.argument("app-name", nargs=-1)
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    help="Show what apps would be uninstalled, but do not actually perform the operation.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Ignore all warnings and perform potentially dangerous operations anyways.",
)
def uninstall(app_name, yes, dry_run, force):
    """Uninstall apps."""
    with _spinner_with_message("Collecting apps to uninstall... "):
        apps_to_uninstall = [
            (path, name, app)
            for (path, name, app) in _list_apps(Path(AIIDALAB_APPS))
            if any(fnmatch(name, app_name_) for app_name_ in app_name)
        ]

        # Determine whether some apps are dirty or detached.
        dirty = {
            name: (app is not None and app.dirty())
            for _, name, app in apps_to_uninstall
        }

        detached = {
            name: app is None or app.installed_version() is AppVersion.UNKNOWN
            for _, name, app in apps_to_uninstall
        }

    if not len(apps_to_uninstall):
        click.echo("Nothing to uninstall, exiting.", err=True)
        return

    apps_table = "\n".join(_tabulate_apps(apps_to_uninstall, tablefmt="simple"))
    click.echo(f"Would uninstall:\n\n{indent(apps_table, '  ')}\n")

    if any(dirty.values()):
        click.secho(
            "\n".join(
                wrap(
                    "WARNING: Some applications selected for removal have modifications "
                    "that would potentially be lost."
                )
            ),
            err=True,
            fg="yellow" if force else "red",
        )

    if any(detached.values()):
        click.secho(
            "\n".join(
                wrap(
                    "WARNING: Some applications selected for removal are detached, meaning they can "
                    "either not be found in the registry or are installed with unknown versions. "
                    "Their removal may lead to data loss."
                )
            ),
            err=True,
            fg="yellow" if force else "red",
        )

    potential_data_loss = any(dirty.values()) or any(detached.values())
    if potential_data_loss and not force:
        click.secho(
            "Use the -f/--force option to ignore all warnings.", err=True, fg="red"
        )
        raise click.Abort()

    if yes or click.confirm("Proceed?", default=not potential_data_loss):
        for app_path, _, app in apps_to_uninstall:
            if app is None:
                if dry_run:
                    click.secho(f"Would remove directory '{app_path!s}'.", err=True)
                else:
                    shutil.rmtree(app_path)
                    click.echo(f"Removed directory '{app_path!s}'.", err=True)
            else:
                if dry_run:
                    click.echo(
                        f"Would uninstall '{app.name}' ('{app.path!s}').", err=True
                    )
                else:
                    app.uninstall()
                    click.echo(
                        f"Uninstalled '{app.name}' ('{app.path!s}').",
                        err=True,
                    )


@contextmanager
def _mock_schemas_endpoints():
    schema_paths = [
        path
        for path in pkg_resources.resource_listdir(f"{__package__}.registry", "schemas")
        if path.endswith(".schema.json")
    ]

    with requests_mock.Mocker(real_http=True) as mocker:
        for schema_path in schema_paths:
            schema = json.loads(
                pkg_resources.resource_string(
                    f"{__package__}.registry", f"schemas/{schema_path}"
                )
            )
            mocker.get(
                schema.get("$id", f"{SCHEMAS_CANONICAL_BASE_URL}/{schema_path}"),
                text=json.dumps(schema),
            )
        yield


@cli.group()
def registry():
    """Functions related to managing an app registry."""


@registry.command()
@click.argument("url")
def parse_app_repo(url):
    """Parse an app repo for metadata and other information.

    Use this command to parse a local or remote app repository for the app
    metadata and environment specification.

    Examples:

    For a local app repository, provide the absolute or relative path:

        parse-app-repo /path/to/aiidalab-hello-world

    For a remote app repository, provide a PEP 508 compliant URL, for example:

        parse-app-repo git+https://github.com/aiidalab/aiidalab-hello-world.git@v1.0.0
    """
    click.echo(f"Parsing {url} ...", err=True)
    try:
        click.echo(json.dumps(_parse_app_repo(url)))
    except (ValueError, TypeError) as error:
        click.secho(
            f"Failed to parse metadata from '{url}': {error!s}",
            err=True,
            fg="red",
        )


@registry.command()
@click.option(
    "--apps",
    type=click.Path(exists=True, dir_okay=False),
    default="apps.yaml",
    help="Path to the registry's apps.yaml file.",
    show_default=True,
)
@click.option(
    "--categories",
    type=click.Path(exists=True, dir_okay=False),
    default="categories.yaml",
    help="Path to the registry's categories.yaml file.",
    show_default=True,
)
@click.option(
    "-o",
    "--out",
    type=click.Path(file_okay=False, writable=True),
    default="build/",
    show_default=True,
    help="Path to the base directory of where the registry's HTML and API pages are generated.",
)
@click.option(
    "--html-path",
    type=str,
    help="Relative path to the build directory at which the HTML pages are generated. "
    "Set to an empty value to skip the build of HTML pages entirely.",
    default=".",
    show_default=True,
)
@click.option(
    "--api-path",
    type=str,
    help="Relative path to the build directory at which the API pages are generated. "
    "Set to an empty value to skip the build of API pages entirely.",
    default="api/v1",
    show_default=True,
)
@click.option("--static", type=click.Path(file_okay=False, exists=True))
@click.option("-t", "--templates", type=click.Path(file_okay=False, exists=True))
@click.option(
    "--validate/--no-validate",
    is_flag=True,
    default=True,
    show_default=True,
    help="Validate inputs and outputs against the published or local schemas.",
)
@click.option(
    "-m",
    "--mock-schemas-endpoints",
    "mock_schemas",
    is_flag=True,
    help="Mock the schemas endpoints such that the local versions are used insted of the published ones.",
)
def build(
    apps,
    categories,
    out,
    html_path,
    api_path,
    static,
    templates,
    validate,
    mock_schemas,
):
    """Build the app store website and API endpoints.

    Example:

        build --apps=apps.yaml --categories=categories.yaml --out=./build/
    """
    if any(path and Path(path).is_absolute() for path in (html_path, api_path)):
        raise click.ClickException("The html- and api-paths must be relative paths.")

    maybe_mock = _mock_schemas_endpoints() if mock_schemas else nullcontext()
    with maybe_mock:
        try:
            build_registry(
                apps_path=Path(apps),
                categories_path=Path(categories),
                base_path=Path(out),
                html_path=Path(html_path) if html_path else None,
                api_path=Path(api_path) if api_path else None,
                static_path=Path(static) if static else None,
                templates_path=Path(templates) if templates else None,
                validate_output=validate,
                validate_input=validate,
            )
        except ValidationError as error:
            raise click.ClickException(f"Error during schema validation:\n{error}")
        except RefResolutionError as error:
            raise click.ClickException(
                f"Failed to resolve schema JSON reference: {error}\n\n"
                "Maybe try to run with `--mock-schemas-endpoints` ?"
            )
        except JsonRefError as error:
            raise click.ClickException(
                f"Failed to resolve JSON reference: {error.reference}\n{error.cause}"
            )


if __name__ == "__main__":
    cli()
