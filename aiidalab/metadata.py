"""App metadata specification"""

from __future__ import annotations

import logging
import string
from collections.abc import Generator
from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

import tomllib

if TYPE_CHECKING:
    from configparser import SectionProxy

    from .git_util import GitPath

__all__ = [
    "Metadata",
]

logger = logging.getLogger(__name__)


def _map_development_state(classifiers: str | list[str]) -> str:
    """Map standard trove classifiers (PEP 301) to aiidalab development states."""
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
    """Parse a config dict string for key-values pairs."""
    for line in dict_.splitlines():
        if line:
            key, value = line.split("=")
            yield key.strip(), value.strip()


_CitationType = dict[str, str | list[str] | None]


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


class MetadataDict(TypedDict):
    """TypedDict for app metadata, basically a copy of Metadata dataclass."""

    title: str
    description: str
    authors: str | None
    state: str | None
    documentation_url: str | None
    external_url: str | None
    logo: str | None
    categories: list[str]
    version: str | None
    citations: list[_CitationType]


def package_name_from_setup_cfg(setup_cfg: str) -> str:
    cfg = ConfigParser()
    cfg.read_string(setup_cfg)

    # This really shouldn't happen, setuptools would probably not be happy
    if not "metadata" in cfg:
        return ""

    metadata_pep426 = cfg["metadata"]
    return metadata_pep426.get("name", "")


def package_name_from_pyproject_toml(pyproject_toml: str) -> str:
    pyproject = tomllib.loads(pyproject_toml)
    metadata_pep621 = _get_toml_table(pyproject, "project", "")
    return _get_toml_str(metadata_pep621, "name", "project") or ""


def _get_toml_table(table: dict[str, Any], key: str, name: str) -> dict[str, Any]:
    "Get a sub-table from a parsed TOML table, logging an error if it is not a table."
    value = table.get(key, {})
    if not isinstance(value, dict):
        full_key = f"{name}.{key}" if name else key
        logger.error(f"Could not parse {full_key}:\n{value}\nERROR: Expected a table")
        return {}
    return value


def _get_toml_str(table: dict[str, Any], key: str, name: str) -> str | None:
    """Get a string value from a parsed TOML table.

    Returns None if the key is missing or (logging an error) if it is not a string.
    """
    if key not in table:
        return None
    value = table[key]
    if not isinstance(value, str):
        logger.error(
            f"Could not parse {name}.{key}:\n{value}\nERROR: Expected a string"
        )
        return None
    return value


def _get_toml_str_list(table: dict[str, Any], key: str, name: str) -> list[str]:
    "Get a list of strings from a parsed TOML table, dropping (and logging) invalid ones."
    values = table.get(key, [])
    if not isinstance(values, list):
        logger.error(f"Could not parse {name}.{key}:\n{values}\nERROR: Expected a list")
        return []

    strings = []
    for value in values:
        if not isinstance(value, str):
            logger.error(
                f"Could not parse invalid {name}.{key} entry\n{value}\n"
                "ERROR: Expected a string"
            )
            continue
        strings.append(value)
    return strings


def _validate_citations(citations_raw: Any) -> list[_CitationType]:
    "Validate a list of raw citation dicts, dropping (and logging) invalid ones."
    citations: list[_CitationType] = []
    if not isinstance(citations_raw, list):
        logger.error(
            f"Could not parse citations:\n{citations_raw}\nERROR: Expected a list"
        )
        return citations

    for cit in citations_raw:
        try:
            SimpleCitation(**cit)
        except (ValueError, TypeError):
            pass
        else:
            citations.append(cit)
            continue

        try:
            StandardCitation(**cit)
        except (ValueError, TypeError) as e:
            logger.error(f"Could not parse invalid citation\n{cit}\nERROR: {e}")
        else:
            citations.append(cit)

    return citations


def _parse_pep621_authors(authors_raw: Any) -> str:
    "Join PEP 621 authors (a list of tables with name and/or email) into a string."
    if not isinstance(authors_raw, list):
        logger.error(f"Could not parse authors:\n{authors_raw}\nERROR: Expected a list")
        return ""

    authors = []
    for author in authors_raw:
        if not isinstance(author, dict):
            logger.error(
                f"Could not parse invalid author\n{author}\nERROR: Expected a table"
            )
            continue
        name = author.get("name") or author.get("email")
        if not name or not isinstance(name, str):
            logger.error(
                f"Could not parse invalid author\n{author}\n"
                "ERROR: Expected a non-empty 'name' or 'email'"
            )
            continue
        authors.append(name)
    return ", ".join(authors)


