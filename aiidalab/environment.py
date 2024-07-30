"""App environment specification

The specification is used to describe a reproducible environment for a
specific app, similar to the Reproducible Environment Specification (REES) [1]

[1] https://repo2docker.readthedocs.io/en/latest/specification.html

The following configuration files are recognized with the order of precedence
matching the order shown here:

.. glossary::

    setup.cfg
        Requirements listed as part of the [options]/install_requires field are
        parsed as pip-installable Python requirements for this app.

    requirements.txt
        Requirements listed within this file are parsed as pip-installable
        Python requirements for this app unless already parsed from the
        setup.cfg file.

"""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator

from .git_util import GitPath

__all__ = [
    "Environment",
]


@dataclass
class Environment:
    """App environment specification.

    This dataclass contains the specification of an app environment and can be
    used to scan an existing environment configuration from a given path and to
    detect whether a given environment is meeting the specification.
    """

    # TODO: The type should be list[Requirement], so that we parse only once.
    python_requirements: list[str] = field(default_factory=list)

    @staticmethod
    def _scan(path: Path | GitPath) -> Generator[Any, None, None]:
        def _parse_reqs(requirements: str) -> Generator[str, None, None]:
            for line in (line.strip() for line in requirements.splitlines()):
                if line and not line.startswith("#"):
                    yield line

        def _parse_setup_cfg(setup_cfg: str) -> Any:
            cfg = ConfigParser()
            cfg.read_string(setup_cfg)
            return cfg["options"].get("install_requires", None)

        # Parse the setup.cfg file (if present).
        try:
            yield (
                "python_requirements",
                list(
                    _parse_reqs(
                        _parse_setup_cfg(path.joinpath("setup.cfg").read_text())
                    )
                ),
            )
        except (FileNotFoundError, KeyError):
            # Parse the requirements.txt file (if present).
            try:
                yield (
                    "python_requirements",
                    list(_parse_reqs(path.joinpath("requirements.txt").read_text())),
                )
            except FileNotFoundError:
                pass

    @classmethod
    def scan(cls, root: Path | GitPath) -> Environment:
        """Scan the root path and determine the environment specification."""
        return cls(**dict(cls._scan(root)))
