# -*- coding: utf-8 -*-
"""Module that implements a basic command line interface (CLI) for AiiDAlab."""

import json
import shutil
from collections import defaultdict
from contextlib import contextmanager
from fnmatch import fnmatch
from pathlib import Path
from textwrap import indent
from textwrap import wrap

import click
from click_spinner import spinner
from packaging.requirements import InvalidRequirement
from packaging.requirements import Requirement
from packaging.version import parse
from tabulate import tabulate

from . import __version__
from .app import AppVersion
from .app import _AiidaLabApp as AiidaLabApp
from .config import AIIDALAB_APPS
from .config import AIIDALAB_REGISTRY
from .utils import load_app_registry_index


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
def cli():
    pass


@cli.command()
def info():
    """Show information about the AiiDAlab configuration."""
    click.echo(f"AiiDAlab, version {__version__}")
    click.echo(f"Apps path:      {Path(AIIDALAB_APPS).resolve()}")
    click.echo(f"Apps registry:  {AIIDALAB_REGISTRY}")


@cli.command()
@click.argument("app-query", default="*")
def search(app_query):
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
            registry = load_app_registry_index()
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
            version for version in app.find_matching_releases(app_requirement.specifier)
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
        raise click.ClickException(
            f"Invalid requirement '{app_requirement}': {error!s}"
        )


def _find_app_from_id(name):
    """Find app for a given requirement."""
    try:
        return AiidaLabApp.from_id(name)
    except KeyError:
        raise click.ClickException(f"Did not find entry for app with name '{name}'.")


def _find_app_and_releases(app_requirement):
    """Find app and a suitable release for a given requirement."""
    app = _find_app_from_id(app_requirement.name)
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


def _find_version_to_install(app_requirement, app, force, python_bin):
    matching_releases = app.find_matching_releases(app_requirement.specifier)
    compatible_releases = [
        version
        for version in matching_releases
        if not python_bin or app.is_compatible(version, python_bin=python_bin)
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
    "--python",
    "python_bin",
    default="python",
    help="Specify the Python binary for which to check Python-dependencies for. "
    "Set this option to an empty string to skip the dependency check.",
    type=click.Path(dir_okay=False),
)
def install(app_requirement, yes, dry_run, force, python_bin):
    """Install apps.

    This command will install the latest version of an app matching the given requirement.

    Examples:

    Install the 'hello-world' app with the latest version that matches the specification '>=1.0':

        install hello-world>=1.0
    """

    with _spinner_with_message("Collecting apps matching requirements... "):
        install_candidates = {
            requirement: _find_version_to_install(
                requirement,
                _find_app_from_id(requirement.name),
                force=force,
                python_bin=python_bin,
            )
            for requirement in map(_parse_requirement, set(app_requirement))
        }

    if all(version is None for (_, version) in install_candidates.values()):
        click.echo("Nothing to install, exiting.", err=True)
        return

    elif any(version is None for (_, version) in install_candidates.values()):
        for requirement, (_, version) in sorted(install_candidates.items()):
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
            for _, (app, version) in sorted(install_candidates.items())
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
                    app.install(version=version)
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


if __name__ == "__main__":
    cli()
