# -*- coding: utf-8 -*-
"""Module that implements a basic command line interface (CLI) for AiiDA lab."""

from pathlib import Path

import click
import dulwich
from tabulate import tabulate

from .app import AiidaLabApp
from .config import AIIDALAB_APPS
from .utils import load_app_registry


def _get_app_from_name(name):
    """Return the app instance from name."""
    apps = load_app_registry()['apps']
    app_data = apps.get(name)
    if app_data is None:
        click.secho(f"Did not find app '{name}' in app registry.", fg='yellow')
    return AiidaLabApp(name, app_data, AIIDALAB_APPS, watch=False)


def _get_app():
    """Return the app instance from the current working directory."""
    try:
        name = str(Path.cwd().relative_to(AIIDALAB_APPS))
        if name == '.':
            raise ValueError
    except ValueError:
        raise click.ClickException(f"The current directory is not a sub-directory of '{AIIDALAB_APPS}'.")

    try:
        return _get_app_from_name(name)
    except dulwich.errors.NotGitRepository:
        raise click.ClickException("The app directory must be a git repository.")


@click.group()
def cli():
    pass


@cli.command()
def status():
    """Show basic information about the app and the installation status."""
    app = _get_app()
    rows = list()
    rows.append(("AiiDA lab app", app.name))
    rows.append(("Version:", app.installed_version))

    environment_message = app.environment_message
    if environment_message:
        rows.append(("Environment:", click.style(environment_message, fg='red')))
    else:
        rows.append(
            ("Environment:",
             click.style(str(app.environment.prefix), fg='green') if app.environment.installed() else 'not required'))
    click.echo(tabulate(rows))


@cli.group()
def environment():
    """Manage the app's Python environment."""


@environment.command('install')
@click.option('--yes', is_flag=True, help="Do not ask for confirmation to replace existing environment.")
def install_environment(yes):
    """Install the app's environment.

    WARNING: Any previously existing environment will be replaced.
    """
    app = _get_app()

    # Check whether to replace existing environment, if present.
    if app.environment.installed() and not (yes or click.confirm("Replace existing environment?")):
        return

    try:

        for msg in app.install_environment():
            click.echo(msg)
    except RuntimeError as error:
        raise click.ClickException(str(error))


@environment.command('uninstall')
def uninstall_environment():
    """Uninstall the app's environment."""
    app = _get_app()
    if app.environment.installed():
        app.environment.uninstall()
        click.secho("Uninstalled environment.", fg='green')
    else:
        click.secho("No environment to uninstall.", fg='yellow')


if __name__ == '__main__':
    cli()
