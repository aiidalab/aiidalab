"""Manage a registry of applications."""

from .core import AppRegistryData, AppRegistrySchemas
from .html import build_html
from .web import build

__all__ = [
    "AppRegistryData",
    "AppRegistrySchemas",
    "build",
    "build_html",
]
