# -*- coding: utf-8 -*-
"""Manage a registry of applications."""

from .core import AppRegistryData, AppRegistrySchemas
from .web import build, build_html

__all__ = [
    "AppRegistryData",
    "AppRegistrySchemas",
    "build",
    "build_html",
]
