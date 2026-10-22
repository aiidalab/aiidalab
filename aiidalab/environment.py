"""App environment specification

The specification is used to describe a reproducible environment for a
specific app, similar to the Reproducible Environment Specification (REES) [1]

[1] https://repo2docker.readthedocs.io/en/latest/specification.html

The following configuration files are recognized with the order of precedence
matching the order shown here. Only the first file found is parsed, i.e. if a
file exists, the files listed after it are ignored, even if it declares no
requirements.

.. glossary::

    setup.cfg
        Requirements listed as part of the [options]/install_requires field are
        parsed as pip-installable Python requirements for this app.

    pyproject.toml
        Requirements listed as part of the [project]/dependencies field are
        parsed as pip-installable Python requirements for this app.

    requirements.txt
        Requirements listed within this file are parsed as pip-installable
        Python requirements for this app.

"""

from __future__ import annotations

import logging
from collections.abc import Generator
from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path

import tomllib

from .git_util import GitPath

__all__ = [
    "Environment",
]

logger = logging.getLogger(__name__)


@dataclass
class Environment:
    """App environment specification.

    This dataclass contains the specification of an app environment and can be
    used to scan an existing environment configuration from a given path and to
    detect whether a given environment is meeting the specification.
    """

    python_requirements: list[str] = field(default_factory=list)

    @staticmethod
    def _scan(path: Path | GitPath) -> Generator[tuple[str, list[str]], None, None]:
        def _parse_reqs(requirements: str) -> Generator[str, None, None]:
            for line in (line.strip() for line in requirements.splitlines()):
                if line and not line.startswith("#"):
                    yield line

        def _parse_setup_cfg(setup_cfg: str) -> list[str]:
            cfg = ConfigParser()
            cfg.read_string(setup_cfg)
            if "options" not in cfg:
                return []
            return list(_parse_reqs(cfg["options"].get("install_requires", "")))

        def _parse_pyproject_toml(pyproject_toml: str) -> list[str]:
            project = tomllib.loads(pyproject_toml).get("project", {})
            if "dependencies" in project.get("dynamic", []):
                logger.warning(
                    "Dynamic dependencies in pyproject.toml are not supported, "
                    "declare them in the [project].dependencies field instead"
                )
            dependencies = project.get("dependencies", [])
            if not isinstance(dependencies, list):
                logger.error(
                    f"Could not parse dependencies:\n{dependencies}\n"
                    "ERROR: Expected a list"
                )
                return []

            requirements = []
            for dependency in dependencies:
                if not isinstance(dependency, str):
                    logger.error(
                        f"Could not parse invalid dependency\n{dependency}\n"
                        "ERROR: Expected a string"
                    )
                    continue
                requirements.append(dependency)
            return requirements

        # Only the first existing file is parsed, in order of precedence.
        try:
            setup_cfg = path.joinpath("setup.cfg").read_text()
        except FileNotFoundError:
            pass
        else:
            yield "python_requirements", _parse_setup_cfg(setup_cfg)
            return

        try:
            pyproject_toml = path.joinpath("pyproject.toml").read_text()
        except FileNotFoundError:
            pass
        else:
            yield "python_requirements", _parse_pyproject_toml(pyproject_toml)
            return

        try:
            requirements_txt = path.joinpath("requirements.txt").read_text()
        except FileNotFoundError:
            pass
        else:
            yield "python_requirements", list(_parse_reqs(requirements_txt))

    @classmethod
    def scan(cls, root: Path | GitPath) -> Environment:
        """Scan the root path and determine the environment specification."""
        return cls(**dict(cls._scan(root)))
