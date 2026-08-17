"""App metadata specification"""

from __future__ import annotations

from collections.abc import Generator
from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from typing_extensions import Required, TypedDict

if TYPE_CHECKING:
    from configparser import SectionProxy

    from .git_util import GitPath

__all__ = [
    "Metadata",
]


def _map_development_state(classifiers: str | list[str]) -> str:
    "Map standard trove classifiers (PEP 301) to aiidalab development states."
    if "Development Status :: 1 - Planning" in classifiers:
        return "registered"
    elif "Development Status :: 5 - Production/Stable" in classifiers:
        return "stable"
    elif any(
        classifier in classifiers
        for classifier in (
            "Development Status :: 2 - Pre-Alpha",
            "Development Status :: 3 - Alpha",
            "Development Status :: 4 - Beta",
        )
    ):
        return "development"
    else:
        return "registered"


def _parse_config_dict(dict_: str) -> Generator[tuple[str, str], None, None]:
    "Parse a config dict string for key-values pairs."
    for line in dict_.splitlines():
        if line:
            key, value = line.split("=")
            yield key.strip(), value.strip()


def _parse_setup_cfg(
    setup_cfg: str,
) -> Generator[tuple[str, str | list[str]], None, None]:
    "Parse a setup.cfg configuration file string for metadata."
    import json

    cfg = ConfigParser()
    cfg.read_string(setup_cfg)

    metadata_pep426: SectionProxy | dict[Any, Any] = (
        cfg["metadata"] if "metadata" in cfg else {}  # noqa: SIM401
    )
    aiidalab: SectionProxy | dict[Any, Any] = (
        cfg["aiidalab"] if "aiidalab" in cfg else {}  # noqa: SIM401
    )

    yield "title", aiidalab.get("title", metadata_pep426.get("name", ""))
    yield "version", aiidalab.get("version", metadata_pep426.get("version", ""))
    yield (
        "description",
        aiidalab.get("description", metadata_pep426.get("description", "")),
    )
    yield "authors", aiidalab.get("authors", metadata_pep426.get("author", ""))
    yield "external_url", aiidalab.get("external_url", metadata_pep426.get("url", ""))

    project_urls = dict(_parse_config_dict(metadata_pep426.get("project_urls", "")))
    yield (
        "documentation_url",
        aiidalab.get(
            "documentation_url",
            project_urls.get("Documentation") or project_urls.get("documentation", ""),
        ),
    )
    yield (
        "logo",
        aiidalab.get("logo", project_urls.get("Logo") or project_urls.get("logo", "")),
    )
    yield (
        "state",
        aiidalab.get(
            "state", _map_development_state(metadata_pep426.get("classifiers", ""))
        ),
    )

    # Allow passing single category and convert to list
    # and allow parse line separated string as list
    categories = aiidalab.get("categories", "")
    if isinstance(categories, str):
        categories = [c for c in categories.split("\n") if c]
    yield "categories", categories

    citations = aiidalab.get("citations", metadata_pep426.get("citations"))
    try:
        yield "citations", json.loads(str(citations))
    except json.JSONDecodeError:
        yield "citations", []


@dataclass
class SimpleCitation:
    """App citation specification for free-form text with an optional link."""

    text: str
    link: str | None = None


@dataclass
class StandardCitation:
    """App citation specification for structured metadata."""

    authors: list[str]
    journal: str
    year: str
    doi: str
    title: str | None = None
    issue: str | None = None
    volume: str | None = None
    pages: str | None = None


@dataclass
class Metadata:
    """App metadata specification.

    If you add any fields here, also update them in MetadataDict below.
    """

    title: str
    description: str
    authors: str | None = None
    state: str | None = None
    documentation_url: str | None = None
    external_url: str | None = None
    logo: str | None = None
    categories: list[str] = field(default_factory=list)
    version: str | None = None
    citations: list[SimpleCitation | StandardCitation] = field(default_factory=list)

    _search_dirs = (".aiidalab", "./")

    @staticmethod
    def _parse(path: Path | GitPath) -> dict[str, Any]:
        try:
            return {
                key: value
                for key, value in _parse_setup_cfg(
                    path.joinpath("setup.cfg").read_text()
                )
                if value is not None
            }
        except FileNotFoundError:
            return {}

    @classmethod
    def parse(cls, root: Path | GitPath) -> Metadata:
        """Parse the app metadata from a setup.cfg within the app repository.

        This function will parse metadata fields from a possible "aiidalab"
        section, but falls back to the standard fields defined as part of the
        PEP 426-compliant metadata section for any missing values.
        """
        for path in (root.joinpath(dir_) for dir_ in cls._search_dirs):
            if path.is_dir():
                return cls(**dict(cls._parse(path)))

        raise ValueError(f"Directory '{root}' does not exist.")


class MetadataDict(TypedDict, total=False):
    """TypedDict for app metadata, basically a copy of Metadata dataclass."""

    title: Required[str]
    description: Required[str]
    authors: str | None
    state: str | None
    documentation_url: str | None
    external_url: str | None
    logo: str | None
    categories: list[str]
    version: str | None
    citations: list[dict[str, Any]] | None