def _parse_pyproject_toml(
    pyproject_toml: str,
) -> MetadataDict:
    "Parse a pyproject.toml configuration file string for metadata."

    def normalize_url_label(label: str) -> str:
        """Normalize Project URL labels according to:
        https://packaging.python.org/en/latest/specifications/well-known-project-urls/#label-normalization
        """
        chars_to_remove = string.punctuation + string.whitespace
        removal_map = str.maketrans("", "", chars_to_remove)
        return label.translate(removal_map).lower()

    pyproject = tomllib.loads(pyproject_toml)

    metadata_pep621 = _get_toml_table(pyproject, "project", "")
    tool = _get_toml_table(pyproject, "tool", "")
    aiidalab = _get_toml_table(tool, "aiidalab", "tool")

    def get_str(key: str, pep621_value: str | None = None) -> str:
        "Get a string from [tool.aiidalab], falling back to the PEP 621 value."
        value = _get_toml_str(aiidalab, key, "tool.aiidalab")
        if value is not None:
            return value
        return pep621_value or ""

    def get_pep621_str(key: str) -> str | None:
        return _get_toml_str(metadata_pep621, key, "project")

    urls = _get_toml_table(metadata_pep621, "urls", "project")
    project_urls = {
        normalize_url_label(label): url
        for label in urls
        if (url := _get_toml_str(urls, label, "project.urls")) is not None
    }

    title = get_str("title", get_pep621_str("name"))
    version = get_str("version", get_pep621_str("version"))
    description = get_str("description", get_pep621_str("description"))
    authors = get_str(
        "authors", _parse_pep621_authors(metadata_pep621.get("authors", []))
    )
    external_url = get_str("external_url", project_urls.get("homepage"))
    documentation_url = get_str("documentation_url", project_urls.get("documentation"))
    logo = get_str("logo", project_urls.get("logo"))
    state = get_str(
        "state",
        _map_development_state(
            _get_toml_str_list(metadata_pep621, "classifiers", "project")
        ),
    )

    # Allow passing single category and convert to list
    # and allow parse line separated string as list
    if isinstance(aiidalab.get("categories"), str):
        categories = [c for c in aiidalab["categories"].split("\n") if c]
    else:
        categories = _get_toml_str_list(aiidalab, "categories", "tool.aiidalab")

    citations = _validate_citations(aiidalab.get("citations", []))

    return MetadataDict(
        title=title,
        description=description,
        authors=authors,
        state=state,
        documentation_url=documentation_url,
        external_url=external_url,
        logo=logo,
        categories=categories,
        version=version,
        citations=citations,
    )


def _parse_setup_cfg(
    setup_cfg: str,
) -> MetadataDict:
    """Parse a setup.cfg configuration file string for metadata."""
    import json

    cfg = ConfigParser()
    cfg.read_string(setup_cfg)

    metadata_pep426: SectionProxy | dict[Any, Any] = (
        cfg["metadata"] if "metadata" in cfg else {}  # noqa: SIM401
    )
    aiidalab: SectionProxy | dict[Any, Any] = (
        cfg["aiidalab"] if "aiidalab" in cfg else {}  # noqa: SIM401
    )

    title = aiidalab.get("title", metadata_pep426.get("name", ""))
    version = aiidalab.get("version", metadata_pep426.get("version", ""))
    description = aiidalab.get("description", metadata_pep426.get("description", ""))
    authors = aiidalab.get("authors", metadata_pep426.get("author", ""))
    external_url = aiidalab.get("external_url", metadata_pep426.get("url", ""))

    project_urls = dict(_parse_config_dict(metadata_pep426.get("project_urls", "")))
    documentation_url = aiidalab.get(
        "documentation_url",
        project_urls.get("Documentation") or project_urls.get("documentation", ""),
    )
    logo = aiidalab.get(
        "logo", project_urls.get("Logo") or project_urls.get("logo", "")
    )
    state = aiidalab.get(
        "state", _map_development_state(metadata_pep426.get("classifiers", ""))
    )

    # Allow passing single category and convert to list
    # and allow parse line separated string as list
    categories = aiidalab.get("categories", "")
    if isinstance(categories, str):
        categories = [c for c in categories.split("\n") if c]

    citation_string = aiidalab.get("citations", "[]")
    citations: list[_CitationType] = []
    try:
        citations_raw = json.loads(str(citation_string))
    except json.JSONDecodeError as e:
        logger.error(f"Could not parse citations:\n{citation_string}\nERROR: {e}")
    else:
        citations = _validate_citations(citations_raw)

    return MetadataDict(
        title=title,
        description=description,
        authors=authors,
        state=state,
        documentation_url=documentation_url,
        external_url=external_url,
        logo=logo,
        categories=categories,
        version=version,
        citations=citations,
    )


@dataclass
class Metadata:
    """App metadata specification.

    If you add any fields here, also update them in MetadataDict above.
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
    citations: list[_CitationType] = field(default_factory=list)

    @classmethod
    def from_setup_cfg(cls, content: str) -> Metadata:
        """Parse the app metadata from a setup.cfg within the app repository.

        This function will parse metadata fields from a possible "aiidalab"
        section, but falls back to the standard fields defined as part of the
        PEP 426-compliant metadata section for any missing values.
        """
        return cls(**_parse_setup_cfg(content))

    @classmethod
    def from_pyproject_toml(cls, content: str) -> Metadata:
        """Parse the app metadata from a pyproject.toml within the app repository.

        This function will parse metadata fields from a possible "tool.aiidalab"
        table, but falls back to the standard fields defined as part of the
        PEP 621-compliant "project" table for any missing values.
        """
        return cls(**_parse_pyproject_toml(content))

    @classmethod
    def from_path(cls, root: Path | GitPath) -> Metadata:
        if not root.is_dir():
            raise ValueError(f"Directory '{root}' does not exist.")

        # First, try reading metadata from `setup.cfg`
        try:
            setup_cfg = root.joinpath("setup.cfg").read_text()
        except FileNotFoundError:
            pass
        else:
            return cls.from_setup_cfg(setup_cfg)

        # setup.cfg did not exist, try reading metadata from pyproject.toml
        try:
            pyproject_toml = root.joinpath("pyproject.toml").read_text()
        except FileNotFoundError:
            raise ValueError(
                f"Directory '{root}' does not contain setup.cfg nor pyproject.toml"
            )
        else:
            return cls.from_pyproject_toml(pyproject_toml)
