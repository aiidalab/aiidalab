"""Module to manage AiiDAlab configuration."""

from os import getenv
from pathlib import Path
from typing import Any, Optional

import click
import toml

CONFIG_PATH = Path.home() / "aiidalab.toml"
_CONFIG = toml.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.is_file() else {}
_DEVELOP_MODE = _CONFIG.get("develop", False)

if _DEVELOP_MODE:  # Warn developer that the mode is enabled.
    lines = [f"Executing '{__name__.split('.')[0]}' in DEVELOP mode."]
    config_ = {k: v for k, v in _CONFIG.items() if k != "develop"}
    if config_:  # The config does not only contain the 'develop' key.
        lines.append(f"{CONFIG_PATH!s} (takes precedence):")
        lines.extend(toml.dumps(config_).splitlines())
    click.secho("\n".join([f"\U0001f6a7  {line}" for line in lines]), fg="yellow")


def _as_env_var_name(key: str) -> str:
    return "AIIDALAB_" + key.upper()


def _get_config_value(key: str, default: Optional[str] = None) -> Any:
    """Return config value from configuration source.

    The standard configuration source order is:

        1. environment variables
        2. local configuration

    In 'develop' mode the order is reversed to simplify local
    override of configuration values.

    The convention for environment variables it to prefix keys
    with `AIIDALAB_` and to convert all letters to uppercase.
    For example, the configuration key `registry` is interpreted as
    `AIIDALAB_REGISTRY` when sourced as an environment variable.
    """
    if _DEVELOP_MODE:
        try:
            return _CONFIG[key]
        except KeyError:
            return getenv(_as_env_var_name(key), default)
    return getenv(_as_env_var_name(key), _CONFIG.get(key, default))


AIIDALAB_APPS = _get_config_value("apps", "/project/apps")
AIIDALAB_REGISTRY = _get_config_value(
    "registry", "https://aiidalab.github.io/aiidalab-registry/api/v1"
)
# All the variables below are currently not used.
# The README in the aiidalab-home home app states that AIIDALAB_HOME
# is searched for SSH credentials, but that doesn't seem to be the case.
AIIDALAB_HOME = _get_config_value("home", "/project")
AIIDALAB_SCRIPTS = _get_config_value("scripts", "/opt")
AIIDALAB_DEFAULT_GIT_BRANCH = _get_config_value("default_git_branch", "master")
